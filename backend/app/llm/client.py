"""LLM 客户端封装：统一超时、思考开关与 JSON 解析。

注意 deepseek-flash 的两个特性（M0 实测）：
1. 默认开启思考，reasoning token 计入 max_tokens —— 预算不足会返回空 content；
2. 因此默认 max_tokens 给到 1500，并对空内容明确报错而不是当作"无答案"。
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass

from openai import OpenAI

from ..core.settings import Settings, get_settings


class LLMError(RuntimeError):
    """LLM 调用失败。"""


class LLMFormatError(LLMError):
    """返回内容不是合法 JSON。"""


@dataclass
class LLMResponse:
    content: str
    model: str
    elapsed_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int | None = None
    reasoning: str | None = None


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def extract_json(text: str) -> dict:
    """从模型输出里取第一个 JSON 对象，容忍代码块与前后废话。"""
    cleaned = _FENCE_RE.sub("", text.strip())
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise LLMFormatError(f"未找到 JSON 对象: {text[:200]!r}")
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMFormatError(f"JSON 解析失败: {exc}; 原文: {cleaned[:200]!r}") from exc


class LLMClient:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        model: str | None = None,
        base_url: str | None = None,
        thinking: bool | None = None,
        reasoning_effort: str | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        if not self.settings.llm_configured:
            raise LLMError("LLM_API_KEY 未配置")
        self.model = model or self.settings.llm_model
        self.thinking = self.settings.llm_thinking if thinking is None else thinking
        self.reasoning_effort = reasoning_effort or self.settings.llm_reasoning_effort
        self._client = OpenAI(
            api_key=self.settings.llm_api_key.get_secret_value(),
            base_url=base_url or self.settings.llm_base_url,
            timeout=self.settings.llm_timeout,
        )

    def complete(
        self,
        messages: list[dict],
        max_tokens: int = 3000,
        thinking: bool | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        use_thinking = self.thinking if thinking is None else thinking
        extra_body: dict = {"thinking": {"type": "enabled" if use_thinking else "disabled"}}
        if use_thinking:
            extra_body["reasoning_effort"] = self.reasoning_effort

        start = time.perf_counter()
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                extra_body=extra_body,
            )
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"调用失败: {type(exc).__name__}: {exc}") from exc
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        message = resp.choices[0].message
        content = (message.content or "").strip()
        reasoning = getattr(message, "reasoning_content", None) or (message.model_extra or {}).get(
            "reasoning_content"
        )
        usage = resp.usage
        details = getattr(usage, "completion_tokens_details", None)

        result = LLMResponse(
            content=content,
            model=resp.model,
            elapsed_ms=elapsed_ms,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            reasoning_tokens=getattr(details, "reasoning_tokens", None) if details else None,
            reasoning=reasoning,
        )
        if not content:
            raise LLMError(
                f"模型返回空内容（completion={result.completion_tokens}, "
                f"reasoning={result.reasoning_tokens}），通常是 max_tokens 被思考占满"
            )
        return result

    def complete_json(
        self,
        messages: list[dict],
        max_tokens: int = 3000,
        thinking: bool | None = None,
    ) -> tuple[dict, LLMResponse]:
        response = self.complete(messages, max_tokens=max_tokens, thinking=thinking)
        return extract_json(response.content), response
