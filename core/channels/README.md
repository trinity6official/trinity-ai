# `core/channels/` — Communication Adapters

Channels connect external communication surfaces to the single local Trinity runtime.

Telegram is currently the main remote-chat adapter. It is optional and must not own reasoning, memory, model selection, scheduling, or identity.

Channel responsibilities include transport-specific polling/sending/file-download behavior. Channel-neutral attachment interpretation belongs in `core/attachments.py`, and all messages should ultimately enter the normal Trinity conversation pipeline.
