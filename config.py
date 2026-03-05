import json
import os
import pathlib

CONFIG_FILE = str(pathlib.Path(__file__).parent / "config.json")

DEFAULT_PROMPT = """这是一个浏览器截图。

请判断这个页面是否是 Bilibili 视频页面（bilibili.com/video）。判断依据：
- 地址栏 URL 包含 bilibili.com/video
- 页面有视频播放器、弹幕、投币/收藏/分享等 Bilibili 特征

如果是 Bilibili 视频页面，提取以下信息并返回 JSON：
{
  "match": true,
  "url": "地址栏完整 URL，读不清则留空",
  "title": "视频标题，看不到则留空",
  "views": "播放量字符串，如 12.3万，看不到则留空",
  "comments": "评论数字符串，看不到则留空",
  "date": "发布日期字符串，看不到则留空"
}

如果不是 Bilibili 视频页面，只返回：
{"match": false}

只返回 JSON 对象，不要 markdown，不要解释。"""


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {"api_key": "", "base_url": "", "prompt": DEFAULT_PROMPT}


def save_config(data: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
