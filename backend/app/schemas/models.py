from pydantic import BaseModel, Field


class CSVEntry(BaseModel):
    """Une entrée du fichier CSV avec sujet et commentaire."""

    sujet: str = Field(..., description="Le sujet/clause à rechercher dans le contrat")
    commentaire: str = Field(..., description="Le commentaire à annoter")


class Chapter(BaseModel):
    """Un chapitre extrait du PDF avec son titre et son contenu."""

    title: str = Field(..., description="Titre du chapitre")
    content: str = Field(..., description="Contenu textuel complet du chapitre")
    start_page: int = Field(..., description="Page de début du chapitre (0-indexed)")
    end_page: int = Field(..., description="Page de fin du chapitre (0-indexed)")
    title_x0: float = Field(..., description="Coordonnée X gauche du titre")
    title_y0: float = Field(..., description="Coordonnée Y haut du titre")
    title_x1: float = Field(..., description="Coordonnée X droite du titre")
    title_y1: float = Field(..., description="Coordonnée Y bas du titre")
    title_font_size: float = Field(..., description="Taille de police du titre")


class ChapterAnalysis(BaseModel):
    """Résultat de l'analyse d'un chapitre par le LLM."""

    chapter: Chapter
    matched: bool = Field(..., description="True si le chapitre correspond à un sujet")
    csv_entry: CSVEntry | None = Field(
        default=None, description="L'entrée CSV correspondante si matched=True"
    )
    explanation: str = Field(
        ..., description="Explication du LLM justifiant sa décision"
    )


class ProcessingResult(BaseModel):
    """Résultat complet du traitement d'un PDF."""

    analyses: list[ChapterAnalysis] = Field(
        ..., description="Liste des analyses pour chaque chapitre"
    )
    total_chapters: int = Field(..., description="Nombre total de chapitres analysés")
    matched_chapters: int = Field(..., description="Nombre de chapitres avec correspondance")


class HealthResponse(BaseModel):
    """Réponse de la route health."""

    status: str
    app: str
    version: str
