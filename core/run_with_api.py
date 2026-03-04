"""
Starts Trinity brain daemon AND the voice API server in parallel.

Usage:
  python core/run_with_api.py

This is the entry point for the Mac Mini M5 (or any always-on server).
It launches:
  1. FastAPI voice server  on :8000  (background thread)
  2. Trinity Telegram bot  (main thread, blocking)

Environment variables:
  TRINITY_API_PORT   API port (default 8000)
  TRINITY_JWT_SECRET Required for production — set a long random string
  TRINITY_APP_PIN_HASH SHA-256 hex of your PIN (echo -n "1234" | sha256sum)
"""

from __future__ import annotations

import logging
import os
import threading

logger = logging.getLogger(__name__)


def _start_api() -> None:
    """Run the FastAPI voice server in a background daemon thread."""
    import uvicorn
    port = int(os.environ.get("TRINITY_API_PORT", "8000"))
    logger.info("Trinity Voice API starting on port %d", port)
    uvicorn.run(
        "core.api:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="warning",   # keep main thread logs readable
        access_log=False,
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Start API in background thread (daemon=True ensures it exits with main)
    api_thread = threading.Thread(target=_start_api, daemon=True, name="trinity-api")
    api_thread.start()
    logger.info("Voice API thread started")

    # Run Trinity in the main thread (blocking)
    from core.trinity import Trinity  # noqa: PLC0415
    Trinity()
