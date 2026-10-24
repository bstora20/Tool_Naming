"""
Thin wrapper around the Anthropic API, isolating all three harnesses from
SDK details. Centralizes token accounting (research_plan.md S1.7's "total
tokens, prompt+completion, cumulative") so every harness logs cost the same
way.

The API key is never read from the environment or disk directly -- callers
must obtain it via Majk's secret-management flow and pass it into
`make_client`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import anthropic

DEFAULT_MODEL = "claude-sonnet-4-5-20250929"


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def add(self, other: "Usage") -> None:
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens


@dataclass
class LLMResult:
    text: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    stop_reason: str = ""
    usage: Usage = field(default_factory=Usage)
    raw_content: List[Any] = field(default_factory=list)


class LLMClient:
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 1024,
        base_url: Optional[str] = None,
        application_source: str = "tool_name_experiment",
        session_id: Optional[str] = None,
    ):
        default_headers = {"X-Application-Source": application_source}
        default_headers["X-Session-Id"] = session_id or str(uuid.uuid4())

        # The custom proxy expects `Authorization: Bearer <key>` rather than
        # the SDK default `x-api-key` header, so we use `auth_token=` instead
        # of `api_key=` when a custom base_url is supplied.
        client_kwargs: Dict[str, Any] = {
            "default_headers": default_headers,
        }
        if base_url:
            client_kwargs["base_url"] = base_url
            client_kwargs["auth_token"] = api_key
        else:
            client_kwargs["api_key"] = api_key

        self._client = anthropic.Anthropic(**client_kwargs)
        self.model = model
        self.max_tokens = max_tokens
        self.session_id = default_headers["X-Session-Id"]

    def call(
        self,
        system: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResult:
        kwargs: Dict[str, Any] = dict(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=messages,
        )
        if tools:
            kwargs["tools"] = tools

        resp = self._client.messages.create(**kwargs)

        text_parts = []
        tool_calls = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append({"id": block.id, "name": block.name, "input": block.input})

        return LLMResult(
            text="\n".join(text_parts),
            tool_calls=tool_calls,
            stop_reason=resp.stop_reason,
            usage=Usage(
                prompt_tokens=resp.usage.input_tokens,
                completion_tokens=resp.usage.output_tokens,
            ),
            raw_content=resp.content,
        )


def make_client(
    api_key: str,
    model: str = DEFAULT_MODEL,
    base_url: Optional[str] = None,
    application_source: str = "tool_name_experiment",
    session_id: Optional[str] = None,
) -> LLMClient:
    return LLMClient(
        api_key=api_key,
        model=model,
        base_url=base_url,
        application_source=application_source,
        session_id=session_id,
    )
