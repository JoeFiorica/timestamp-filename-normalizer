# Timestamp Filename Normalizer

Normalize top-level MP4 names to `SYYYYEMMDD - Title.mp4`.
Dates come from existing names, matching raw-data folders or a median fallback.
Fallback dates are estimates, not verified recording timestamps.

## Requirements

Windows with Python 3.11+ available as `python`. Keep `findname.bat` and `findname.py` together.
No Python packages or network access are needed.

## Usage

Double-click `findname.bat` to preview MP4s beside the launcher, or give a local folder:

```bat
findname.bat "C:\Videos\Example Folder"
findname.bat "C:\Videos\Example Folder" --apply
python findname.py --help
```

Without `--apply`, no file is renamed. Review the plan and back up valuable media first.
Commands with arguments finish without pausing. In PowerShell, prefix BAT commands
with `.\`. Quote paths containing spaces.

## Behavior

- A name such as `2022_02-08_Title.mp4` supplies its date and title.
- Otherwise, a raw folder whose name contains the cleaned title supplies the date.
  Multiple matches stop the plan. The folder's own date takes priority, followed by
  descendant files before child-directory names, sorted within each group.
- Raw dates accept `YYYYMMDD`, `YYYY-MM-DD`, `YYYY_MM_DD`, `YYYY_MM-DD` and `YYYY MM DD`.
  Invalid raw dates are ignored; invalid dated MP4 names stop the plan.
- Already normalized files stay unchanged and contribute to the median known date.
  Undated files receive that median, then one-day increments. No known date stops the plan.
- Existing destinations advance the proposed date until a free name is found.
- Titles use the existing left/right underscore-selection rule.
  MP4 names containing `findname` are skipped.

## Outputs

Plans and completed renames print to the console; no report files are created.
Exit codes: 0 completed preview/application; 1 operational error; 2 bad arguments.

## Safety and privacy

Only regular top-level MP4s are renamed; their bytes and extension case are retained.
Raw folders are read for names only. Links are not traversed; linked MP4s and network
folders are refused. Existing names are never overwritten. Avoid concurrent changes:
a write error can leave a partial batch. Keep the console output to help recover manually.
No telemetry or uploads; console filenames may identify your library.

Defaults are 10,000 scanned entries, raw depth 16 and 30 seconds.
Adjust with `--max-files` (1-100000), `--max-depth` (0-64) and `--timeout` (1-300 seconds).

## Troubleshooting

Check `python --version`; install Python separately with PATH enabled if missing.
Run `python findname.py "C:\Videos\Example Folder"` to see errors directly.
In a disposable folder, create empty `2024_01-02_Demo.mp4`. Preview leaves it unchanged;
`--apply` yields `S2024E0102 - Demo.mp4`. A second preview should propose zero renames.

Report issues with example filenames, the command and expected/actual result.
Omit personal filenames and media.
