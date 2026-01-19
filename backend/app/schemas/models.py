from pydantic import BaseModel, Field


class CSVEntry(BaseModel):
    """Une entrée du fichier CSV avec sujet et commentaire."""

    sujet: str = Field(..., description="Le sujet/clause à rechercher dans le contrat")
    commentaire: str = Field(..., description="Le commentaire à annoter")


class TextBlock(BaseModel):
    """Un bloc de texte extrait du PDF avec ses coordonnées."""

    text: str = Field(..., description="Contenu textuel du bloc")
    page_number: int = Field(..., description="Numéro de la page (0-indexed)")
    x0: float = Field(..., description="Coordonnée X gauche")
    y0: float = Field(..., description="Coordonnée Y haut")
    x1: float = Field(..., description="Coordonnée X droite")
    y1: float = Field(..., description="Coordonnée Y bas")


class AnnotationMatch(BaseModel):
    """Un match entre un bloc de texte et un sujet du CSV."""

    text_block: TextBlock
    csv_entry: CSVEntry
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Score de confiance du match"
    )


class ProcessingStatus(BaseModel):
    """Statut du traitement."""

    status: str = Field(..., description="État du traitement")
    message: str = Field(default="", description="Message descriptif")
    annotations_count: int = Field(
        default=0, description="Nombre d'annotations ajoutées"
    )


class HealthResponse(BaseModel):
    """Réponse de la route health."""

    status: str
    app: str
    version: str
