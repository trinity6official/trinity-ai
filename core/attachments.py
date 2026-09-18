"""Attachment ingestion for Trinity.

Keeps remote-file transport, parsing and attachment-specific prompting outside
the main Trinity composition root. The service receives a file-loader callback
so it is independent of any specific chat or transport interface.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Callable


FileLoader = Callable[[str], tuple[str, bytes]]

from core.models import ChatMessage


class AttachmentService:
    """Process images and documents for a Trinity host."""

    TEXT_EXTENSIONS = {
        ".txt", ".md", ".csv", ".tsv", ".log", ".json", ".yaml", ".yml",
        ".toml", ".ini", ".cfg", ".env", ".xml", ".html", ".htm",
        ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp",
        ".h", ".cs", ".go", ".rb", ".rs", ".sh", ".bash", ".zsh",
        ".sql", ".r", ".swift", ".kt", ".dart", ".php", ".vue",
    }

    def __init__(
        self,
        host: Any,
        file_loader: FileLoader | None,
        vision: Any = None,
        max_document_chars: int = 12_000,
    ) -> None:
        self.host = host
        self.file_loader = file_loader
        self.vision = vision
        self.max_document_chars = max_document_chars

    def _remote_file(self, file_id: str) -> tuple[str, bytes]:
        if self.file_loader is None:
            raise RuntimeError("Remote attachment transport is not configured")
        return self.file_loader(file_id)

    def handle_photo(self, photos: list[dict[str, Any]], caption: str = "") -> None:
        vision = self.vision
        if vision is None or not vision.available():
            self.host.respond(
                "I can see you sent a photo, but local vision is not configured right now. "
                "Install a multimodal model in Ollama and set TRINITY_VISION_MODEL."
            )
            return

        question = caption or (
            "David sent you this image. Describe what is visibly present, extract useful "
            "details, and be explicit about uncertainty. Never invent details that are not visible."
        )
        try:
            if not photos:
                raise ValueError("No photo metadata received")
            largest = max(photos, key=lambda p: p.get("file_size", 0))
            file_path, image_bytes = self._remote_file(largest["file_id"])
            media_type = self._image_media_type(file_path)
            self.host.respond("Looking at your image locally...")
            reply = vision.analyze(image_bytes, question, media_type)
            self.host.respond(reply)
            self.host.conversation._save_to_history(f"[photo] {question[:300]}", reply)
        except Exception as exc:
            print(f"Vision error: {exc}")
            message = (
                f"I had trouble processing that image locally: {str(exc)}\n"
                "You can describe what it shows and I will help."
            )
            self.host.respond(message)
            self.host.conversation._save_to_history(f"[photo] {question[:300]}", message)

    @staticmethod
    def _image_media_type(path: str) -> str:
        suffix = Path(path).suffix.lower()
        return {
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }.get(suffix, "image/jpeg")

    def handle_document(self, doc: dict[str, Any], caption: str = "") -> None:
        fname = doc.get("file_name", "document")
        mime = doc.get("mime_type", "")
        file_id = doc["file_id"]
        try:
            _remote_path, raw = self._remote_file(file_id)
            self.host.respond(f"Reading {fname}...")
            text = self._extract_text(fname, mime, raw)
            if text is None:
                self.host.respond(
                    f"I received '{fname}' but I can't read that file type yet.\n"
                    "I can read: text files, code, CSV, JSON, YAML, PDF, and Word docs."
                )
                return
            if not text.strip():
                self.host.respond(
                    f"I opened '{fname}' but couldn't find any readable text inside."
                )
                return

            truncated = len(text) > self.max_document_chars
            if truncated:
                text = text[: self.max_document_chars]

            question = caption or (
                f"David sent you a file called '{fname}'. Read it carefully and give a thorough "
                "summary. Note key points, numbers, decisions, or action items."
            )
            prompt = (
                f"David sent a file: '{fname}'\n\n--- FILE CONTENT ---\n{text}\n--- END ---\n"
                + (f"(Note: file was truncated — showing first {self.max_document_chars:,} chars)\n" if truncated else "")
                + f"\nDavid's question / instruction: {question}"
            )
            reply = self._ask_document_llm(question, prompt)
            self.host.respond(reply)
            self.host.conversation._save_to_history(f"[document: {fname}] {question[:200]}", reply)
        except ImportError as exc:
            dependency = "pypdf" if "pypdf" in str(exc) else "python-docx"
            self.host.respond(f"I need the `{dependency}` library to read '{fname}'.")
        except Exception as exc:
            print(f"Document read error: {exc}")
            message = f"I had trouble reading '{fname}': {str(exc)[:200]}"
            self.host.respond(message)
            self.host.conversation._save_to_history(f"[document: {fname}]", message)

    def _extract_text(self, fname: str, mime: str, raw: bytes) -> str | None:
        lower = fname.lower()
        suffix = Path(lower).suffix
        if suffix == ".pdf" or mime == "application/pdf":
            try:
                import pypdf
            except ImportError as exc:
                raise ImportError("pypdf") from exc
            reader = pypdf.PdfReader(io.BytesIO(raw))
            return "\n\n".join(page.extract_text() or "" for page in reader.pages)

        if suffix == ".docx" or "wordprocessingml" in mime:
            try:
                import docx
            except ImportError as exc:
                raise ImportError("python-docx") from exc
            document = docx.Document(io.BytesIO(raw))
            return "\n".join(paragraph.text for paragraph in document.paragraphs)

        if suffix in self.TEXT_EXTENSIONS or mime.startswith("text/"):
            for encoding in ("utf-8", "latin-1", "cp1252"):
                try:
                    return raw.decode(encoding)
                except UnicodeDecodeError:
                    continue
            return ""
        return None

    def _ask_document_llm(self, question: str, prompt: str) -> str:
        llm = self.host.get_llm_for_task(question)
        if not llm:
            return "AI brain is not available right now."
        messages = [
            ChatMessage("system", (
                "You are Trinity, David's AI company manager. David has sent you a file to read "
                "and analyze. Be thorough and specific. Extract actionable insights. If it is "
                "code, explain what it does and flag issues. If it is data, summarize key numbers. "
                "If it is a document, extract the main points, decisions and tasks."
            ))
        ]
        for turn in self.host._conversation_history[-6:]:
            messages.append(
                ChatMessage("user", turn["content"])
                if turn["role"] == "user"
                else ChatMessage("assistant", turn["content"])
            )
        messages.append(ChatMessage("user", prompt))
        response = self.host._invoke_with_failover(messages, preferred_llm=llm)
        return response.content
