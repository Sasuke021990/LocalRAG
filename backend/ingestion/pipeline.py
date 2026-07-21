"""
Document Ingestion Pipeline — LocalRAG v2.0
============================================
Processes documents through the full RAG pipeline:
  parse → chunk → embed → store (Redis + JSON backup) → delete original

Key features:
- Pool-aware storage: <DATA_DIR>/<user_id>/<pool>/<filename>.json
- Dual storage: Redis (fast retrieval) + JSON backup (durability / portability)
- Auto re-index on startup: reads all JSON backups and restores to Redis
- Original file deleted after successful ingestion
- Supports: PDF, DOCX, TXT, CSV, MD, HTML, JSON, XML
"""

import os
import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pypdf as PyPDF2
import redis
from docx import Document as DocxDocument
from sentence_transformers import SentenceTransformer

from retrieval import vector_index
from utils.config import config
from utils.device import get_best_device

ALLOWED_EXTENSIONS = {
    ".pdf", ".txt", ".docx", ".csv",
    ".md", ".html", ".htm", ".json",
    ".xml", ".log",
}

logger = logging.getLogger(__name__)


class DocumentIngestionPipeline:
    """
    Full RAG ingestion pipeline with knowledge-pool support and dual storage.

    Storage strategy
    ----------------
    After processing a document:
      1. Embeddings + chunks are written to Redis under key
         ``document:<user_id>:<pool>:<filename>``
      2. A portable JSON backup is saved at
         ``<DATA_DIR>/<user_id>/<pool>/<stem>.json``
      3. The original uploaded file is deleted

    On container restart the ``reindex_from_disk`` method scans every JSON
    backup and re-populates Redis, so no data is ever lost.
    """

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.embedding_model_name = embedding_model

        # Redis connection
        try:
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                decode_responses=True,
            )
            self.redis_client.ping()
            logger.info(f"Connected to Redis at {redis_host}:{redis_port}")
            vector_index.ensure_index(self.redis_client)
        except Exception as exc:
            logger.error(f"Failed to connect to Redis: {exc}")
            raise

        # Sentence-transformer model
        try:
            device = get_best_device()
            self.model = SentenceTransformer(embedding_model, device=device)
            logger.info(f"Loaded embedding model: {embedding_model} on {device}")
        except Exception as exc:
            logger.error(f"Failed to load embedding model '{embedding_model}': {exc}")
            raise

    # ─────────────────────────────────────────────────────────────────────────
    # Public helpers
    # ─────────────────────────────────────────────────────────────────────────

    def validate_file_type(self, file_path: str) -> bool:
        """Return True if the file extension is in the allowed list."""
        return Path(file_path).suffix.lower() in ALLOWED_EXTENSIONS

    def reindex_from_disk(self, data_dir: str = "/app/data") -> int:
        """
        Scan every ``*.json`` backup under *data_dir* (now laid out as
        ``<data_dir>/<user_id>/<pool>/<stem>.json``) and restore any
        documents missing from Redis. Called automatically on app startup.

        This is also the migration path for the RediSearch chunk vector
        index: every backup's chunks are re-written to their ``chunk:*``
        HASHes (via ``vector_index.index_chunk``) on every call, regardless
        of whether the ``document:*`` blob already existed. That write is
        idempotent (HSET), so upgrading an existing deployment to real
        vector search only requires one backend restart to backfill the
        index for documents ingested before this feature existed.

        Returns the number of documents that were re-indexed.
        """
        data_path = Path(data_dir)
        if not data_path.exists():
            logger.warning(f"Data directory '{data_dir}' does not exist — skipping reindex")
            return 0

        count = 0
        for user_dir in data_path.iterdir():
            if not user_dir.is_dir():
                continue
            user_id = user_dir.name
            for pool_dir in user_dir.iterdir():
                if not pool_dir.is_dir():
                    continue
                pool = pool_dir.name
                for json_file in pool_dir.glob("*.json"):
                    try:
                        with open(json_file, "r", encoding="utf-8") as fh:
                            data = json.load(fh)

                        file_name = data.get("file_name", json_file.stem)
                        doc_key = f"document:{user_id}:{pool}:{file_name}"

                        if not self.redis_client.exists(doc_key):
                            self.redis_client.set(doc_key, json.dumps(data))
                            count += 1
                            logger.info(f"Re-indexed: {doc_key}")

                        chunks = data.get("chunks", [])
                        embeddings = data.get("embeddings", [])
                        for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
                            vector_index.index_chunk(
                                self.redis_client, user_id, pool, file_name, i, chunk_text, embedding
                            )
                    except Exception as exc:
                        logger.error(f"Error re-indexing {json_file}: {exc}")

        logger.info(f"Startup re-index complete — {count} document(s) restored from disk")
        return count

    def list_documents(self, user_id: str) -> List[Dict[str, Any]]:
        """Return metadata for every document this user has indexed in Redis."""
        try:
            keys = self.redis_client.keys(f"document:{user_id}:*")
            documents = []
            for key in keys:
                raw = self.redis_client.get(key)
                if not raw:
                    continue
                data = json.loads(raw)
                documents.append({
                    "key": key,
                    "file_name": data.get("file_name", "Unknown"),
                    "pool": data.get("pool") or data.get("category") or "General",
                    "pool_assigned": data.get("pool_assigned", True),
                    "chunk_count": data.get("chunk_count", 0),
                    "processed_at": data.get("processed_at", ""),
                    "embedding_dimension": (
                        len(data["embeddings"][0])
                        if data.get("embeddings")
                        else 0
                    ),
                })
            return documents
        except Exception as exc:
            logger.error(f"Error listing documents: {exc}")
            return []

    def delete_document(self, file_name: str, pool: str, user_id: str) -> Optional[int]:
        """
        Delete a document from Redis and remove its JSON backup from disk.
        Returns the deleted backup's byte size (for quota accounting), or
        ``None`` if the document didn't exist.
        """
        try:
            doc_key = f"document:{user_id}:{pool}:{file_name}"

            raw = self.redis_client.get(doc_key)
            if raw is None:
                return None
            chunk_count = json.loads(raw).get("chunk_count", 0)

            self.redis_client.delete(doc_key)
            vector_index.delete_chunks(self.redis_client, user_id, pool, file_name, chunk_count)
            logger.info(f"Deleted from Redis: {doc_key} ({chunk_count} chunk(s))")

            # Remove JSON backup
            stem = Path(file_name).stem
            json_path = Path(config.DATA_DIR) / user_id / pool / f"{stem}.json"
            freed_bytes = 0
            if json_path.exists():
                freed_bytes = json_path.stat().st_size
                json_path.unlink()
                logger.info(f"Deleted JSON backup: {json_path}")

            return freed_bytes
        except Exception as exc:
            logger.error(f"Error deleting document '{file_name}': {exc}")
            return None

    def move_document(
        self, user_id: str, file_name: str, from_pool: str, to_pool: str
    ) -> Optional[Dict[str, Any]]:
        """
        Move a document from one pool to another (also used to *assign* a
        doc that was uploaded without a chosen pool — pass ``to_pool ==
        from_pool`` to just confirm/keep it).

        Re-keys the Redis blob, re-indexes the chunk vectors under the new
        pool, moves the JSON disk backup, and sets ``pool_assigned=True``.
        Storage bytes are unchanged (same content, relabeled). Returns the
        updated document metadata, or ``None`` if the source doc is missing.
        """
        try:
            src_key = f"document:{user_id}:{from_pool}:{file_name}"
            raw = self.redis_client.get(src_key)
            if raw is None:
                return None

            data = json.loads(raw)
            data["pool"] = to_pool
            data["pool_assigned"] = True
            chunks = data.get("chunks", [])
            embeddings = data.get("embeddings", [])
            chunk_count = data.get("chunk_count", len(chunks))
            stem = Path(file_name).stem

            # Assign-in-place (same pool): just flip the flag, no re-keying.
            if to_pool == from_pool:
                self.redis_client.set(src_key, json.dumps(data))
                backup_path = Path(config.DATA_DIR) / user_id / from_pool / f"{stem}.json"
                if backup_path.exists():
                    backup_path.write_text(json.dumps(data), encoding="utf-8")
                return self._doc_meta(src_key, data)

            # Different pool: write new representation, then remove the old.
            dst_key = f"document:{user_id}:{to_pool}:{file_name}"
            self.redis_client.set(dst_key, json.dumps(data))
            for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
                vector_index.index_chunk(self.redis_client, user_id, to_pool, file_name, i, chunk_text, embedding)

            # Move the disk backup.
            new_dir = Path(config.DATA_DIR) / user_id / to_pool
            new_dir.mkdir(parents=True, exist_ok=True)
            (new_dir / f"{stem}.json").write_text(json.dumps(data), encoding="utf-8")
            old_backup = Path(config.DATA_DIR) / user_id / from_pool / f"{stem}.json"
            if old_backup.exists():
                old_backup.unlink()

            # Remove the old Redis blob + chunk vectors.
            self.redis_client.delete(src_key)
            vector_index.delete_chunks(self.redis_client, user_id, from_pool, file_name, chunk_count)

            logger.info(f"Moved '{file_name}' for user {user_id}: {from_pool} → {to_pool}")
            return self._doc_meta(dst_key, data)
        except Exception as exc:
            logger.error(f"Error moving document '{file_name}': {exc}")
            return None

    @staticmethod
    def _doc_meta(key: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Public metadata view of a document blob (no chunks/embeddings)."""
        return {
            "key": key,
            "file_name": data.get("file_name", "Unknown"),
            "pool": data.get("pool") or data.get("category") or "General",
            "pool_assigned": data.get("pool_assigned", True),
            "chunk_count": data.get("chunk_count", 0),
            "processed_at": data.get("processed_at", ""),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Main ingestion method
    # ─────────────────────────────────────────────────────────────────────────

    def process_document(
        self,
        file_path: str,
        user_id: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        pool: str = "General",
        pool_assigned: bool = True,
    ) -> Dict[str, Any]:
        """
        Full pipeline: validate → parse → chunk → embed → store → delete original.

        Parameters
        ----------
        file_path:        Absolute path to the uploaded file.
        user_id:          Owning user's ID — every stored key is scoped to it.
        chunk_size:       Maximum characters per chunk.
        chunk_overlap:    Characters of overlap between consecutive chunks.
        progress_callback: Optional ``(percent: int, message: str) -> None``.
        pool:             Destination knowledge pool (folder name under
                          ``<DATA_DIR>/<user_id>/``).
        pool_assigned:    False when the uploader didn't explicitly pick a
                          pool (the doc lands in the default pool but is
                          flagged so the UI can prompt for a choice).

        Returns
        -------
        Dict with processing results, including ``stored_bytes`` (the JSON
        backup's size on disk, used for quota accounting), ``pool``, and
        ``pool_assigned``.
        """
        try:
            if not self.validate_file_type(file_path):
                raise ValueError(f"File type not allowed: {Path(file_path).suffix}")

            _cb(progress_callback, 10, "File validated ✓")

            # 1. Parse
            logger.info(f"Parsing: {file_path}")
            text = self._parse_document(file_path)
            _cb(progress_callback, 30, "Document parsed ✓")

            # 2. Chunk
            chunks = self._chunk_text(text, chunk_size, chunk_overlap)
            _cb(progress_callback, 50, f"Split into {len(chunks)} chunks ✓")

            # 3. Embed
            embeddings = self._generate_embeddings(chunks)
            _cb(progress_callback, 70, "Embeddings generated ✓")

            # 4a. Store in Redis
            self._store_in_redis(file_path, chunks, embeddings, pool, user_id, pool_assigned)

            # 4b. Save JSON backup to disk (durability)
            stored_bytes = self._save_json_backup(file_path, chunks, embeddings, pool, user_id, pool_assigned)
            _cb(progress_callback, 90, "Stored in Redis + JSON backup ✓")

            # 5. Delete original uploaded file
            try:
                os.remove(file_path)
                logger.info(f"Original file deleted: {file_path}")
            except Exception as exc:
                logger.warning(f"Could not delete original file '{file_path}': {exc}")

            _cb(progress_callback, 100, "Processing complete ✓")

            return {
                "status": "success",
                "file_name": Path(file_path).name,
                "pool": pool,
                "pool_assigned": pool_assigned,
                "total_chunks": len(chunks),
                "embedding_dimension": len(embeddings[0]) if embeddings else 0,
                "stored_bytes": stored_bytes,
                "message": "Document processed and stored successfully",
            }

        except Exception as exc:
            logger.error(f"Error processing '{file_path}': {exc}")
            # Best-effort cleanup of the original file
            try:
                os.remove(file_path)
            except Exception:
                pass
            raise

    # ─────────────────────────────────────────────────────────────────────────
    # Storage helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _store_in_redis(
        self,
        file_path: str,
        chunks: list,
        embeddings: list,
        pool: str,
        user_id: str,
        pool_assigned: bool = True,
    ) -> None:
        """Write document data to Redis under ``document:<user_id>:<pool>:<filename>``."""
        file_name = Path(file_path).name
        doc_key = f"document:{user_id}:{pool}:{file_name}"
        data = {
            "file_name": file_name,
            "pool": pool,
            "pool_assigned": pool_assigned,
            "user_id": user_id,
            "chunks": chunks,
            "embeddings": embeddings,
            "chunk_count": len(chunks),
            "processed_at": datetime.now().isoformat(),
        }
        self.redis_client.set(doc_key, json.dumps(data))

        for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            vector_index.index_chunk(self.redis_client, user_id, pool, file_name, i, chunk_text, embedding)

        logger.info(f"Stored in Redis: {doc_key} ({len(chunks)} chunks, vector-indexed)")

    def _save_json_backup(
        self,
        file_path: str,
        chunks: list,
        embeddings: list,
        pool: str,
        user_id: str,
        pool_assigned: bool = True,
    ) -> int:
        """
        Write a portable JSON backup to ``<DATA_DIR>/<user_id>/<pool>/<stem>.json``.

        This file is the source of truth used by ``reindex_from_disk`` on
        container restarts, so the knowledge base survives even if the Redis
        volume is wiped. Its byte size on disk is also the canonical figure
        used for per-user storage quota accounting (see ``utils.quota``) —
        the Redis document blob and RediSearch chunk HASHes are derived
        copies of this same content, not separate storage to also count.

        Returns the backup file's size in bytes.
        """
        file_name = Path(file_path).name
        stem = Path(file_path).stem
        backup_dir = Path(config.DATA_DIR) / user_id / pool
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"{stem}.json"

        data = {
            "file_name": file_name,
            "pool": pool,
            "pool_assigned": pool_assigned,
            "user_id": user_id,
            "chunks": chunks,
            "embeddings": embeddings,
            "chunk_count": len(chunks),
            "processed_at": datetime.now().isoformat(),
        }
        with open(backup_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)

        stored_bytes = backup_path.stat().st_size
        logger.info(f"Saved JSON backup: {backup_path} ({stored_bytes} bytes)")
        return stored_bytes

    # ─────────────────────────────────────────────────────────────────────────
    # Document parsers
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_document(self, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        parsers = {
            ".pdf":  self._parse_pdf,
            ".docx": self._parse_docx,
            ".txt":  self._parse_txt,
            ".md":   self._parse_txt,
            ".log":  self._parse_txt,
            ".csv":  self._parse_csv,
            ".html": self._parse_html,
            ".htm":  self._parse_html,
            ".json": self._parse_json_file,
            ".xml":  self._parse_xml,
        }
        parser = parsers.get(ext)
        if not parser:
            raise ValueError(f"Unsupported file type: {ext}")
        return parser(file_path)

    def _parse_pdf(self, file_path: str) -> str:
        text = ""
        with open(file_path, "rb") as fh:
            reader = PyPDF2.PdfReader(fh)
            for page in reader.pages:
                text += (page.extract_text() or "") + "\n"
        return text

    def _parse_docx(self, file_path: str) -> str:
        doc = DocxDocument(file_path)
        return "\n".join(p.text for p in doc.paragraphs)

    def _parse_txt(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()

    def _parse_csv(self, file_path: str) -> str:
        lines = []
        with open(file_path, "r", encoding="utf-8") as fh:
            for row in csv.reader(fh):
                lines.append(", ".join(row))
        return "\n".join(lines)

    def _parse_html(self, file_path: str) -> str:
        from bs4 import BeautifulSoup
        with open(file_path, "r", encoding="utf-8") as fh:
            soup = BeautifulSoup(fh, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        return " ".join(soup.get_text().split())

    def _parse_json_file(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return json.dumps(data, indent=2)

    def _parse_xml(self, file_path: str) -> str:
        from xml.etree import ElementTree as ET
        tree = ET.parse(file_path)
        return "\n".join(
            elem.text for elem in tree.getroot().iter() if elem.text
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Text chunking
    # ─────────────────────────────────────────────────────────────────────────

    def _chunk_text(self, text: str, chunk_size: int, chunk_overlap: int) -> list:
        if not text or chunk_size <= 0:
            return []
        import re
        sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
        chunks, current = [], ""
        for sentence in sentences:
            if len(current) + len(sentence) + 1 > chunk_size and current:
                chunks.append(current.strip())
                current = self._get_overlap(chunks[-1], chunk_overlap)
            current = (current + " " + sentence).strip() if current else sentence
        if current.strip():
            chunks.append(current.strip())
        return chunks

    def _get_overlap(self, text: str, size: int) -> str:
        if size <= 0:
            return ""
        if len(text) <= size:
            return text
        start = max(0, len(text) - size)
        while start > 0 and text[start] != " ":
            start -= 1
        return text[start:] if start > 0 else text[-size:]

    # ─────────────────────────────────────────────────────────────────────────
    # Embeddings
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_embeddings(self, chunks: list) -> list:
        if not chunks:
            return []
        return [e.tolist() for e in self.model.encode(chunks)]


# ─── Module-level helper ──────────────────────────────────────────────────────

def _cb(callback: Optional[Callable], pct: int, msg: str) -> None:
    """Fire the progress callback if one was provided."""
    if callback:
        try:
            callback(pct, msg)
        except Exception:
            pass