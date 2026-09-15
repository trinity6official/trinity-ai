"""llama.cpp server implementation of Trinity's local model provider.

The provider targets llama-server's OpenAI-compatible HTTP API.  It is used by
Trinity's Android/Termux pre-hardware profile and can also be used on any local
machine running llama-server.
"""
from __future__ import annotations

import json
from typing import Any, Iterator, Optional, Sequence

import requests

from .base import (
    ChatMessage,
    LocalModelNotFoundError,
    LocalModelUnavailableError,
    ModelInfo,
)


class LlamaCppProvider:
    name = "llama_cpp"

    def __init__(self, base_url: str = "http://127.0.0.1:8080", timeout: int = 180):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def health(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/health", timeout=3)
            if response.ok:
                return True
            # Some llama-server builds expose only the OpenAI-compatible API.
            return requests.get(f"{self.base_url}/v1/models", timeout=3).ok
        except requests.RequestException:
            return False

    def available_models(self) -> Sequence[ModelInfo]:
        try:
            response = requests.get(f"{self.base_url}/v1/models", timeout=self.timeout)
            response.raise_for_status()
            data = response.json().get("data", [])
            return [
                ModelInfo(str(item["id"]), self.name)
                for item in data
                if isinstance(item, dict) and item.get("id")
            ]
        except (requests.RequestException, ValueError) as exc:
            raise LocalModelUnavailableError(
                f"llama.cpp server unavailable at {self.base_url}: {exc}"
            ) from exc

    @staticmethod
    def _messages(messages: Sequence[ChatMessage]) -> list[dict[str, str]]:
        return [{"role": msg.role, "content": msg.content} for msg in messages]

    def _ensure_model(self, model: str) -> None:
        installed = {item.name for item in self.available_models()}
        if installed and model not in installed:
            raise LocalModelNotFoundError(
                f"Local llama.cpp model alias '{model}' is not available; "
                f"server reports: {', '.join(sorted(installed))}"
            )

    def chat(
        self,
        messages: Sequence[ChatMessage],
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        if not model:
            raise LocalModelNotFoundError("A local model alias must be specified")
        self._ensure_model(model)
        payload = {
            "model": model,
            "messages": self._messages(messages),
            "stream": False,
            **kwargs,
        }
        try:
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            choices = response.json().get("choices", [])
            if not choices:
                return ""
            return str(choices[0].get("message", {}).get("content", ""))
        except (requests.RequestException, ValueError, IndexError) as exc:
            raise LocalModelUnavailableError(f"llama.cpp chat failed: {exc}") from exc

    def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> Iterator[str]:
        if not model:
            raise LocalModelNotFoundError("A local model alias must be specified")
        self._ensure_model(model)
        payload = {
            "model": model,
            "messages": self._messages(messages),
            "stream": True,
            **kwargs,
        }
        try:
            with requests.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=self.timeout,
                stream=True,
            ) as response:
                response.raise_for_status()
                for raw in response.iter_lines(decode_unicode=True):
                    if not raw:
                        continue
                    line = raw.strip()
                    if line.startswith("data:"):
                        line = line[5:].strip()
                    if line == "[DONE]":
                        break
                    chunk = json.loads(line)
                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    text = choices[0].get("delta", {}).get("content", "")
                    if text:
                        yield str(text)
        except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
            raise LocalModelUnavailableError(f"llama.cpp stream failed: {exc}") from exc
