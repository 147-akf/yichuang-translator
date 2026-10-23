"""Translation engine for 译窗 Translator.

No API key and no third-party dependencies. Text is sent to Google's
public gtx endpoint first; if that fails, the MyMemory API is used as a
fallback. Both are free public services intended for light/personal use.
"""

from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
HTTP_TIMEOUT = 12  # seconds

GOOGLE_ENDPOINT = "https://translate.googleapis.com/translate_a/single"
MYMEMORY_ENDPOINT = "https://api.mymemory.translated.net/get"

GOOGLE_CHUNK_CHARS = 1800
MYMEMORY_CHUNK_CHARS = 450
MYMEMORY_CJK_CHUNK_CHARS = 150

_CJK_RE = re.compile(r"[㐀-䶿一-鿿豈-﫿]")

# A sentence should not be cut right after these characters.
_SENTENCE_ENDINGS = "。！？；.!?;"


class TranslationError(Exception):
    """Raised when no provider could translate the text."""


@dataclass
class TranslationResult:
    text: str
    source: str
    target: str
    provider: str
    fallback: bool = False


def has_chinese(text: str) -> bool:
    """Return True if the text contains any CJK ideograph."""
    return bool(_CJK_RE.search(text))


def resolve_languages(text: str, mode: str = "auto") -> tuple[str, str]:
    """Return (source, target) for a UI direction mode.

    mode: "auto" | "zh-en" | "en-zh"
    """
    if mode == "zh-en":
        return "zh-CN", "en"
    if mode == "en-zh":
        return "en", "zh-CN"
    if has_chinese(text):
        return "zh-CN", "en"
    return "en", "zh-CN"


def translate(text: str, mode: str = "auto") -> TranslationResult:
    """Translate text between Chinese and English.

    Raises TranslationError when both providers fail.
    """
    if text is None or not text.strip():
        raise TranslationError("没有可翻译的文字。")

    source_guess, target = resolve_languages(text, mode)
    google_source = "auto" if mode == "auto" else source_guess
    errors: list[str] = []

    try:
        translated, detected = _translate_with_google(text, google_source, target)
        if detected in ("", "auto"):
            detected = source_guess
        return TranslationResult(
            text=translated,
            source=detected,
            target=target,
            provider="Google",
        )
    except Exception as exc:  # fall back to the second provider
        errors.append(f"Google（{exc}）")

    try:
        translated = _translate_with_mymemory(text, source_guess, target)
        return TranslationResult(
            text=translated,
            source=source_guess,
            target=target,
            provider="MyMemory",
            fallback=True,
        )
    except Exception as exc:
        errors.append(f"MyMemory（{exc}）")

    raise TranslationError(
        "翻译失败，请检查网络连接后重试。\n" + "；".join(errors)
    )


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


def _read_json(url: str, data: bytes | None = None) -> object:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = (
            "application/x-www-form-urlencoded; charset=UTF-8"
        )
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            body = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raise TranslationError(f"HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise TranslationError(f"网络错误：{exc.reason}") from exc
    except TimeoutError as exc:
        raise TranslationError("请求超时") from exc

    try:
        return json.loads(body)
    except ValueError as exc:
        raise TranslationError("接口返回了非 JSON 数据") from exc


def _translate_with_google(text: str, source: str, target: str) -> tuple[str, str]:
    parts: list[str] = []
    detected = source
    for chunk in _chunk_text(text, GOOGLE_CHUNK_CHARS):
        translated, chunk_detected = _google_chunk(chunk, source, target)
        if detected == "auto" and chunk_detected not in ("", "auto"):
            detected = chunk_detected
        parts.append(translated)
    return _join_parts(parts), detected


def _google_chunk(text: str, source: str, target: str) -> tuple[str, str]:
    params = {
        "client": "gtx",
        "sl": source,
        "tl": target,
        "dt": "t",
        "q": text,
    }
    payload = _read_json(
        GOOGLE_ENDPOINT, urllib.parse.urlencode(params).encode("utf-8")
    )

    if not isinstance(payload, list) or not payload or not isinstance(payload[0], list):
        raise TranslationError("Google 返回格式异常")

    translated = "".join(
        segment[0] or ""
        for segment in payload[0]
        if isinstance(segment, list) and segment
    )
    detected = (
        payload[2]
        if len(payload) > 2 and isinstance(payload[2], str)
        else "auto"
    )

    if text.strip() and not translated.strip():
        raise TranslationError("Google 返回空结果")
    return translated, detected


def _translate_with_mymemory(text: str, source: str, target: str) -> str:
    limit = (
        MYMEMORY_CJK_CHUNK_CHARS if has_chinese(text) else MYMEMORY_CHUNK_CHARS
    )
    return _join_parts(
        _mymemory_chunk(chunk, source, target)
        for chunk in _chunk_text(text, limit)
    )


def _mymemory_chunk(text: str, source: str, target: str) -> str:
    params = {"q": text, "langpair": f"{source}|{target}"}
    url = MYMEMORY_ENDPOINT + "?" + urllib.parse.urlencode(params)
    payload = _read_json(url)

    if not isinstance(payload, dict):
        raise TranslationError("MyMemory 返回格式异常")

    status = payload.get("responseStatus")
    if status not in (None, 200, "200"):
        detail = payload.get("responseDetails") or f"状态码 {status}"
        raise TranslationError(str(detail))

    response_data = payload.get("responseData")
    if not isinstance(response_data, dict):
        raise TranslationError("MyMemory 返回格式异常")
    translated = response_data.get("translatedText")
    if not isinstance(translated, str) or not translated.strip():
        raise TranslationError("MyMemory 返回空结果")
    if "QUERY LENGTH LIMIT" in translated.upper():
        raise TranslationError("超出 MyMemory 单次长度限制")

    return html.unescape(translated)


# ---------------------------------------------------------------------------
# Chunking helpers (public endpoints cap request sizes)
# ---------------------------------------------------------------------------


def _chunk_text(text: str, limit: int) -> list[str]:
    """Split text into <= limit sized chunks, preferring sentence breaks."""
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        if current and len(current) + len(line) > limit:
            chunks.append(current)
            current = ""
        while len(line) > limit:
            cut = _find_break(line, limit)
            chunks.append(line[:cut])
            line = line[cut:]
        current += line
    if current:
        chunks.append(current)
    return chunks or [text]


def _find_break(text: str, limit: int) -> int:
    window = text[:limit]
    for index in range(len(window) - 1, 0, -1):
        if window[index] in _SENTENCE_ENDINGS:
            end = index + 1
            while end < len(text) and text[end] in "”’\"')]  ":
                end += 1
            return end
    space = window.rfind(" ")
    if space > limit // 2:
        return space + 1
    return limit


def _join_parts(parts) -> str:
    """Join translated chunks without gluing together Latin words."""
    result = ""
    for part in parts:
        if not part:
            continue
        if not result:
            result = part
            continue
        if result[-1].isspace() or part[0].isspace():
            result += part
        elif result[-1].isascii() and part[0].isascii():
            result += " " + part
        else:
            result += part
    return result
