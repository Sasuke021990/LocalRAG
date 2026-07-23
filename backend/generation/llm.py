"""
LLM backends — a tiny, swappable interface so answer generation can run either
in-process or against a dedicated inference server.

Two backends, chosen by ``LLM_BACKEND``:

- ``embedded`` (``EmbeddedLLM``): a single in-process llama.cpp model, one
  generation at a time behind an ``asyncio.Lock``. Simple; fine for a homelab
  or a handful of users. Doesn't scale — every concurrent user queues, and
  each backend worker would need its own copy of the model.

- ``openai`` (``OpenAICompatibleLLM``): streams from an external
  OpenAI-compatible server (Ollama / vLLM / TGI / ``llama.cpp --server``) that
  **batches concurrent requests on a GPU**. No in-process model and no lock, so
  many users generate at once and the FastAPI backend stays stateless — you can
  run several workers/replicas, all pointing at the shared inference server.
  This is the horizontal-scaling path.

Both expose the same ``generate_stream(system, user) -> AsyncIterator[str]`` /
``ready`` / ``ensure_loaded`` interface, so ``pipeline.py`` never knows which is
in use. All errors degrade to "no tokens" (the pipeline then falls back to
ranked passages) — generation never crashes a request.
"""

import asyncio
import json
import logging
import threading
from typing import AsyncIterator, List, Optional

import requests

from generation import grounding
from utils.config import config

logger = logging.getLogger(__name__)


class BaseLLM:
    enabled = False

    def ensure_loaded(self) -> None:
        return

    @property
    def ready(self) -> bool:
        return False

    async def generate_stream(self, system: str, user: str, history: Optional[List[dict]] = None) -> AsyncIterator[str]:
        return
        yield  # pragma: no cover — makes this an async generator


class EmbeddedLLM(BaseLLM):
    """In-process llama.cpp. One generation at a time (llama contexts aren't
    concurrency-safe). Library + weights are optional (``requirements-llm.txt``)
    and loaded lazily; any failure disables the LLM rather than crashing."""

    def __init__(self):
        self.enabled = bool(config.LLM_ENABLED)
        self._llama = None
        self._loaded = False
        self._lock = asyncio.Lock()

    def ensure_loaded(self) -> None:
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
            logger.info("Embedded LLM loaded and ready")
        except Exception as exc:
            logger.error(f"Embedded LLM disabled — could not load model: {exc}")
            self.enabled = False
            self._llama = None

    @property
    def ready(self) -> bool:
        return self.enabled and self._loaded and self._llama is not None

    async def generate_stream(self, system: str, user: str, history: Optional[List[dict]] = None) -> AsyncIterator[str]:
        if not self.ready:
            return
        prompt = grounding.format_chat_prompt(system, user, history)
        async with self._lock:
            loop = asyncio.get_event_loop()
            queue: asyncio.Queue = asyncio.Queue()
            _SENTINEL = object()
            # Set when the consumer stops listening (client disconnected —
            # see main.py's query_stream). _produce() runs in a plain thread
            # via run_in_executor, so it has no idea an asyncio task got
            # cancelled; without this it would keep pulling tokens from
            # llama.cpp — burning generation time under the shared lock —
            # for an answer nobody will ever receive.
            cancel_event = threading.Event()

            def _produce():
                try:
                    for chunk in self._llama(
                        prompt,
                        max_tokens=config.LLM_MAX_TOKENS,
                        temperature=config.LLM_TEMPERATURE,
                        stream=True,
                    ):
                        if cancel_event.is_set():
                            break
                        token = chunk["choices"][0]["text"]
                        if token:
                            loop.call_soon_threadsafe(queue.put_nowait, token)
                except Exception as exc:
                    if not cancel_event.is_set():
                        logger.error(f"Embedded generation failed: {exc}")
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, _SENTINEL)

            loop.run_in_executor(None, _produce)
            try:
                while True:
                    item = await queue.get()
                    if item is _SENTINEL:
                        break
                    yield item
            finally:
                # Reached on normal completion (harmless no-op — _produce
                # already finished) and on early teardown via GeneratorExit
                # when the caller stops iterating (client disconnect).
                cancel_event.set()


