"""Ollama implementation of Trinity's local model provider."""
import json
from typing import Any, Iterator, Optional, Sequence
import requests
from .base import ChatMessage, ModelInfo, LocalModelNotFoundError, LocalModelUnavailableError

class OllamaProvider:
    name = "ollama"
    def __init__(self, base_url="http://127.0.0.1:11434", timeout=60):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def health(self):
        try:
            return requests.get(f"{self.base_url}/api/tags", timeout=3).ok
        except requests.RequestException:
            return False

    def available_models(self):
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=self.timeout)
            r.raise_for_status()
            return [ModelInfo(m["name"], self.name) for m in r.json().get("models", []) if m.get("name")]
        except requests.RequestException as exc:
            raise LocalModelUnavailableError(f"Ollama unavailable at {self.base_url}: {exc}") from exc

    def _ensure_model(self, model):
        installed = {m.name for m in self.available_models()}
        # Ollama may report an explicit :latest suffix.
        if model not in installed and f"{model}:latest" not in installed:
            raise LocalModelNotFoundError(f"Local model '{model}' is not installed")

    @staticmethod
    def _messages(messages):
        return [{"role": m.role, "content": m.content} for m in messages]

    def chat(self, messages: Sequence[ChatMessage], model: Optional[str] = None, **kwargs: Any):
        if not model: raise LocalModelNotFoundError("A local model must be specified")
        self._ensure_model(model)
        try:
            r = requests.post(f"{self.base_url}/api/chat", json={"model": model, "messages": self._messages(messages), "stream": False, **kwargs}, timeout=self.timeout)
            r.raise_for_status()
            return r.json().get("message", {}).get("content", "")
        except requests.RequestException as exc:
            raise LocalModelUnavailableError(f"Ollama chat failed: {exc}") from exc

    def stream_chat(self, messages: Sequence[ChatMessage], model: Optional[str] = None, **kwargs: Any) -> Iterator[str]:
        if not model: raise LocalModelNotFoundError("A local model must be specified")
        self._ensure_model(model)
        try:
            with requests.post(f"{self.base_url}/api/chat", json={"model": model, "messages": self._messages(messages), "stream": True, **kwargs}, timeout=self.timeout, stream=True) as r:
                r.raise_for_status()
                for line in r.iter_lines(decode_unicode=True):
                    if not line: continue
                    chunk = json.loads(line)
                    text = chunk.get("message", {}).get("content", "")
                    if text: yield text
                    if chunk.get("done"): break
        except requests.RequestException as exc:
            raise LocalModelUnavailableError(f"Ollama stream failed: {exc}") from exc
