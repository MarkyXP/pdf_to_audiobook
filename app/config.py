from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    output_dir: Path = Path("output")
    voice_dir: Path = Path("voices")
    max_file_size_mb: int = 25

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
