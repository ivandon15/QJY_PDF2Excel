"""
core/aggregator.py — 以规范化 URL 为 key，合并多张截图的字段

规则：
- 同一 URL 的截图字段合并：先出现的非空值优先（不覆盖）
- notes 字段取最短的唯一备注，截断至 40 字
- BV 号中视觉易混淆字符（i/l/1/I，O/0）可能导致同一视频出现多个 URL
  → 以 canonical BV 为分组 key，按出现次数投票选取最终 BV 拼写
- 最终按 URL 去重，返回干净的行列表
"""
from collections import Counter
from core.url_normalizer import normalize_url, is_bilibili_video_url, extract_bv, bv_canonical

_MERGE_FIELDS = [
    "url", "title", "views", "danmaku", "date", "has_playlist",
    "likes", "coins", "favorites", "shares", "comments",
    "description", "tags",
]


def _merge_into(target: dict, src: dict):
    """将 src 的非空字段合并进 target（不覆盖已有值）。"""
    for k in _MERGE_FIELDS:
        v = src.get(k, "")
        if v and not target.get(k):
            target[k] = v
    # notes：收集所有不同备注，最后取最短的
    src_notes = src.get("notes", "").strip()
    if src_notes:
        existing_list = list(target.get("_notes_list", []))
        existing_lower = {n.lower() for n in existing_list}
        if src_notes.lower() not in existing_lower:
            existing_list.append(src_notes)
        target["_notes_list"] = existing_list
    # 记录该 BV 拼写出现次数（用于投票）
    bv = extract_bv(src.get("url", ""))
    if bv:
        bv_counter: Counter = target.setdefault("_bv_counter", Counter())
        bv_counter[bv] += 1


def aggregate(
    results: dict[int, dict],
    all_images: list[tuple[int, bytes, str]],
) -> list[dict]:
    """
    将 Stage2 结果按 URL 去重合并，返回干净的行列表。
    all_images 仅用于确定图片总顺序（按 index 排序处理）。
    """
    # canonical BV -> 合并后的行（用于跨拼写合并）
    canon_rows: dict[str, dict] = {}
    # 保留第一次出现的顺序（按 canonical BV）
    canon_order: list[str] = []

    for idx in sorted(results.keys()):
        result = results[idx]
        if not result.get("match"):
            continue

        raw_url = result.get("url", "").strip()
        norm_url = normalize_url(raw_url) if raw_url else ""

        if not (norm_url and is_bilibili_video_url(norm_url)):
            # 无有效URL的截图直接跳过（用户确认：有效页面一定有地址栏URL）
            continue

        bv = extract_bv(norm_url)
        canon = bv_canonical(bv) if bv else ""
        if not canon:
            continue

        if canon not in canon_rows:
            canon_rows[canon] = {"url": norm_url}
            canon_order.append(canon)
        _merge_into(canon_rows[canon], result)

    rows = []
    for canon in canon_order:
        row = canon_rows[canon]

        # 用投票结果选出最终 BV 拼写
        bv_counter: Counter = row.pop("_bv_counter", Counter())
        if bv_counter:
            best_bv, _ = bv_counter.most_common(1)[0]
            row["url"] = f"https://www.bilibili.com/video/{best_bv}/"

        # 取最短备注，截断至 40 字
        notes_list = row.pop("_notes_list", [])
        if notes_list:
            notes_list.sort(key=len)
            row["notes"] = notes_list[0][:40]
        else:
            row["notes"] = row.get("notes", "")

        rows.append(row)

    return rows
