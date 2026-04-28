"""
core/ocr_engine.py — 封装 ocr_extract Swift 二进制调用
"""
import json
import subprocess
import tempfile
import os
from pathlib import Path

_BIN = Path(__file__).parent.parent / "ocr" / "ocr_extract"


def ocr_image_bytes(image_bytes: bytes, ext: str) -> list[dict]:
    """
    对图片 bytes 执行 macOS Vision OCR。
    返回文本片段列表: [{"text": str, "x": float, "y": float, "w": float, "h": float, "conf": float}, ...]
    若二进制不存在或系统不支持，返回空列表（降级）。
    """
    if not _BIN.exists():
        return []

    suffix = f".{ext}" if not ext.startswith(".") else ext
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(image_bytes)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [str(_BIN), tmp_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        line = result.stdout.strip()
        if not line:
            return []
        data = json.loads(line)
        if "error" in data:
            return []
        return data.get("texts", [])
    except Exception:
        return []
    finally:
        os.unlink(tmp_path)


def ocr_texts_to_string(texts: list[dict]) -> str:
    """将文本片段列表按从上到下顺序拼接成纯文本字符串，供 LLM 参考。"""
    sorted_texts = sorted(texts, key=lambda t: (round(t.get("y", 0) * 20), t.get("x", 0)))
    return "\n".join(t["text"] for t in sorted_texts if t.get("text"))
