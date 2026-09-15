"""Provider-neutral local vision support for Trinity."""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Protocol
from urllib import error, request


class VisionProvider(Protocol):
    name: str
    def available(self) -> bool: ...
    def analyze(self, image: bytes, prompt: str, media_type: str = "image/jpeg") -> str: ...


class OllamaVisionProvider:
    """Local multimodal inference through Ollama's chat API."""

    name = "ollama-vision"

    def __init__(
        self,
        model: str,
        base_url: str = "http://127.0.0.1:11434",
        timeout: float = 120.0,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _json_request(self, path: str, payload: dict | None = None) -> dict:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}{path}",
            data=body,
            method="POST" if body is not None else "GET",
            headers={"Content-Type": "application/json"} if body is not None else {},
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError) as exc:
            raise RuntimeError(f"Local vision provider unavailable: {exc}") from exc

    def available(self) -> bool:
        if not self.model:
            return False
        try:
            models = self._json_request("/api/tags").get("models", [])
            installed = {item.get("name") for item in models}
            return self.model in installed
        except RuntimeError:
            return False

    def analyze(self, image: bytes, prompt: str, media_type: str = "image/jpeg") -> str:
        if not self.model:
            raise RuntimeError("No local vision model configured")
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [base64.b64encode(image).decode("ascii")],
                }
            ],
        }
        data = self._json_request("/api/chat", payload)
        return data.get("message", {}).get("content", "")


@dataclass
class LocalVisionService:
    provider: VisionProvider | None = None

    @classmethod
    def from_environment(cls) -> "LocalVisionService":
        model = os.getenv("TRINITY_VISION_MODEL", "").strip()
        if not model:
            return cls(None)
        return cls(
            OllamaVisionProvider(
                model=model,
                base_url=os.getenv("LOCAL_LLM_URL", "http://127.0.0.1:11434"),
            )
        )

    def available(self) -> bool:
        return bool(self.provider and self.provider.available())

    def analyze(self, image: bytes, prompt: str, media_type: str = "image/jpeg") -> str:
        if self.provider is None:
            raise RuntimeError(
                "Local vision is not configured. Set TRINITY_VISION_MODEL to an installed multimodal model."
            )
        return self.provider.analyze(image, prompt, media_type)
