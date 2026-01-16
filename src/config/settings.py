"""Application configuration settings."""

import os
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)


class DatabaseSettings(BaseModel):
    """Database configuration."""
    url: str = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/holiday_finder.db")


class OllamaSettings(BaseModel):
    """Ollama LLM configuration."""
    host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")


class ScrapingSettings(BaseModel):
    """Web scraping configuration."""
    timeout: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
    rate_limit_delay: float = float(os.getenv("RATE_LIMIT_DELAY", "2"))
    user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


class LoggingSettings(BaseModel):
    """Logging configuration."""
    level: str = os.getenv("LOG_LEVEL", "INFO")
    log_file: Path = LOGS_DIR / "holiday_finder.log"


class Settings(BaseModel):
    """Main application settings."""
    database: DatabaseSettings = DatabaseSettings()
    ollama: OllamaSettings = OllamaSettings()
    scraping: ScrapingSettings = ScrapingSettings()
    logging: LoggingSettings = LoggingSettings()


# Global settings instance
settings = Settings()
