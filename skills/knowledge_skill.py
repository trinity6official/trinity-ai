"""Personal knowledge skill backed by Trinity's local KnowledgeIndex."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from core.knowledge_index import KnowledgeIndex


class KnowledgeSkill:
    name = "knowledge"
    description = (
        "Index approved local folders/files and search personal knowledge with source references"
    )

    def __init__(self, db_path: str | Path | None = None):
        configured = db_path or os.environ.get(
            "TRINITY_KNOWLEDGE_DB", "memory/knowledge_index.db"
        )
        self.index = KnowledgeIndex(configured)

    def get_tools(self):
        return [
            {
                "name": "index_knowledge_path",
                "description": (
                    "Add a local file/folder as an approved personal-knowledge root and index it"
                ),
                "params": ["path", "recursive"],
                "needs_approval": True,
            },
            {
                "name": "refresh_knowledge_index",
                "description": "Incrementally refresh all previously approved knowledge roots",
                "params": [],
                "needs_approval": False,
            },
            {
                "name": "search_knowledge",
                "description": "Search indexed local knowledge and return source/line references",
                "params": ["query", "limit"],
                "needs_approval": False,
            },
            {
                "name": "read_knowledge_source",
                "description": "Read a line range from an already indexed knowledge source",
                "params": ["source_path", "start_line", "end_line"],
                "needs_approval": False,
            },
            {
                "name": "list_knowledge_sources",
                "description": "List files currently present in the personal knowledge index",
                "params": ["limit"],
                "needs_approval": False,
            },
            {
                "name": "get_knowledge_status",
                "description": "Get local personal-knowledge index statistics",
                "params": [],
                "needs_approval": False,
            },
            {
                "name": "remove_knowledge_root",
                "description": (
                    "Remove an approved knowledge root and its indexed copies; never deletes originals"
                ),
                "params": ["path", "remove_documents"],
                "needs_approval": True,
            },
        ]

    def execute(self, tool_name: str, params: dict[str, Any] | None = None):
        params = params or {}
        tools = {
            "index_knowledge_path": self.index_knowledge_path,
            "refresh_knowledge_index": self.refresh_knowledge_index,
            "search_knowledge": self.search_knowledge,
            "read_knowledge_source": self.read_knowledge_source,
            "list_knowledge_sources": self.list_knowledge_sources,
            "get_knowledge_status": self.get_knowledge_status,
            "remove_knowledge_root": self.remove_knowledge_root,
        }
        tool = tools.get(tool_name)
        if tool is None:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
        try:
            return tool(**params)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def index_knowledge_path(self, path: str, recursive: bool = True):
        summary = self.index.index_path(path, recursive=bool(recursive))
        return {"success": True, **summary}

    def refresh_knowledge_index(self):
        return {"success": True, **self.index.refresh()}

    def search_knowledge(self, query: str, limit: int = 5):
        hits = self.index.search(query, limit=max(1, min(int(limit), 20)))
        return {
            "success": True,
            "query": query,
            "results": [hit.to_dict() for hit in hits],
        }

    def read_knowledge_source(
        self,
        source_path: str,
        start_line: int = 1,
        end_line: int | None = None,
    ):
        return {
            "success": True,
            **self.index.read_source(
                source_path,
                start_line=int(start_line),
                end_line=None if end_line is None else int(end_line),
            ),
        }

    def list_knowledge_sources(self, limit: int = 100):
        return {
            "success": True,
            "sources": self.index.list_sources(limit=max(1, min(int(limit), 500))),
        }

    def get_knowledge_status(self):
        return {"success": True, **self.index.status()}

    def remove_knowledge_root(
        self,
        path: str,
        remove_documents: bool = True,
    ):
        return {
            "success": True,
            **self.index.remove_root(
                path,
                remove_documents=bool(remove_documents),
            ),
        }
