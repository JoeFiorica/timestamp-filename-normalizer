# Timestamp Filename Normalizer

A concise Python utility that standardizes inconsistent MP4 filenames by assigning each one a reliable date—pulled from legacy filename patterns, raw data folders, or a median-based fallback—then converting everything into the clean, sortable format:

```
SYYYYEMMDD - Title.mp4
```

---

## 🎯 What This Tool Does

- Normalizes legacy names like `2022_02-08_Title.mp4`
- Extracts timestamps from associated raw-data folders
- Cleans messy titles (removes prefixes/suffixes like `Twitter_`)
- Assigns fallback dates using the median of all known timestamps
- Auto-increments dates to avoid duplicates (e.g., Twitter reposts)
- Guarantees correct `.mp4` extensions and prevents naming collisions

---

## 🧠 How It Works

### 1. Legacy Filename Parsing
Matches:

```
YYYY_MM-DD_Title.mp4
```

→ Converts to standard format.

### 2. Raw Folder Timestamp Extraction
If the MP4 filename has no date:

- Locates a raw-data folder with a matching title
- Recursively scans filenames and subfolders for valid timestamps
- Applies the extracted date

### 3. Median-Based Fallback
If no datestamp exists at all:

- Calculates the median of all extracted dates
- Applies it to undated files
- Increments by +1 day for duplicates

---

## ▶️ Usage

Run the tool by double-clicking or via terminal:

```bash
python timestamp-filename-normalizer.py
```

The script:

1. Scans the current folder for `.mp4`
2. Parses any legacy filenames
3. Extracts dates from raw folders
4. Assigns fallback median timestamps
5. Renames files into `SYYYYEMMDD - Title.mp4`
6. Prints a clear, readable log
7. Pauses before closing

---

## 📁 Expected Folder Layout

```
/YourFolder/
│
├── Title.mp4
├── RAW_2023_01-24_Title/
│     ├── metadata.json
│     ├── frame_2023-01-24.png
│     └── ...
│
└── 2022_02-08_Title.mp4
```

Only `.mp4` files in the main directory are renamed.  
Subfolders are used only to extract timestamps.

---

## ⚠️ Notes

- Handles `.mp4` only (top-level directory)
- Skips already normalized files
- Uses case-insensitive matching for raw-data folders
- Ensures every output filename is unique and chronological

---

## ✅ Result

A completely standardized, sortable library of MP4 files—clean, dated, and archive-ready.