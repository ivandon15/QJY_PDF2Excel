"""
core/url_normalizer.py — BV ID 提取与 URL 规范化
"""
import re

# BV ID 格式：BV + 10位字母数字
_BV_RE = re.compile(r'BV[A-Za-z0-9]{10}')

# 视觉上容易混淆的字符映射（用于 BV 号去重比较）
# 小写 l / 大写 I / 数字 1 → 小写 i；大写 O → 数字 0
_CONFUSE_MAP = str.maketrans("lI1O", "iii0")


def extract_bv(raw_url: str) -> str | None:
    """从任意 URL 或文本中提取 BV ID，返回 None 如果找不到。"""
    if not raw_url:
        return None
    m = _BV_RE.search(raw_url)
    return m.group() if m else None


def bv_canonical(bv: str) -> str:
    """
    将 BV ID 中视觉上易混淆的字符归一化，用于同 BV 不同拼写的去重。
    归一化规则（仅用于比较，不用于输出）：
      l / i / 1 / I → i    （BV 号中第2位之后可能出现）
      O → 0
    """
    # 只处理 BV 后的 10 位，前缀 "BV" 固定不变
    if not bv.startswith("BV") or len(bv) < 3:
        return bv
    return "BV" + bv[2:].translate(_CONFUSE_MAP)


def normalize_url(raw_url: str) -> str:
    """
    将 URL 规范化为 https://www.bilibili.com/video/BVxxxxxxxxxx/
    若无法提取 BV ID，返回原始 URL（去除首尾空格）。
    """
    bv = extract_bv(raw_url)
    if bv:
        return f"https://www.bilibili.com/video/{bv}/"
    return raw_url.strip()


def is_bilibili_video_url(url: str) -> bool:
    """判断是否包含有效 BV ID。"""
    return bool(extract_bv(url))
