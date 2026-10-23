"""Preview MP4 timestamp normalization; write only with --apply."""
import argparse
import os
import re
import statistics
import sys
import time
from datetime import date, timedelta
from pathlib import Path

LEGACY = re.compile(r"^(\d{4})_(\d{2})-(\d{2})_(.+)$")
NORMAL = re.compile(r"^S(\d{4})E(\d{2})(\d{2}) - (.+)$")
DATE_PATTERNS = (re.compile(r"(\d{4})[-_ ]?(\d{2})[-_ ]?(\d{2})"),
                 re.compile(r"(\d{4})_(\d{2})-(\d{2})"))


def clean_base_name(name):
    if "_" not in name:
        return name.strip()
    left, right = name.split("_", 1)
    return right.strip() if " " not in left and " " in right else left.strip()


def valid_date(parts):
    return date(*(int(value) for value in parts))


def date_in(name):
    for pattern in DATE_PATTERNS:
        for match in pattern.finditer(name):
            try:
                return valid_date(match.groups())
            except ValueError:
                continue
    return None


def local_directory(value):
    root = Path(os.path.abspath(value))
    if str(root).startswith(("\\\\", "//")):
        raise ValueError("Choose a local directory, not a network path")
    for parent in (root, *root.parents):
        if parent.is_symlink() or getattr(parent.lstat(), "st_file_attributes", 0) & 0x400:
            raise ValueError("Choose a folder reached without symbolic links or folder junctions")
    if not root.is_dir():
        raise ValueError("Directory does not exist")
    if os.name == "nt":
        import ctypes
        if ctypes.windll.kernel32.GetDriveTypeW(str(root.anchor)) == 4:
            raise ValueError("Choose a local drive")
    return root


def entries_in(root, maximum):
    entries = []
    with os.scandir(root) as scan:
        for entry in scan:
            if len(entries) >= maximum:
                raise ValueError("Directory entry limit reached; use a smaller folder or --max-files")
            entries.append(entry)
    return sorted(entries, key=lambda e: (e.name.casefold(), e.name))



def plan_renames(root, maximum=10000, max_depth=16, timeout=30):
    deadline = time.monotonic() + timeout
    remaining = [maximum]
    def scan(folder):
        if time.monotonic() > deadline:
            raise ValueError("Scanning took too long; use a smaller folder or increase --timeout")
        result = entries_in(folder, remaining[0])
        remaining[0] -= len(result)
        return result

    entries = scan(root)
    occupied = {entry.name.casefold() for entry in entries}
    directories = [entry for entry in entries if entry.is_dir(follow_symlinks=False)
                   and not getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400
                   and "findname" not in entry.name.casefold()]
    cache = {}
    def raw_date(folder):
        if folder in cache:
            return cache[folder]
        # Root-folder timestamps are useful even when its contents are empty.
        found = date_in(folder.name)
        stack = [(folder, 0)]
        while stack and found is None:
            current, depth = stack.pop()
            children = scan(current)
            # Preserve the historical file-before-directory timestamp priority.
            ordered = sorted(children, key=lambda entry: (entry.is_dir(follow_symlinks=False), entry.name.casefold(), entry.name))
            for entry in ordered:
                if entry.is_symlink() or getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400:
                    continue
                found = date_in(entry.name)
                if found:
                    break
            if found:
                break
            subdirs = [Path(entry.path) for entry in children if entry.is_dir(follow_symlinks=False)
                       and not getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400]
            if subdirs and depth >= max_depth:
                raise ValueError("Raw folders are nested too deeply; use a shallower folder or adjust --max-depth")
            stack.extend((child, depth + 1) for child in reversed(subdirs))
        cache[folder] = found
        return found

    dated, undated, known = [], [], []
    for entry in entries:
        if time.monotonic() > deadline:
            raise ValueError("Preparing the rename plan took too long; use a smaller folder or increase --timeout")
        if not entry.name.lower().endswith(".mp4") or "findname" in Path(entry.name).stem.casefold():
            continue
        if entry.is_symlink() or getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400:
            raise ValueError("Linked MP4 files are not supported; use the original files in a local folder")
        if not entry.is_file(follow_symlinks=False):
            continue
        stem = Path(entry.name).stem
        normalized = NORMAL.fullmatch(stem)
        if normalized:
            known.append(valid_date(normalized.groups()[:3]))
            continue
        legacy = LEGACY.fullmatch(stem)
        if legacy:
            stamp = valid_date(legacy.groups()[:3])
            title = clean_base_name(legacy.group(4))
        else:
            title = clean_base_name(stem)
            if not title:
                raise ValueError("Cannot determine title: " + entry.name)
            matches = [Path(d.path) for d in directories if title.casefold() in d.name.casefold()]
            if len(matches) > 1:
                raise ValueError("Ambiguous raw-data folders for: " + entry.name)
            stamp = raw_date(matches[0]) if matches else None
        if not title:
            raise ValueError("Cannot determine title: " + entry.name)
        if stamp:
            known.append(stamp)
            dated.append((entry.name, title, stamp))
        else:
            undated.append((entry.name, title))

    plans = []
    def assign(name, title, stamp):
        for _ in range(maximum + 1):
            if time.monotonic() > deadline:
                raise ValueError("Finding an unused destination name took too long; use a smaller folder")
            candidate = f"S{stamp.year:04}E{stamp:%m%d} - {title}{Path(name).suffix}"
            if candidate.casefold() not in occupied:
                occupied.add(candidate.casefold())
                plans.append((name, candidate))
                return stamp
            stamp += timedelta(days=1)
        raise ValueError("Could not find an unused destination name within the search limit; check existing filenames")

    for name, title, stamp in dated:
        assign(name, title, stamp)
    if undated:
        if not known:
            raise ValueError("No usable date was found in filenames or matching raw folders; nothing was renamed")
        current = date.fromordinal(int(statistics.median(stamp.toordinal() for stamp in known)))
        for index, (name, title) in enumerate(undated):
            final = assign(name, title, current)
            if index + 1 < len(undated):
                current = final + timedelta(days=1)
    return plans


