"""
config.py — 配置读写
"""
import json
import os
from pathlib import Path

_CONFIG_FILE = Path(__file__).parent / "config.json"

_DEFAULT_PROMPT1 = """\
我给你展示了一张由多个截图拼成的3×4网格图，每个格子左上角有白色标签，标签上的数字是该截图的编号（编号不一定从0开始，是实际的图片序号）。
这些截图来自B站（bilibili.com）电子存证文件，内容是电脑屏幕截图。

请判断每个编号的截图是否是以下两类页面之一：
1. B站视频页：特征包括——顶部B站导航栏（"首页/番剧/直播..."）、中间偏左有视频播放框、视频标题、右侧有其他视频推荐列表、下方有点赞/投币/收藏/转发按钮行
2. B站视频评论页（视频页向下滚动）：特征包括——顶部B站导航栏、视频描述文字区域、视频标签（如"MAD/热血/..."）、可能有广告横幅、有"评论 XXX"字样的评论区入口

注意：宁可多召回（将非视频页误判为候选），绝对不要漏掉真正的视频页/评论页。

请返回JSON格式，candidates中填写标签上的实际编号数字：
{"candidates": [8, 12, 17]}
如果网格中没有一张是视频/评论页，返回 {"candidates": []}
只返回JSON，不要解释。"""

_DEFAULT_PROMPT2 = """\
我给你展示了三张图：
- 图1（info1）：示例截图，红框标注了需要提取的字段位置（URL、标题、播放量+弹幕量+发布时间、点赞/投币/收藏/转发、是否有合集）
- 图2（info2）：示例截图，红框标注了视频描述、视频标签、评论数的位置
- 图3：实际需要提取信息的B站截图

【第一步：判断图3是否是有效页面】
图3必须同时满足以下两个条件才算有效：
1. 顶部有浏览器地址栏，且其中的完整URL清晰可读（非客户端/APP/小窗/弹窗遮挡状态）
2. 是B站视频页或视频评论页（参照info1和info2的样式）

如果图3是B站APP客户端、小窗播放、或者地址栏被遮挡/不可见，直接返回：{"match": false}
如果图3不是B站视频/评论页，也直接返回：{"match": false}

【第二步：直接从图3视觉内容提取信息】
请用肉眼仔细阅读图3中的每个字符，特别是：
- URL：逐字符读取浏览器地址栏中的BV号（BV开头+10位字母数字），大小写敏感；i和l、1和I、0和O视觉上易混淆请仔细辨认；OCR提供的文本仅供字段定位参考，BV号必须以地址栏画面为最终依据
- 所有数字字段也请逐位读取

返回JSON：
{
  "match": true,
  "url": "地址栏中完整URL，BV号逐字符读取",
  "title": "视频标题，看不到则留空",
  "views": "播放量如96.6万，看不到则留空",
  "danmaku": "弹幕量如516，看不到则留空",
  "date": "发布时间含年月日时分秒如2023-05-30 14:22:08，看不到则留空",
  "has_playlist": "查看截图右侧栏：若出现'订阅合集'按钮则填是，明确没有则填否，看不清则留空",
  "likes": "点赞数如8.3万，看不到则留空",
  "coins": "投币数如1.7万，看不到则留空",
  "favorites": "收藏数如2.5万，看不到则留空",
  "shares": "转发数如3327，看不到则留空",
  "description": "视频描述全文，看不到则留空",
  "tags": "视频标签逗号分隔，看不到则留空",
  "comments": "评论总数如983，看不到则留空",
  "notes": "若某个已填字段的值你不确定，用10字以内说明，如'BV末位不确定'；若全部清晰则留空。不要解释字段为空的原因。"
}

只返回JSON对象，不要markdown，不要解释。"""


def load_config() -> dict:
    if _CONFIG_FILE.exists():
        try:
            return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "api_key": "",
        "base_url": "",
        "detected_provider": "",
        "model_stage1": "",
        "model_stage2": "",
        "prompt1": _DEFAULT_PROMPT1,
        "prompt2": _DEFAULT_PROMPT2,
    }


def save_config(cfg: dict):
    _CONFIG_FILE.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_default_prompt1() -> str:
    return _DEFAULT_PROMPT1


def get_default_prompt2() -> str:
    return _DEFAULT_PROMPT2
