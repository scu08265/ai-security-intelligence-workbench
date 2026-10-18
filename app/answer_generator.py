"""Evidence-bound answer generation.

The model is never asked an open question.  It receives the question plus the
exact chunks that retrieval already selected, and has to answer *from those
chunks only*, citing the chunk id of every sentence.  The caller rejects any
answer that carries no retrievable citation and falls back to the local
extractive answer, so a model outage or a hallucinated paragraph can never
turn into an unsourced claim.

This module speaks the OpenAI-compatible chat-completions protocol, which is
what ``config.DEFAULT_MODEL_BASE_URL`` (DeepSeek) exposes.  Swapping providers
is a base_url/model change, not a code change.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable, Sequence

SYSTEM_PROMPT = (
    "你是 AI 安全情报助手。只能依据 <evidence> 中给出的原文回答，"
    "不得使用任何外部知识，不得推测证据里没有的内容。\n"
    "规则：\n"
    "1. 先用一句话直接回答问题，再补充一句必要的限定。\n"
    "2. 每个句子末尾必须标注它依据的 chunk id，格式如 [chunk-1a2b3c4d]；"
    "编号必须从下面给出的“可用引用”里原样复制，不要改写、缩写或省略。\n"
    "3. 如果证据不足以回答，只输出：证据不足，无法回答。\n"
    "4. 不要罗列证据清单，不要复述题目。"
)

MAX_EVIDENCE_CHARS = 700


class GeneratorError(RuntimeError):
    """Raised when the provider is unreachable or returns an unusable body."""


def _evidence_block(citations: Sequence[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for citation in citations:
        chunk_id = str(citation.get("chunk_id") or citation.get("document_id") or "")
        title = str(citation.get("title") or "")
        quote = " ".join(str(citation.get("quote") or "").split())[:MAX_EVIDENCE_CHARS]
        if not chunk_id or not quote:
            continue
        blocks.append(f"[{chunk_id}] {title}\n{quote}")
    return "\n\n".join(blocks)


def _chat(model_config: dict[str, Any], messages: list[dict[str, str]]) -> str:
    base_url = str(model_config.get("base_url") or "").rstrip("/")
    model = str(model_config.get("model") or "")
    key_name = str(model_config.get("api_key_env") or "")
    api_key = os.getenv(key_name, "").strip() if key_name else ""
    if not base_url or not model or not api_key:
        raise GeneratorError("模型配置不完整")
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": 400,
    }).encode()
    request = urllib.request.Request(
        base_url + "/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    timeout = float(model_config.get("timeout") or 8)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise GeneratorError(type(exc).__name__) from exc
    choices = body.get("choices") or []
    if not choices:
        raise GeneratorError("模型未返回 choices")
    content = (choices[0].get("message") or {}).get("content") or ""
    if not str(content).strip():
        raise GeneratorError("模型返回空内容")
    return str(content).strip()


def build_generator(
    model_config: dict[str, Any],
) -> Callable[[str, str, Sequence[dict[str, Any]]], str]:
    """Return a generator bound to one configured model."""
    def generate(question: str, context_text: str, citations: Sequence[dict[str, Any]]) -> str:
        evidence = _evidence_block(citations)
        if not evidence:
            return ""
        available = "\n".join(
            f"- {str(item.get('chunk_id') or item.get('document_id') or '')}"
            for item in citations
            if item.get("chunk_id") or item.get("document_id")
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"<evidence>\n{evidence}\n</evidence>\n\n"
                    f"可用引用（回答中只能出现这些编号）：\n{available}\n\n"
                    f"问题：{question}"
                ),
            },
        ]
        return _chat(model_config, messages)

    return generate
