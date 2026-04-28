"""
core/detail_extractor.py — Stage 2：对候选图片执行 OCR + LLM 精细提取

每张图：
  1. macOS Vision OCR → 文本参考（帮助 LLM 定位字段，但 URL/BV 以地址栏视觉为准）
  2. info1 + info2 参考图 + 原图 + OCR文本 → LLM vision → 结构化字段JSON
"""
import base64
import json
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.ocr_engine import ocr_image_bytes, ocr_texts_to_string
from core.llm_client import chat

_REF_DIR = Path(__file__).parent.parent / "docs" / "ref"
_INFO1 = _REF_DIR / "info1.png"
_INFO2 = _REF_DIR / "info2.png"

_REF1_B64: str | None = None
_REF2_B64: str | None = None


def _load_refs():
    global _REF1_B64, _REF2_B64
    if _REF1_B64 is None and _INFO1.exists():
        _REF1_B64 = base64.standard_b64encode(_INFO1.read_bytes()).decode()
    if _REF2_B64 is None and _INFO2.exists():
        _REF2_B64 = base64.standard_b64encode(_INFO2.read_bytes()).decode()


def extract_one(
    img_index: int,
    img_bytes: bytes,
    img_ext: str,
    prompt2: str,
    model: str,
    api_key: str,
    base_url: str,
) -> tuple[int, dict]:
    """
    提取单张候选图片的结构化字段。
    返回 (img_index, result_dict)。
    """
    _load_refs()

    # Step 1: OCR（提供文字参考，帮助 LLM 识别字段，但 BV 号以地址栏视觉为准）
    ocr_texts = ocr_image_bytes(img_bytes, img_ext)
    ocr_str = ocr_texts_to_string(ocr_texts) if ocr_texts else ""

    # Step 2: 构造 messages
    mime_map = {
        "jpeg": "image/jpeg", "jpg": "image/jpeg",
        "png": "image/png", "gif": "image/gif", "webp": "image/webp",
    }
    mime = mime_map.get(img_ext.lower(), "image/jpeg")
    img_b64 = base64.standard_b64encode(img_bytes).decode()

    content = []

    # 参考图1
    if _REF1_B64:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{_REF1_B64}"},
        })
        content.append({"type": "text", "text": "图1（info1 参考示例，红框标注了URL、标题、播放量、弹幕量、发布时间、互动数据位置）"})

    # 参考图2
    if _REF2_B64:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{_REF2_B64}"},
        })
        content.append({"type": "text", "text": "图2（info2 参考示例，红框标注了视频描述、视频标签、评论数位置）"})

    # 实际图片
    content.append({
        "type": "image_url",
        "image_url": {"url": f"data:{mime};base64,{img_b64}"},
    })

    # OCR 辅助文本：提供字段参考，明确提示 BV 号须以地址栏视觉为准
    ocr_hint = ""
    if ocr_str:
        ocr_hint = (
            f"\n\n【OCR识别文本（仅供字段定位参考；URL/BV号请以地址栏视觉内容为准，不要直接采用OCR读出的BV号）】\n"
            f"{ocr_str}"
        )

    content.append({"type": "text", "text": prompt2 + ocr_hint})

    messages = [{"role": "user", "content": content}]

    try:
        text = chat(
            model=model,
            api_key=api_key,
            base_url=base_url,
            messages=messages,
            max_tokens=1024,
        )
        text = text.strip()
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            return img_index, json.loads(m.group())
        return img_index, json.loads(text)
    except json.JSONDecodeError:
        return img_index, {"match": False, "error": "json_parse_error"}
    except Exception as e:
        return img_index, {"match": False, "error": str(e)[:120]}


def run_stage2(
    all_images: list[tuple[int, bytes, str]],
    candidates: list[int],
    prompt2: str,
    model: str,
    api_key: str,
    base_url: str,
    session=None,         # core.session.Session 实例，用于实时保存
    progress_cb=None,     # callable(done: int, total: int, img_index: int, result: dict)
    stop_flag=None,       # threading.Event
    max_workers: int = 4,
) -> dict[int, dict]:
    """
    对候选图片执行精细提取。
    返回 {img_index: result_dict}。
    """
    # 已处理的跳过（断点续提）
    already_done = {}
    if session:
        for k, v in session.get_processed().items():
            already_done[int(k)] = v

    image_map = {idx: (b, e) for idx, b, e in all_images}
    todo = [c for c in candidates if c not in already_done]
    results = dict(already_done)
    done_count = len(already_done)
    total = len(candidates)

    def process(img_index):
        if img_index not in image_map:
            return img_index, {"match": False}
        b, e = image_map[img_index]
        return extract_one(img_index, b, e, prompt2, model, api_key, base_url)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process, idx): idx for idx in todo}
        for future in as_completed(futures):
            if stop_flag and stop_flag.is_set():
                break
            idx, result = future.result()
            results[idx] = result
            done_count += 1
            if session:
                session.save_result(idx, result)
            if progress_cb:
                progress_cb(done_count, total, idx, result)

    return results
