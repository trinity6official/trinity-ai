# Trinity Session Memory

Completed interactions are stored locally in SQLite `conversation_turns`, separately from durable semantic memory. Search prefers SQLite FTS5 and falls back to text search.

Historical retrieval runs only for explicit prior-conversation questions. Retrieved session text is untrusted historical evidence placed in the user/evidence payload, never the system prompt. Personal knowledge, session history, and durable memory remain separate retrieval sources.
