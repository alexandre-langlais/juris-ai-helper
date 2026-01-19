from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.routes import router as api_router
from app.logging_config import setup_logging, get_logger

# Configuration du logging
setup_logging()
logger = get_logger(__name__)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="API pour l'annotation automatique de contrats PDF par IA",
)

# Configuration CORS pour le frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # À restreindre en production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusion des routes
app.include_router(api_router, prefix="/api")

logger.info(f"Application {settings.app_name} v{settings.app_version} demarree")
logger.info(f"Ollama configure sur {settings.ollama_base_url} avec le modele {settings.ollama_model}")


@app.get("/health")
async def health_check():
    """Route de vérification de santé de l'API."""
    logger.debug("Health check demande")
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
    }
