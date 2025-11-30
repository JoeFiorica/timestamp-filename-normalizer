import os
import sys
import re
from datetime import datetime, timedelta
import statistics

try:

    print("================================================")
    print("         TIMESTAMP FILENAME NORMALIZER          ")
    print("================================================\n")

    root = os.getcwd()
    SCRIPT_NAME = os.path.splitext(os.path.basename(sys.argv[0]))[0].lower()

    # Legacy format: YYYY_MM-DD_Title.mp4
    legacy_pattern = re.compile(r"^(\d{4})_(\d{2})-(\d{2})_(.+)$", re.IGNORECASE)

    # Date patterns inside raw data folders
    date_patterns = [
        re.compile(r"(\d{4})[-_ ]?(\d{2})[-_ ]?(\d{2})"),
        re.compile(r"(\d{4})_(\d{2})-(\d{2})")
    ]

    known_dates = []
    undated_files = []
    original_names = {}   # path → (original_name_without_ext, original_ext)


    # ============================================================
    # Guarantee unique final name by incrementing date
    # ============================================================
    def ensure_unique_date_and_name(clean_title, ext, start_dt):
        dt = start_dt

        while True:
            Y = str(dt.year)
            MM = f"{dt.month:02}"
            DD = f"{dt.day:02}"
            candidate = f"S{Y}E{MM}{DD} - {clean_title}{ext}"
            candidate_path = os.path.join(root, candidate)

            if not os.path.exists(candidate_path):
                return (Y, MM, DD, candidate, dt)

            dt += timedelta(days=1)


    # ============================================================
    # Title cleaning
    # ============================================================
    def clean_base_name(name):
        if "_" not in name:
            return name.strip()

        left, right = name.split("_", 1)
        left_has_space = " " in left
        right_has_space = " " in right

        if not left_has_space and right_has_space:
            return right.strip()

        if left_has_space and not right_has_space:
            return left.strip()

        return left.strip()


    def determine_base_for_search(name):
        cleaned = clean_base_name(name).lower()
        if SCRIPT_NAME in cleaned:
            cleaned = cleaned.replace(SCRIPT_NAME, "").strip()
        return cleaned


    # ============================================================
    # Date extractors
    # ============================================================
    def extract_date_from_legacy(name):
        m = legacy_pattern.match(name)
        if not m:
            return None
        Y, MM, DD, title = m.groups()
        return Y, MM, DD, title


    def find_raw_folder(basename):
        basename_lower = basename.lower()
        for item in os.listdir(root):
            if os.path.isdir(item):
                item_lower = item.lower()
                if SCRIPT_NAME in item_lower:
                    continue
                if basename_lower in item_lower:
                    return os.path.join(root, item)
        return None


    def extract_date_from_raw(folder):
        for rootdir, dirs, files in os.walk(folder):

            for fname in files:
                for pat in date_patterns:
                    m = pat.search(fname)
                    if m:
                        return m.groups()

            for dname in dirs:
                for pat in date_patterns:
                    m = pat.search(dname)
                    if m:
                        return m.groups()

        return None


    # ============================================================
    # PASS 1 — Collect real dates & mark undated
    # ============================================================
    print("PASS 1: Collecting real dates...\n")

    all_paths = []

    def pass1_collect_dates(path):
        fname = os.path.basename(path)
        name, ext = os.path.splitext(fname)

        # Store original info
        original_names[path] = (name, ext)

        if SCRIPT_NAME in name.lower():
            return False

        # Legacy
        legacy = extract_date_from_legacy(name)
        if legacy:
            Y, MM, DD, _title = legacy
            known_dates.append((Y, MM, DD))
            return True

        # Raw folder
        base = determine_base_for_search(name)
        folder = find_raw_folder(base)
        if folder:
            date_tuple = extract_date_from_raw(folder)
            if date_tuple:
                known_dates.append(date_tuple)
                return True

        # Needs fallback
        undated_files.append(path)
        return False


    # Collect everything
    for fname in os.listdir(root):
        if fname.lower().endswith(".mp4"):
            full = os.path.join(root, fname)
            all_paths.append(full)
            pass1_collect_dates(full)


    # Compute median (ordinal-safe)
    if known_dates:
        ordinals = [
            datetime(int(Y), int(MM), int(DD)).toordinal()
            for (Y, MM, DD) in known_dates
        ]
        median_ordinal = int(statistics.median(ordinals))
        median_dt = datetime.fromordinal(median_ordinal)
        median_date = (
            str(median_dt.year),
            f"{median_dt.month:02}",
            f"{median_dt.day:02}"
        )
    else:
        median_date = None


    # ============================================================
    # PASS 2 — Real-date renaming
    # ============================================================
    print("\nPASS 2: Renaming dated files...\n")

    def pass2_rename(path):
        original_name, ext = original_names[path]

        if SCRIPT_NAME in original_name.lower():
            return

        clean_title = clean_base_name(original_name)

        # 1. Legacy
        legacy = extract_date_from_legacy(original_name)
        if legacy:
            Y, MM, DD, title = legacy
            clean_title = clean_base_name(title)
            base_dt = datetime(int(Y), int(MM), int(DD))

            Y, MM, DD, new_name, final_dt = ensure_unique_date_and_name(clean_title, ext, base_dt)
            os.rename(path, os.path.join(root, new_name))
            print(f"Legacy → {new_name}")

            if path in undated_files:
                undated_files.remove(path)
            return

        # 2. Raw-folder detection
        base = determine_base_for_search(original_name)
        folder = find_raw_folder(base)

        if folder:
            tup = extract_date_from_raw(folder)
            if tup:
                Y, MM, DD = tup
                base_dt = datetime(int(Y), int(MM), int(DD))

                Y, MM, DD, new_name, final_dt = ensure_unique_date_and_name(clean_title, ext, base_dt)
                os.rename(path, os.path.join(root, new_name))
                print(f"Raw-data date → {new_name}")

                if path in undated_files:
                    undated_files.remove(path)
                return


    for path in all_paths:
        if path not in undated_files:
            pass2_rename(path)


    # ============================================================
    # PASS 3 — Fallback (median + increments)
    # ============================================================
    print("\nPASS 3: Assigning fallback median + incremental dates...\n")

    if median_date:
        current_dt = datetime(int(median_date[0]),
                              int(median_date[1]),
                              int(median_date[2]))

        undated_files.sort()

        for path in undated_files:
            name, ext = original_names[path]
            clean_title = clean_base_name(name)

            Y, MM, DD, new_name, final_dt = ensure_unique_date_and_name(clean_title, ext, current_dt)
            os.rename(path, os.path.join(root, new_name))
            print(f"Fallback date → {new_name}")

            current_dt = final_dt + timedelta(days=1)

    else:
        print("ERROR: No real dates found for fallback.\n")


    print("\nDONE.")
    input("\nPress Enter to exit...")

except Exception as e:
    print("\n================ FATAL ERROR ================\n")
    print(str(e))
    print("\n=============================================\n")
    input("Press Enter to exit...")
