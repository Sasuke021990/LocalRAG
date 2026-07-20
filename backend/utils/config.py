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
    
    # === Cache Configuration ===
    CACHE_TTL_SECONDS: int = int(os.getenv('CACHE_TTL_SECONDS', 3600))
    SEMANTIC_CACHE_SIMILARITY_THRESHOLD: float = float(
        os.getenv('SEMANTIC_CACHE_SIMILARITY_THRESHOLD', 0.92)
    )

    # === API Configuration ===
    MAX_FILE_SIZE_MB: int = int(os.getenv('MAX_FILE_SIZE_MB', 50))

    # === ROCm Configuration ===
    USE_ROCM: bool = os.getenv('USE_ROCM', 'True').lower() == 'true'

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

    # === Google OAuth Configuration ===
    GOOGLE_CLIENT_ID: str = os.getenv('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET: str = os.getenv('GOOGLE_CLIENT_SECRET', '')
    GOOGLE_REDIRECT_URI: str = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:3000/api/auth/google/callback')

    # === SMTP Configuration (password reset email) ===
    SMTP_HOST: str = os.getenv('SMTP_HOST', '')
    SMTP_PORT: int = int(os.getenv('SMTP_PORT', 587))
    SMTP_USER: str = os.getenv('SMTP_USER', '')
    SMTP_PASSWORD: str = os.getenv('SMTP_PASSWORD', '')
    SMTP_FROM: str = os.getenv('SMTP_FROM', 'noreply@vaultly.local')
    SMTP_USE_TLS: bool = os.getenv('SMTP_USE_TLS', 'True').lower() == 'true'

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