def apply_renames(root, plans):
    # Preflight the full plan. Each rename also refuses an existing destination.
    for old, new in plans:
        source = root / old
        if source.is_symlink() or not source.is_file() or getattr(source.lstat(), "st_file_attributes", 0) & 0x400:
            raise ValueError("File changed while this run was preparing the renames: " + old)
        if os.path.lexists(root / new):
            raise ValueError("Destination already exists: " + new)
    for old, new in plans:
        if os.name == "nt":
            os.rename(root / old, root / new)
        else:
            os.link(root / old, root / new, follow_symlinks=False)
            os.unlink(root / old)
        print("Renamed:", old, "->", new)



def main(argv=None):
    if sys.version_info < (3, 11):
        print("ERROR: Python 3.11 or newer is required.", file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser(
        description='Rename MP4s to SYYYYEMMDD - Title.mp4 using names, raw-folder dates\nor an estimated fallback. Preview first; rename only with --apply.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples (use .\\ before BAT commands in PowerShell):
  findname.bat "C:\\Videos\\Example Folder"
  findname.bat "C:\\Videos\\Example Folder" --apply

Preview changes no filenames. Back up important media before --apply.
Existing files are never overwritten; a write error may leave a partial batch.
Python 3.11+ is required. No network access or uploads.
Exit codes: 0 completed preview/rename; 1 operational error; 2 bad arguments.""")
    parser.add_argument("directory", nargs="?", default=".", help="local MP4 folder (default: current directory)")
    parser.add_argument("--apply", action="store_true", help="rename files using the plan; default: preview only")
    parser.add_argument("--max-files", type=int, default=10000, help="maximum entries to scan (default: 10000; range: 1-100000)")
    parser.add_argument("--max-depth", type=int, default=16, help="maximum depth inside raw folders (default: 16; range: 0-64)")
    parser.add_argument("--timeout", type=int, default=30, help="scan/planning time limit in seconds (default: 30; range: 1-300)")
    args = parser.parse_args(argv)
    try:
        if not 1 <= args.max_files <= 100000 or not 0 <= args.max_depth <= 64 or not 1 <= args.timeout <= 300:
            raise ValueError("Limits: --max-files 1-100000, --max-depth 0-64, --timeout 1-300")
        root = local_directory(args.directory)
        plans = plan_renames(root, args.max_files, args.max_depth, args.timeout)
        for old, new in plans:
            print("Plan:", old, "->", new)
        print(f"{len(plans)} rename(s). " + ("Applying." if args.apply else "Preview only; use --apply to rename."))
        if args.apply:
            apply_renames(root, plans)
        return 0
    except (OSError, ValueError, OverflowError) as exc:
        if isinstance(exc, FileNotFoundError):
            message = "A required file or folder was not found. Check the selected folder and whether files changed during the run."
        elif isinstance(exc, PermissionError):
            message = "A file or folder could not be accessed. Check permissions and close programs that may be using the files."
        elif isinstance(exc, OSError):
            message = "A file operation failed. Check folder access and free disk space. If applying, check completed renames before retrying."
        else:
            message = str(exc)
        print("ERROR:", message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="backslashreplace")
    sys.stderr.reconfigure(errors="backslashreplace")
    raise SystemExit(main())
