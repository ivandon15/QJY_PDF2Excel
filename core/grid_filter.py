"""
core/grid_filter.py — Stage 1：将图片拼成3×4网格，发给LLM批量过滤候选

返回候选图片序号列表（宁多勿漏）。
"""
import json
import io
import re
from PIL import Image, ImageDraw, ImageFont

GRID_COLS = 3
GRID_ROWS = 4
BATCH_SIZE = GRID_COLS * GRID_ROWS  # 12

# 每个缩略图的目标尺寸（原图按比例缩放，宽不超过此值）
THUMB_W = 480
THUMB_H = 300

LABEL_FONT_SIZE = 28
LABEL_PAD = 4
SEPARATOR = 4  # 格子间隔像素


def _make_thumbnail(img_bytes: bytes, ext: str) -> Image.Image:
    try:
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        img.thumbnail((THUMB_W, THUMB_H), Image.LANCZOS)
        # 粘贴到固定画布（保证对齐）
        canvas = Image.new("RGB", (THUMB_W, THUMB_H), (40, 40, 40))
        canvas.paste(img, (0, 0))
        return canvas
    except Exception:
        return Image.new("RGB", (THUMB_W, THUMB_H), (60, 60, 60))


def _draw_label(canvas: Image.Image, label: str):
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", LABEL_FONT_SIZE)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    # 黑色背景框
    draw.rectangle([LABEL_PAD, LABEL_PAD, tw + LABEL_PAD * 3, th + LABEL_PAD * 3], fill=(0, 0, 0, 200))
    draw.text((LABEL_PAD * 2, LABEL_PAD * 2), label, fill=(255, 255, 255), font=font)


def build_grid(batch: list[tuple[int, bytes, str]]) -> bytes:
    """
    将一批（最多12张）(index, bytes, ext) 拼成3×4网格PNG。
    返回 PNG bytes。
    """
    thumbs = []
    for (img_idx, img_bytes, ext) in batch:
        thumb = _make_thumbnail(img_bytes, ext)
        _draw_label(thumb, str(img_idx))
        thumbs.append(thumb)

    # 填充空格到12张
    while len(thumbs) < BATCH_SIZE:
        thumbs.append(Image.new("RGB", (THUMB_W, THUMB_H), (20, 20, 20)))

    grid_w = GRID_COLS * THUMB_W + (GRID_COLS - 1) * SEPARATOR
    grid_h = GRID_ROWS * THUMB_H + (GRID_ROWS - 1) * SEPARATOR
    grid = Image.new("RGB", (grid_w, grid_h), (10, 10, 10))

    for i, thumb in enumerate(thumbs):
        col = i % GRID_COLS
        row = i // GRID_COLS
        x = col * (THUMB_W + SEPARATOR)
        y = row * (THUMB_H + SEPARATOR)
        grid.paste(thumb, (x, y))

    buf = io.BytesIO()
    grid.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def filter_batch(
    batch: list[tuple[int, bytes, str]],
    prompt1: str,
    model: str,
    api_key: str,
    base_url: str,
) -> list[int]:
    """
    对一批图片执行 Stage1 过滤。
    返回这批图片中被判定为候选的原始 index 列表。
    """
    from core.llm_client import chat

    grid_bytes = build_grid(batch)
    index_map = [item[0] for item in batch]  # 位置 -> 原始 index

    messages = [{
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{__import__('base64').b64encode(grid_bytes).decode()}"},
            },
            {"type": "text", "text": prompt1},
        ],
    }]

    try:
        text = chat(model=model, api_key=api_key, base_url=base_url,
                    messages=messages, max_tokens=256)
        text = text.strip()
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            data = json.loads(m.group())
        else:
            data = json.loads(text)
        returned = data.get("candidates", [])
        # 标签显示的是原始 index，LLM 看到标签直接返回原始 index
        # 用 set 快速过滤，只保留确实在这批里的值（防幻觉）
        valid_indices = set(index_map)
        result = [v for v in returned if isinstance(v, int) and v in valid_indices]
        return result
    except Exception:
        # 出错时保守返回全部（宁多勿漏）
        return [item[0] for item in batch]


def run_stage1(
    all_images: list[tuple[int, bytes, str]],
    prompt1: str,
    model: str,
    api_key: str,
    base_url: str,
    progress_cb=None,  # callable(batch_done: int, total_batches: int, candidates: list[int])
    stop_flag=None,    # threading.Event
) -> list[int]:
    """
    对全部图片执行 Stage1 批次过滤，返回所有候选图片的原始 index 列表。
    progress_cb: 每批完成后回调
    stop_flag: threading.Event，置位时终止
    """
    candidates = []
    total_batches = (len(all_images) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_num in range(total_batches):
        if stop_flag and stop_flag.is_set():
            break
        start = batch_num * BATCH_SIZE
        batch = all_images[start: start + BATCH_SIZE]
        found = filter_batch(batch, prompt1, model, api_key, base_url)
        candidates.extend(found)
        if progress_cb:
            progress_cb(batch_num + 1, total_batches, found)

    return sorted(set(candidates))
