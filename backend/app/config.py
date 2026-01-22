from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration de l'application."""

    app_name: str = "JurisAnnotate API"
    app_version: str = "0.1.0"
    debug: bool = False

    # Configuration Ollama
    ollama_base_url: str = "http://ollama-service:11434"
    ollama_model: str = "llama3.2"
    ollama_timeout: int = 120
    ollama_available_models: str = "llama3.2,mistral,gemma2"  # Liste séparée par des virgules

    # Limites de fichiers
    max_pdf_size_mb: int = 50
    max_csv_size_mb: int = 5

    # Configuration extraction de chapitres
    default_min_title_font_size: float = 14.0

    class Config:
        env_prefix = "JURIS_"
        env_file = ".env"


settings = Settings()
