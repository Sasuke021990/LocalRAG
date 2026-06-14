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
    
    # === API Configuration ===
    MAX_FILE_SIZE_MB: int = int(os.getenv('MAX_FILE_SIZE_MB', 50))
    
    # === ROCm Configuration ===
    USE_ROCM: bool = os.getenv('USE_ROCM', 'True').lower() == 'true'
    
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