# PDF2Excel Design — 2026-03-05

## Goal
Extract Bilibili video metadata (URL, title, views, comments, publish date) from browser screenshot PDFs, export to Excel.

## Context
- PDFs contain browser screenshots, each page is a 1600×900 JPEG (no text layer)
- Pages showing `bilibili.com/video` URLs need extraction; others are skipped
- All PDFs share the same screenshot size → crop regions are reusable

## Architecture

### Single-region crop approach
User draws one bounding box around the browser window area on a sample page. That crop is applied to every page before sending to Claude haiku vision API.

### Components
- `main.py` — entry point, launches PyQt6 app
- `ui/main_window.py` — main window with left panel (PDF list + thumbnails) and right panel (two tabs)
- `ui/annotation_view.py` — image widget supporting draw/delete rectangle
- `extractor.py` — Claude haiku API calls, returns structured JSON per page
- `exporter.py` — writes Excel via openpyxl
- `regions.json` — persisted crop coordinates `{image_size, regions: [{name, rect}]}`
- `files/` — input PDFs

### UI Layout
```
┌─────────────────────────────────────────────────────┐
│  Toolbar: [Open Folder] [Run Extraction] [Export]   │
├──────────────┬──────────────────────────────────────┤
│ PDF List     │  Tab: 区域设置 | 提取结果             │
│              │                                      │
│ [pdf1.pdf]   │  区域设置: sample page image         │
│ [pdf2.pdf]   │  draw/delete box overlay             │
│              │  [Save Regions]                      │
│ Thumbnails   │                                      │
│ [pg1][pg2].. │  提取结果: table (page,url,title..)  │
│              │  [Export Excel]                      │
└──────────────┴──────────────────────────────────────┘
```

### Data Flow
1. User selects PDF → extract all pages as JPEG in memory
2. User picks sample page in "区域设置" tab → draws crop box → saves to regions.json
3. User clicks "Run Extraction":
   - For each page: crop to saved region → send to Claude haiku
   - Claude prompt asks for JSON: {is_bilibili_video, url, title, views, comments, date}
   - Non-bilibili pages: skipped (url field empty)
4. Results shown in table → "Export Excel" writes .xlsx

### Excel Output
Columns: 页码 | URL | 标题 | 浏览次数 | 评论次数 | 发布时间

## Dependencies
- PyQt6
- PyMuPDF (fitz)
- anthropic
- openpyxl
