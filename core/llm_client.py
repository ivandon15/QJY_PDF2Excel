"""
core/llm_client.py — 统一 LLM 调用层

支持 OpenAI-compatible 和 Anthropic-compatible 两种 API，
用户只需提供一套 api_key + base_url，系统自动检测 provider 类型。
"""
import base64
import re

_provider_cache: dict[str, str] = {}  # base_url -> "openai" | "anthropic"


_PROBE_MSG = [{"role": "user", "content": "hi"}]
_PROBE_TOKENS = 8


def auto_detect_provider(api_key: str, base_url: str) -> str:
    """
    自动检测 base_url 的 provider 类型。
    策略（逐步降级）：
      1. 试 OpenAI /models 列表   → openai
      2. 试 Anthropic /models 列表 → anthropic
      3. 试 OpenAI chat probe      → openai
      4. 试 Anthropic chat probe   → anthropic
      5. 全部失败 → RuntimeError
    结果缓存，避免重复检测。
    """
    cache_key = f"{base_url}::{api_key[:8]}"
    if cache_key in _provider_cache:
        return _provider_cache[cache_key]

    # 1. Try OpenAI models listing
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
        models = client.models.list()
        _ = [m.id for m in models.data]
        _provider_cache[cache_key] = "openai"
        return "openai"
    except Exception:
        pass

    # 2. Try Anthropic models listing
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key, base_url=base_url)
        models = client.models.list()
        _ = [m.id for m in models.data]
        _provider_cache[cache_key] = "anthropic"
        return "anthropic"
    except Exception:
        pass

    # 3. Try OpenAI chat probe (many proxies support chat but not /models)
    try:
        from openai import OpenAI
        from openai import AuthenticationError, PermissionDeniedError as OAIPermDenied
        client = OpenAI(api_key=api_key, base_url=base_url)
        client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=_PROBE_TOKENS,
            messages=_PROBE_MSG,
        )
        _provider_cache[cache_key] = "openai"
        return "openai"
    except (AuthenticationError, OAIPermDenied):
        # 401/403 = endpoint understood OpenAI format, just key/model issue
        _provider_cache[cache_key] = "openai"
        return "openai"
    except Exception:
        pass

    # 4. Try Anthropic chat probe
    try:
        from anthropic import Anthropic
        from anthropic import AuthenticationError as AnthAuthError, PermissionDeniedError as AnthPermDenied
        client = Anthropic(api_key=api_key, base_url=base_url)
        client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=_PROBE_TOKENS,
            messages=_PROBE_MSG,
        )
        _provider_cache[cache_key] = "anthropic"
        return "anthropic"
    except (AnthAuthError, AnthPermDenied):
        # 401/403 = endpoint understood Anthropic format
        _provider_cache[cache_key] = "anthropic"
        return "anthropic"
    except Exception:
        pass

    raise RuntimeError(
        f"无法识别 endpoint：{base_url}\n"
        "请确认 Base URL 和 API Key 正确，并在「设置」中手动输入模型名称后直接使用。"
    )


def fetch_models(api_key: str, base_url: str) -> list[str]:
    """
    拉取可用模型列表。
    若 /models 接口不支持（404 等），返回空列表——UI 的 ComboBox 支持手动输入。
    """
    provider = auto_detect_provider(api_key, base_url)
    if provider == "openai":
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url=base_url)
            models = client.models.list()
            return sorted(m.id for m in models.data)
        except Exception:
            return []
    else:
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=api_key, base_url=base_url)
            models = client.models.list()
            return sorted(m.id for m in models.data)
        except Exception:
            return []


def _img_content(image_bytes: bytes, ext: str) -> dict:
    """构造图片 content block（OpenAI 格式，可被两种 provider 的包装层使用）。"""
    mime_map = {
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png", "gif": "image/gif", "webp": "image/webp",
    }
    mime = mime_map.get(ext.lower(), "image/jpeg")
    b64 = base64.standard_b64encode(image_bytes).decode()
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{mime};base64,{b64}"},
    }


def chat(
    model: str,
    api_key: str,
    base_url: str,
    messages: list[dict],
    max_tokens: int = 1024,
) -> str:
    """
    统一调用接口。messages 使用 OpenAI 格式（含图片时用 image_url 块）。
    内部根据检测到的 provider 路由到对应库。
    """
    provider = auto_detect_provider(api_key, base_url)

    if provider == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip()

    else:
        # Anthropic — 转换 messages 格式
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key, base_url=base_url)
        anthropic_messages = _convert_to_anthropic(messages)
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=anthropic_messages,
        )
        return resp.content[0].text.strip()


def _convert_to_anthropic(messages: list[dict]) -> list[dict]:
    """将 OpenAI 格式 messages 转换为 Anthropic 格式。"""
    result = []
    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        if isinstance(content, str):
            result.append({"role": role, "content": content})
            continue

        # content 是 list（多模态）
        anthropic_content = []
        for block in content:
            if block["type"] == "text":
                anthropic_content.append({"type": "text", "text": block["text"]})
            elif block["type"] == "image_url":
                url = block["image_url"]["url"]
                # data:image/png;base64,xxxx
                m = re.match(r"data:([^;]+);base64,(.+)", url)
                if m:
                    anthropic_content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": m.group(1),
                            "data": m.group(2),
                        },
                    })
        result.append({"role": role, "content": anthropic_content})
    return result


def clear_provider_cache():
    """清除 provider 检测缓存（切换 key/url 时调用）。"""
    _provider_cache.clear()