class OpenAICompatibleLLM(BaseLLM):
    """Streams from an external OpenAI-compatible ``/chat/completions`` server.
    Concurrency is delegated to that server (which batches); this process only
    caps how many streams it opens at once via a semaphore."""

    def __init__(self):
        self.enabled = bool(config.LLM_ENABLED)
        self._sem = (
            asyncio.Semaphore(config.LLM_MAX_CONCURRENCY)
            if config.LLM_MAX_CONCURRENCY and config.LLM_MAX_CONCURRENCY > 0
            else None
        )

    def ensure_loaded(self) -> None:
        # Nothing to download/load — the model lives in the inference server.
        if self.enabled:
            logger.info(f"Using OpenAI-compatible LLM backend at {config.LLM_API_BASE} (model={config.LLM_MODEL})")

    @property
    def ready(self) -> bool:
        # Assume the server is reachable; a failed stream degrades to fallback.
        return self.enabled

    async def _acquire(self):
        if self._sem is not None:
            await self._sem.acquire()

    def _release(self):
        if self._sem is not None:
            self._sem.release()

    async def generate_stream(self, system: str, user: str, history: Optional[List[dict]] = None) -> AsyncIterator[str]:
        if not self.ready:
            return

        payload = {
            "model": config.LLM_MODEL,
            "messages": grounding.chat_messages(system, user, history),
            "temperature": config.LLM_TEMPERATURE,
            "max_tokens": config.LLM_MAX_TOKENS,
            "stream": True,
        }
        headers = {"Content-Type": "application/json"}
        if config.LLM_API_KEY:
            headers["Authorization"] = f"Bearer {config.LLM_API_KEY}"
        url = config.LLM_API_BASE.rstrip("/") + "/chat/completions"

        await self._acquire()
        try:
            loop = asyncio.get_event_loop()
            queue: asyncio.Queue = asyncio.Queue()
            _SENTINEL = object()
            # Set when the consumer stops listening (client disconnected —
            # see main.py's query_stream). _produce() runs in a plain thread
            # via run_in_executor and is doing a *blocking* HTTP read loop
            # against the inference server; it has no idea an asyncio task
            # got cancelled. Without this, the server would keep generating
            # (and this thread would keep pulling tokens) for an answer
            # nobody will ever receive.
            cancel_event = threading.Event()

            def _produce():
                resp = None
                try:
                    resp = requests.post(url, json=payload, headers=headers, stream=True, timeout=120)
                    resp.raise_for_status()
                    # Inference servers stream UTF-8, but `requests` defaults a
                    # text/event-stream response with no explicit charset to
                    # Latin-1 (RFC 2616) — which corrupts any non-ASCII token
                    # (em dashes, curly quotes, emoji) into mojibake. Pin UTF-8
                    # so decode_unicode below decodes correctly.
                    resp.encoding = "utf-8"
                    for raw in resp.iter_lines(decode_unicode=True):
                        if cancel_event.is_set():
                            break
                        if not raw or not raw.startswith("data:"):
                            continue
                        data = raw[len("data:"):].strip()
                        if data == "[DONE]":
                            break
                        try:
                            delta = json.loads(data)["choices"][0].get("delta", {})
                            token = delta.get("content")
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
                        if token:
                            loop.call_soon_threadsafe(queue.put_nowait, token)
                except Exception as exc:
                    if not cancel_event.is_set():
                        logger.error(f"Inference-server generation failed: {exc}")
                finally:
                    if resp is not None:
                        # Actually closes the connection to the inference
                        # server -- the only thing that tells *it* to stop
                        # generating too, rather than just us stopping reading.
                        resp.close()
                    loop.call_soon_threadsafe(queue.put_nowait, _SENTINEL)

            loop.run_in_executor(None, _produce)
            try:
                while True:
                    item = await queue.get()
                    if item is _SENTINEL:
                        break
                    yield item
            finally:
                # Reached on normal completion (harmless no-op — _produce
                # already finished) and on early teardown via GeneratorExit
                # when the caller stops iterating (client disconnect).
                cancel_event.set()
        finally:
            self._release()


def get_llm() -> BaseLLM:
    """Pick the backend from config (``embedded`` by default)."""
    if config.LLM_BACKEND.strip().lower() == "openai":
        return OpenAICompatibleLLM()
    return EmbeddedLLM()


# Module-level singleton used by the app.
llm = get_llm()
