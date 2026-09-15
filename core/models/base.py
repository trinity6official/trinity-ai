"""Provider-neutral interfaces for Trinity's local AI layer."""
from dataclasses import dataclass
from typing import Any, Iterator, Optional, Protocol, Sequence

@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str

@dataclass(frozen=True)
class ModelInfo:
    name: str
    provider: str

class LocalModelError(RuntimeError): pass
class LocalModelUnavailableError(LocalModelError): pass
class LocalModelNotFoundError(LocalModelError): pass

class LocalModelProvider(Protocol):
    name: str
    def health(self) -> bool: ...
    def available_models(self) -> Sequence[ModelInfo]: ...
    def chat(self, messages: Sequence[ChatMessage], model: Optional[str] = None, **kwargs: Any) -> str: ...
    def stream_chat(self, messages: Sequence[ChatMessage], model: Optional[str] = None, **kwargs: Any) -> Iterator[str]: ...
