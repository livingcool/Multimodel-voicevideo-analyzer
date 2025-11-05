import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AnyHttpUrl
from pathlib import Path
from enum import Enum
# app/llm/answer_generator.py (New Imports)
import os
from typing import List, Optional, Tuple
from google import genai
from google.genai import types
from typing import Optional  # <-- THE MISSING LINE IS HERE

# --- Enums for Settings ---

class StorageBackend(str, Enum):
    LOCAL = "local"
    S3 = "s3"

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

class LLMProvider(str, Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    
# --- Main Settings Class ---

class Settings(BaseSettings):
    """
    Validates and loads all environment variables for the application.
    """
    
    # --- App ---
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: LogLevel = LogLevel.INFO

    # --- Storage ---
    STORAGE_BACKEND: StorageBackend = StorageBackend.LOCAL
    STORAGE_LOCAL_ROOT: Path = Field(default=Path("/srv/multimodal/data"))
    S3_ENDPOINT_URL: Optional[AnyHttpUrl] = None
    S3_ACCESS_KEY: Optional[str] = None
    S3_SECRET_KEY: Optional[str] = None
    S3_BUCKET: Optional[str] = None

    # --- Sarvam ---
    SARVAM_API_KEY: str = Field(..., description="API key for Sarvam transcription service")
    SARVAM_API_URL: AnyHttpUrl = "https://api.sarvam.example/v1/transcribe"

    # --- Redis / Celery ---
    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    CELERY_BROKER_URL: str = Field(validation_alias="REDIS_URL")
    CELERY_RESULT_BACKEND: str = Field(validation_alias="REDIS_URL")
    CELERY_DEFAULT_QUEUE: str = "cpu_tasks"

    # --- Database (Metadata Store) ---
    DATABASE_URL: str = "sqlite:///./metadata.db"
    
    # --- Embeddings / LLM ---
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    LLM_PROVIDER: LLMProvider = LLMProvider.GEMINI
    
    OPENAI_API_KEY: Optional[str] = Field(None, description="Required if LLM_PROVIDER is 'openai'")
    GOOGLE_API_KEY: Optional[str] = Field(None, description="Required if LLM_PROVIDER is 'gemini'")

    # --- App Limits (Tuning) ---
    VIDEO_FRAME_INTERVAL_SEC: int = 7
    TRANSCRIPT_CHUNK_SEC: int = 30
    BATCH_EMBED_SIZE: int = 16

    # --- Derived Paths (Computed properties) ---
    @property
    def UPLOAD_DIR(self) -> Path:
        return self.STORAGE_LOCAL_ROOT / "uploads"
    
    @property
    def TRANSCRIPT_DIR(self) -> Path:
        return self.STORAGE_LOCAL_ROOT / "transcripts"
    
    @property
    def FRAME_DIR(self) -> Path:
        return self.STORAGE_LOCAL_ROOT / "frames"
    
    @property
    def VECTOR_DIR(self) -> Path:
        return self.STORAGE_LOCAL_ROOT / "vectors"

    # --- Model Config ---
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

# --- Singleton Instance ---
try:
    settings = Settings()
except Exception as e:
    print(f"FATAL: Error loading configuration. {e}")
    raise

# --- Helper Function ---
def get_settings() -> Settings:
    """Dependency for FastAPI to get the settings."""
    return settings