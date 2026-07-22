"""
Configuration settings for the Local RAG Application
"""

import os
from typing import Optional

class Config:
    """
    Configuration class for the Local RAG application.
    All configuration values can be overridden by environment variables.
    """
    
    # === Redis Configuration ===
    REDIS_HOST: str = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT: int = int(os.getenv('REDIS_PORT', 6379))
    REDIS_DB: int = int(os.getenv('REDIS_DB', 0))
    REDIS_PASSWORD: Optional[str] = os.getenv('REDIS_PASSWORD', None)
    
    # === Application Configuration ===
    APP_HOST: str = os.getenv('APP_HOST', '0.0.0.0')
    APP_PORT: int = int(os.getenv('APP_PORT', 8000))
    DEBUG: bool = os.getenv('DEBUG', 'False').lower() == 'true'
    
    # === Document Processing Configuration ===
    CHUNK_SIZE: int = int(os.getenv('CHUNK_SIZE', 512))
    CHUNK_OVERLAP: int = int(os.getenv('CHUNK_OVERLAP', 50))
    
    # === Model Configuration ===
    EMBEDDING_MODEL_NAME: str = os.getenv('EMBEDDING_MODEL_NAME', 'all-MiniLM-L6-v2')
    CROSS_ENCODER_MODEL_NAME: str = os.getenv('CROSS_ENCODER_MODEL_NAME', 'cross-encoder/ms-marco-MiniLM-L-6-v2')
    
    # === File Storage Configuration ===
    DOCUMENTS_DIR: str = os.getenv('DOCUMENTS_DIR', './documents')
    PROCESSED_DIR: str = os.getenv('PROCESSED_DIR', './processed')
    # Base directory for per-user document backups + uploads. Defaults to the
    # container mount (/app/data); overridable via env so it can point at a
    # writable temp dir in test/CI environments that aren't running as root.
    DATA_DIR: str = os.getenv('DATA_DIR', '/app/data')
    
    # === Cache Configuration ===
    CACHE_TTL_SECONDS: int = int(os.getenv('CACHE_TTL_SECONDS', 3600))
    SEMANTIC_CACHE_SIMILARITY_THRESHOLD: float = float(
        os.getenv('SEMANTIC_CACHE_SIMILARITY_THRESHOLD', 0.92)
    )

    # === API Configuration ===
    MAX_FILE_SIZE_MB: int = int(os.getenv('MAX_FILE_SIZE_MB', 50))

    # === ROCm Configuration ===
    USE_ROCM: bool = os.getenv('USE_ROCM', 'True').lower() == 'true'

    # === Local AI Answer Generation (grounded LLM) ===
    # Master switch. Off by default so CI / low-RAM installs don't download or
    # load a model — when off, /query falls back to returning ranked passages.
    LLM_ENABLED: bool = os.getenv('LLM_ENABLED', 'False').lower() == 'true'
    # Backend that actually generates:
    #   "embedded" — in-process llama.cpp, one generation at a time (a single
    #                shared model; fine for a homelab / a few users).
    #   "openai"   — stream from an external OpenAI-compatible inference server
    #                (Ollama / vLLM / TGI / llama.cpp --server) that batches
    #                concurrent requests — the horizontal-scaling path. No
    #                in-process model or lock, so backend workers stay stateless.
    LLM_BACKEND: str = os.getenv('LLM_BACKEND', 'embedded')
    # openai backend only: base URL (…/v1), optional key, and the served model.
    LLM_API_BASE: str = os.getenv('LLM_API_BASE', 'http://localhost:11434/v1')
    LLM_API_KEY: str = os.getenv('LLM_API_KEY', '')
    LLM_MODEL: str = os.getenv('LLM_MODEL', 'qwen2.5:1.5b-instruct')
    # Vision model (on the same OpenAI-compatible server) used to OCR/describe
    # uploaded images at ingestion time. Only needs to be a model that accepts
    # image_url content — e.g. a VL or OCR model.
    LLM_VISION_MODEL: str = os.getenv('LLM_VISION_MODEL', 'qwen3-vl-2b-instruct')
    # openai backend only: cap simultaneous in-flight generations from this
    # process to protect the inference server (0 = unlimited).
    LLM_MAX_CONCURRENCY: int = int(os.getenv('LLM_MAX_CONCURRENCY', 8))
    # The model — any GGUF under your RAM budget. Repo + file are all you change
    # to swap models (downloaded once from HuggingFace into LLM_MODELS_DIR).
    LLM_MODEL_REPO: str = os.getenv('LLM_MODEL_REPO', 'Qwen/Qwen2.5-1.5B-Instruct-GGUF')
    LLM_MODEL_FILE: str = os.getenv('LLM_MODEL_FILE', 'qwen2.5-1.5b-instruct-q4_k_m.gguf')
    LLM_MODELS_DIR: str = os.getenv('LLM_MODELS_DIR', '/app/models')
    # Reasoning: when True the model thinks inside a <think></think> block
    # before the final answer (best with a thinking-capable model). The UI
    # shows that reasoning in a separate collapsible section.
    LLM_THINKING_ENABLED: bool = os.getenv('LLM_THINKING_ENABLED', 'False').lower() == 'true'
    LLM_CONTEXT_SIZE: int = int(os.getenv('LLM_CONTEXT_SIZE', 4096))
    LLM_MAX_TOKENS: int = int(os.getenv('LLM_MAX_TOKENS', 512))
    LLM_THREADS: int = int(os.getenv('LLM_THREADS', 0))  # 0 = llama.cpp auto
    LLM_TEMPERATURE: float = float(os.getenv('LLM_TEMPERATURE', 0.0))  # 0 = deterministic grounding
    # Refusal gate: if the top reranked relevance score is below this, the model
    # is never called and the fixed refusal message is returned. Tune upward if
    # you see the model answering from thin context.
    LLM_MIN_RELEVANCE_SCORE: float = float(os.getenv('LLM_MIN_RELEVANCE_SCORE', 0.0))

    # === Security Configuration ===
    CORS_ALLOWED_ORIGINS_LIST: list = [
        origin.strip()
        for origin in os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:3000').split(',')
        if origin.strip()
    ]

    # === Auth / Session Configuration (Vaultly multi-user) ===
    # No default — a missing secret at import time is a startup-time bug,
    # not a runtime surprise. Generate with e.g. `openssl rand -hex 32`.
    JWT_SECRET: str = os.getenv('JWT_SECRET', '')
    SESSION_COOKIE_MAX_AGE_SECONDS: int = int(os.getenv('SESSION_COOKIE_MAX_AGE_SECONDS', 7 * 24 * 3600))
    DEFAULT_STORAGE_QUOTA_BYTES: int = int(os.getenv('DEFAULT_STORAGE_QUOTA_BYTES', 1024 ** 3))
    FRONTEND_BASE_URL: str = os.getenv('FRONTEND_BASE_URL', 'http://localhost:3000')

    # Email of the operator/admin account. A user whose email matches this is
    # treated as an admin (metadata-only admin panel) regardless of their
    # stored is_admin flag. Leave unset to designate no env-level admin.
    ADMIN_EMAIL: str = os.getenv('ADMIN_EMAIL', '')
    # Optional. If set alongside ADMIN_EMAIL, a default admin account is
    # seeded on startup (create-if-missing) so there's an admin to log in as
    # out of the box. If ADMIN_EMAIL is set but this is empty, a random
    # temporary password is generated and logged once at creation.
    ADMIN_PASSWORD: str = os.getenv('ADMIN_PASSWORD', '')

    # === Google OAuth Configuration ===
    GOOGLE_CLIENT_ID: str = os.getenv('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET: str = os.getenv('GOOGLE_CLIENT_SECRET', '')
    GOOGLE_REDIRECT_URI: str = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:3000/api/auth/google/callback')

    # === Webhook Delivery Configuration ===
    WEBHOOK_MAX_RETRIES: int = int(os.getenv('WEBHOOK_MAX_RETRIES', 3))
    WEBHOOK_TIMEOUT_SECONDS: int = int(os.getenv('WEBHOOK_TIMEOUT_SECONDS', 5))

    # === SMTP Configuration (password reset email) ===
    SMTP_HOST: str = os.getenv('SMTP_HOST', '')
    SMTP_PORT: int = int(os.getenv('SMTP_PORT', 587))
    SMTP_USER: str = os.getenv('SMTP_USER', '')
    SMTP_PASSWORD: str = os.getenv('SMTP_PASSWORD', '')
    SMTP_FROM: str = os.getenv('SMTP_FROM', 'noreply@vaultly.local')
    SMTP_USE_TLS: bool = os.getenv('SMTP_USE_TLS', 'True').lower() == 'true'

    # === Billing / Plan limits (INR) — all overridable via env ===
    # Per-plan storage allowances (GB).
    FREE_STORAGE_GB: int = int(os.getenv('FREE_STORAGE_GB', 1))
    PRO_STORAGE_GB: int = int(os.getenv('PRO_STORAGE_GB', 5))
    MAX_STORAGE_GB: int = int(os.getenv('MAX_STORAGE_GB', 15))
    # Per-user AI question allowance per day. Max is "unlimited plan-wide" but
    # still capped per individual user (matters for shared/team plans).
    FREE_AI_QUESTIONS_PER_DAY: int = int(os.getenv('FREE_AI_QUESTIONS_PER_DAY', 10))
    PRO_AI_QUESTIONS_PER_DAY: int = int(os.getenv('PRO_AI_QUESTIONS_PER_DAY', 25))
    MAX_AI_QUESTIONS_PER_DAY_PER_USER: int = int(os.getenv('MAX_AI_QUESTIONS_PER_DAY_PER_USER', 30))
    # Prices in whole rupees.
    PRO_PRICE_MONTHLY_INR: int = int(os.getenv('PRO_PRICE_MONTHLY_INR', 59))
    PRO_PRICE_ANNUAL_INR: int = int(os.getenv('PRO_PRICE_ANNUAL_INR', 600))
    MAX_PRICE_MONTHLY_INR: int = int(os.getenv('MAX_PRICE_MONTHLY_INR', 79))
    MAX_PRICE_ANNUAL_INR: int = int(os.getenv('MAX_PRICE_ANNUAL_INR', 800))
    # Max team members that can share a Max-plan workspace.
    MAX_PLAN_TEAM_MEMBERS: int = int(os.getenv('MAX_PLAN_TEAM_MEMBERS', 5))

    @classmethod
    def validate(cls):
        """
        Validate configuration values.
        """
        if cls.CHUNK_SIZE <= 0:
            raise ValueError("CHUNK_SIZE must be positive")
        if cls.CHUNK_OVERLAP < 0:
            raise ValueError("CHUNK_OVERLAP cannot be negative")
        if cls.REDIS_PORT <= 0 or cls.REDIS_PORT > 65535:
            raise ValueError("REDIS_PORT must be between 1 and 65535")
        if cls.APP_PORT <= 0 or cls.APP_PORT > 65535:
            raise ValueError("APP_PORT must be between 1 and 65535")
        if not cls.JWT_SECRET:
            raise ValueError(
                "JWT_SECRET must be set (e.g. `openssl rand -hex 32`) — required for "
                "account sessions."
            )

# Initialize and validate config
config = Config()
config.validate()

# Print configuration for debugging (only in debug mode)
if config.DEBUG:
    print("=== Local RAG Configuration ===")
    for attr, value in config.__class__.__dict__.items():
        if not attr.startswith('_') and not callable(value):
            print(f"{attr}: {getattr(config, attr)}")
    print("===============================")