"""Application configuration.

Settings are loaded from environment variables (prefixed POISE_) with sane
defaults for local desktop use. The Tauri sidecar launcher passes the port
and data directory explicitly via env vars at process start.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_data_dir() -> Path:
    """Cross-platform per-user app data directory for Poise."""
    home = Path.home()
    # Windows: %APPDATA%\Poise, macOS/Linux: ~/.local/share/poise
    import os

    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Poise"
    return home / ".local" / "share" / "poise"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POISE_", env_file=".env", extra="ignore")

    app_name: str = "Poise Backend"
    app_version: str = "0.1.0"
    environment: str = "development"

    host: str = "127.0.0.1"
    port: int = 8000  # 8000 by default; Tauri sidecar passes POISE_PORT or reads port from stdout

    data_dir: Path = _default_data_dir()
    database_filename: str = "poise.db"

    cors_origins: list[str] = [
        "tauri://localhost",
        "https://tauri.localhost",
        "http://localhost",
        "http://localhost:1420",
        "http://localhost:1421",
        "http://127.0.0.1:1420",
        "http://127.0.0.1:1421",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
    ]

    log_level: str = "info"

    @property
    def database_path(self) -> Path:
        return self.data_dir / self.database_filename

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path}"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings
