"""
LocalLLM — a thin, swappable wrapper around a local GGUF model via
llama-cpp-python.

Design notes
------------
- **Optional at runtime.** ``llama_cpp`` and the model file are only touched
  when ``LLM_ENABLED`` is true *and* the import succeeds. Any failure (library
  missing, download error, load error) flips ``enabled`` to False and the app
  degrades to returning ranked passages — it never crashes. This is why the
  library lives in ``requirements-llm.txt`` (Docker/prod only) rather than the
  base requirements the tests install.
- **One shared model for all users.** The model is stateless — it only ever
  sees the requesting user's own retrieved passages (per-user retrieval
  happens upstream), so there's no isolation reason to load more than one.
- **Generations are serialized** behind an ``asyncio.Lock``: a single llama.cpp
  context is not safe for concurrent generation. Fine at this scale; the
  interface (``generate_stream``) is deliberately tiny so a later swap to a
  dedicated inference service (Ollama/vLLM) touches only this class.
"""

import asyncio
import logging
from typing import AsyncIterator

from utils.config import config

logger = logging.getLogger(__name__)


class LocalLLM:
    def __init__(self):
        self.enabled = bool(config.LLM_ENABLED)
        self._llama = None
        self._loaded = False
        self._lock = asyncio.Lock()

    def ensure_loaded(self) -> None:
        """
        Download (once) + load the model. Blocking — call via
        ``asyncio.to_thread`` from async code. Safe to call repeatedly; on any
        failure it disables the LLM instead of raising.
        """
        if not self.enabled or self._loaded:
            return
        try:
            from huggingface_hub import hf_hub_download
            from llama_cpp import Llama

            logger.info(f"Downloading model {config.LLM_MODEL_REPO}/{config.LLM_MODEL_FILE} …")
            model_path = hf_hub_download(
                repo_id=config.LLM_MODEL_REPO,
                filename=config.LLM_MODEL_FILE,
                local_dir=config.LLM_MODELS_DIR,
            )
            self._llama = Llama(
                model_path=model_path,
                n_ctx=config.LLM_CONTEXT_SIZE,
                n_threads=(config.LLM_THREADS or None),
                verbose=False,
            )
            self._loaded = True
            logger.info("Local LLM loaded and ready")
        except Exception as exc:
            logger.error(f"LLM disabled — could not load model: {exc}")
            self.enabled = False
            self._llama = None

    @property
    def ready(self) -> bool:
        return self.enabled and self._loaded and self._llama is not None

    async def generate_stream(self, prompt: str) -> AsyncIterator[str]:
        """
        Yield generated token strings for ``prompt``. Serialized across callers.
        If the model isn't ready, yields nothing (caller handles the fallback).
        """
        if not self.ready:
            return

        async with self._lock:
            loop = asyncio.get_event_loop()
            # llama.cpp streaming is a blocking generator; pump it from a thread
            # so the event loop stays responsive, handing tokens back via a queue.
            queue: asyncio.Queue = asyncio.Queue()
            _SENTINEL = object()

            def _produce():
                try:
                    for chunk in self._llama(
                        prompt,
                        max_tokens=config.LLM_MAX_TOKENS,
                        temperature=config.LLM_TEMPERATURE,
                        stream=True,
                    ):
                        token = chunk["choices"][0]["text"]
                        if token:
                            loop.call_soon_threadsafe(queue.put_nowait, token)
                except Exception as exc:  # never let a generation error escape
                    logger.error(f"LLM generation failed: {exc}")
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, _SENTINEL)

            loop.run_in_executor(None, _produce)

            while True:
                item = await queue.get()
                if item is _SENTINEL:
                    break
                yield item


# Module-level singleton — one shared model for the whole process.
local_llm = LocalLLM()
