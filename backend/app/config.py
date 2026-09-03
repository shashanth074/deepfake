"""Application settings, loaded from environment variables / .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root: backend/app/config.py -> backend/app -> backend -> <root>
ROOT_DIR = Path(__file__).resolve().parents[2]

# The placeholder shipped in .env.example. Booting production with it would sign
# every token with a value published in this repository.
INSECURE_JWT_SECRET = "change-me-in-production"
MIN_JWT_SECRET_LENGTH = 32


class InsecureConfigurationError(RuntimeError):
    """Raised when a production deployment is configured unsafely."""


class Settings(BaseSettings):
    """All runtime configuration. See .env.example for documentation."""

    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- API ---
    app_name: str = "Deepfake Detection Platform"
    api_v1_prefix: str = "/api"
    environment: str = "development"
    debug: bool = True

    # --- Security ---
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    # --- Database ---
    # Anchored to the repository root, not the working directory, so the dev
    # server works whether it is started from the repo root or from backend/.
    database_url: str = f"sqlite:///{ROOT_DIR / 'storage' / 'deepfake.db'}"

    # --- Queue ---
    celery_broker_url: str = ""
    celery_result_backend: str = ""

    # --- Storage ---
    storage_dir: Path = ROOT_DIR / "storage" / "uploads"
    evidence_dir: Path = ROOT_DIR / "storage" / "evidence"
    report_dir: Path = ROOT_DIR / "storage" / "reports"
    max_upload_mb: int = 100

    # --- Rate limiting ---
    upload_rate_limit_per_hour: int = 20
    guest_rate_limit_per_hour: int = 3

    # --- Models ---
    checkpoint_dir: Path = ROOT_DIR / "checkpoints"
    image_model_backbone: str = "efficientnet_b0"
    image_model_version: str = "image-detector-v1.0.0"
    audio_model_version: str = "audio-lcnn-v1.0.0"
    video_model_version: str = "video-frame-agg-v1.0.0"
    video_sample_fps: float = 1.0
    video_max_frames: int = 32
    audio_sample_rate: int = 16000
    audio_window_seconds: float = 4.0
    device: str = "cpu"

    # --- Decision thresholds ---
    fake_threshold: float = 0.5
    uncertain_band: float = 0.15

    # --- Frontend ---
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept a comma-separated string from the environment."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def _reject_unsafe_production(self) -> Settings:
        """Refuse to start a production deployment with an unsafe configuration.

        Failing loudly at boot is the only reliable moment to catch these: once
        the service is serving traffic, a placeholder signing key is a silent
        authentication bypass — anyone with the repository can mint valid tokens.
        """
        if self.environment.lower() != "production":
            return self

        problems: list[str] = []
        if self.jwt_secret_key == INSECURE_JWT_SECRET:
            problems.append(
                "JWT_SECRET_KEY is still the placeholder from .env.example. Generate one with:\n"
                '    python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        elif len(self.jwt_secret_key) < MIN_JWT_SECRET_LENGTH:
            problems.append(
                f"JWT_SECRET_KEY is only {len(self.jwt_secret_key)} characters; "
                f"use at least {MIN_JWT_SECRET_LENGTH}."
            )
        if self.debug:
            problems.append("DEBUG must be false in production — debug output can leak internals.")
        if "*" in self.cors_origins:
            problems.append("CORS_ORIGINS must name real origins in production, never '*'.")

        if problems:
            raise InsecureConfigurationError(
                "Refusing to start: unsafe production configuration.\n\n  - "
                + "\n  - ".join(problems)
            )
        return self

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def queue_enabled(self) -> bool:
        """False => inference runs inline (Celery eager mode), no Redis needed."""
        return bool(self.celery_broker_url)

    def ensure_directories(self) -> None:
        """Create the storage directories the app writes to."""
        for directory in (
            self.storage_dir,
            self.evidence_dir,
            self.report_dir,
            self.checkpoint_dir,
        ):
            Path(directory).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


settings = get_settings()
