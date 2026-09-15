# `core/models/` — Local Model Providers

This folder defines the provider-neutral interface between Trinity and local language-model runtimes.

- `base.py` defines common message/model types and local-model exceptions/protocols.
- `ollama.py` implements the Ollama adapter.
- `__init__.py` exports the supported provider-facing types.

`core/model_router.py` chooses task routes; this folder should only implement provider behavior. Trinity itself must not depend on Ollama-specific request shapes.

New local runtimes such as MLX or llama.cpp should be added as adapters implementing the same interface, then registered through the router/service configuration.
