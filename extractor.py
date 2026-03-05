import os
import base64
import json
import re
import io
from anthropic import Anthropic

PROMPT = """This is a browser screenshot, likely from a Chinese website.

First, look carefully at:
1. The browser address bar (top of the browser) for the URL
2. The page content for any bilibili.com/video indicators

Determine if this is a Bilibili video page (bilibili.com). Signs include:
- Address bar showing a URL with "bilibili" or "b23.tv"
- Page layout typical of Bilibili video pages (video player, 弹幕, 投币/收藏/分享 buttons)
- Any visible bilibili logo or branding

If this IS a Bilibili video page, return ONLY this JSON:
{
  "is_bilibili_video": true,
  "url": "<full URL from address bar, or empty string if not readable>",
  "title": "<video title, or empty string if not visible>",
  "views": "<view count as string e.g. 12.3万, or empty string>",
  "comments": "<comment count as string, or empty string>",
  "date": "<publish date as string, or empty string>"
}

If this is NOT a Bilibili video page, return ONLY:
{"is_bilibili_video": false}

Return ONLY the JSON object. No markdown, no explanation."""

EXT_TO_MIME = {
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}


def extract_from_bytes(image_bytes: bytes, img_ext: str, crop_regions: list | None, prompt: str) -> dict:
    """Extract Bilibili metadata from raw image bytes via Claude sonnet vision."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise EnvironmentError("请设置 ANTHROPIC_API_KEY 环境变量")

    if crop_regions:
        from PIL import Image
        src = Image.open(io.BytesIO(image_bytes))
        crops = []
        for region in crop_regions:
            x, y, w, h = region["rect"]
            crops.append(src.crop((x, y, x + w, y + h)))
        # stitch vertically with a 4px separator
        total_h = sum(c.height for c in crops) + 4 * (len(crops) - 1)
        max_w = max(c.width for c in crops)
        stitched = Image.new("RGB", (max_w, total_h), (30, 30, 30))
        y_off = 0
        for c in crops:
            stitched.paste(c, (0, y_off))
            y_off += c.height + 4
        buf = io.BytesIO()
        stitched.save(buf, format="JPEG", quality=90)
        image_bytes = buf.getvalue()
        img_ext = "jpeg"

    mime = EXT_TO_MIME.get(img_ext.lower(), "image/jpeg")
    b64 = base64.standard_b64encode(image_bytes).decode()
    client_kwargs = {}
    if os.environ.get("ANTHROPIC_BASE_URL"):
        client_kwargs["base_url"] = os.environ["ANTHROPIC_BASE_URL"]
    client = Anthropic(**client_kwargs)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": mime, "data": b64}
                },
                {"type": "text", "text": prompt}
            ]
        }]
    )

    text = response.content[0].text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
        return {}
