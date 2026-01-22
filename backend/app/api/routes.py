import base64
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from fastapi.responses import Response

from app.config import settings
from app.services.pdf_service import (
    extract_chapters,
    add_annotations_to_pdf,
    get_pdf_info,
    analyze_font_sizes,
)
from app.services.csv_service import parse_csv
from app.services.ollama_service import analyze_all_chapters, check_ollama_health
from app.schemas.models import ProcessingResult
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/ollama/health")
async def ollama_health():
    """Vérifie la connexion au service Ollama."""
    logger.info("Verification de la connexion Ollama")
    is_healthy = await check_ollama_health()
    if not is_healthy:
        logger.error("Service Ollama non disponible")
        raise HTTPException(
            status_code=503,
            detail="Service Ollama non disponible",
        )
    logger.info(f"Ollama connecte avec le modele {settings.ollama_model}")
    return {"status": "connected", "model": settings.ollama_model}


@router.get("/models")
async def get_available_models():
    """Retourne la liste des modèles LLM disponibles."""
    models = [m.strip() for m in settings.ollama_available_models.split(",")]
    return {
        "models": models,
        "default": settings.ollama_model,
    }


@router.post("/process")
async def process_pdf(
    pdf: UploadFile = File(..., description="Fichier PDF du contrat"),
    csv: UploadFile = File(..., description="Fichier CSV avec sujets et commentaires"),
    min_title_font_size: Optional[float] = Form(
        default=None,
        description="Taille de police minimale pour détecter les titres de chapitres. "
                    "Utilise la valeur par défaut de config si non spécifié."
    ),
    model: Optional[str] = Form(
        default=None,
        description="Modèle LLM à utiliser. Utilise le modèle par défaut si non spécifié."
    ),
):
    """
    Traite un PDF et l'annote automatiquement basé sur le CSV fourni.

    - Extrait les chapitres du PDF (détectés via la taille de police des titres)
    - Parse le CSV pour obtenir les sujets et commentaires
    - Utilise l'IA (Ollama) pour analyser chaque chapitre et matcher avec les sujets
    - Insère des annotations Sticky Notes dans le PDF pour les correspondances
    - Retourne le PDF annoté ET les explications de chaque décision du LLM

    Args:
        pdf: Fichier PDF du contrat à annoter
        csv: Fichier CSV avec colonnes 'sujet' et 'commentaire'
        min_title_font_size: Taille de police minimale pour les titres de chapitres

    Returns:
        JSON avec:
        - pdf_base64: Le PDF annoté encodé en base64
        - pdf_filename: Nom du fichier de sortie
        - analyses: Liste des analyses pour chaque chapitre avec explications
        - total_chapters: Nombre total de chapitres analysés
        - matched_chapters: Nombre de chapitres avec correspondance
    """
    logger.info(f"Nouvelle requete de traitement - PDF: {pdf.filename}, CSV: {csv.filename}")

    # Validation des types de fichiers
    if not pdf.filename or not pdf.filename.lower().endswith(".pdf"):
        logger.warning(f"Fichier PDF invalide: {pdf.filename}")
        raise HTTPException(
            status_code=400,
            detail="Le fichier doit être un PDF (.pdf)",
        )

    if not csv.filename or not csv.filename.lower().endswith(".csv"):
        logger.warning(f"Fichier CSV invalide: {csv.filename}")
        raise HTTPException(
            status_code=400,
            detail="Le fichier doit être un CSV (.csv)",
        )

    # Lecture des fichiers
    try:
        pdf_bytes = await pdf.read()
        csv_bytes = await csv.read()
        logger.debug(f"Fichiers lus - PDF: {len(pdf_bytes)} bytes, CSV: {len(csv_bytes)} bytes")
    except Exception as e:
        logger.error(f"Erreur lecture fichiers: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Erreur lors de la lecture des fichiers: {e}",
        )

    # Vérification de la taille des fichiers
    max_pdf_bytes = settings.max_pdf_size_mb * 1024 * 1024
    max_csv_bytes = settings.max_csv_size_mb * 1024 * 1024

    if len(pdf_bytes) > max_pdf_bytes:
        logger.warning(f"PDF trop volumineux: {len(pdf_bytes)} bytes (max: {max_pdf_bytes})")
        raise HTTPException(
            status_code=400,
            detail=f"Le PDF dépasse la taille maximale de {settings.max_pdf_size_mb} Mo",
        )

    if len(csv_bytes) > max_csv_bytes:
        logger.warning(f"CSV trop volumineux: {len(csv_bytes)} bytes (max: {max_csv_bytes})")
        raise HTTPException(
            status_code=400,
            detail=f"Le CSV dépasse la taille maximale de {settings.max_csv_size_mb} Mo",
        )

    # Parse du CSV
    try:
        csv_entries = parse_csv(csv_bytes)
        logger.info(f"CSV parse: {len(csv_entries)} sujets trouves")
    except ValueError as e:
        logger.error(f"Erreur parsing CSV: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    # Déterminer la taille de police pour les titres de chapitres
    effective_font_size = min_title_font_size or settings.default_min_title_font_size
    logger.info(f"Taille de police minimale des titres: {effective_font_size}")

    # Extraction des chapitres
    try:
        chapters = extract_chapters(pdf_bytes, min_title_font_size=effective_font_size)
        logger.info(f"PDF extrait: {len(chapters)} chapitres trouves")
    except Exception as e:
        logger.error(f"Erreur extraction chapitres PDF: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Erreur lors de l'extraction des chapitres du PDF: {e}",
        )

    if not chapters:
        logger.warning("Aucun chapitre detecte dans le PDF")
        raise HTTPException(
            status_code=400,
            detail=f"Aucun chapitre détecté avec une taille de police >= {effective_font_size}. "
                   "Essayez de réduire la valeur de min_title_font_size ou utilisez l'endpoint "
                   "/analyze-fonts pour voir les tailles de police du document.",
        )

    # Analyse des chapitres avec l'IA
    effective_model = model or settings.ollama_model
    logger.info(f"Demarrage de l'analyse IA des chapitres avec le modele {effective_model}...")
    try:
        analyses = await analyze_all_chapters(chapters, csv_entries, effective_model)
        matched_count = sum(1 for a in analyses if a.matched)
        logger.info(f"Analyse terminee: {matched_count} correspondances trouvees sur {len(chapters)} chapitres")
    except Exception as e:
        logger.error(f"Erreur analyse IA: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de l'analyse IA: {e}",
        )

    # Création du PDF annoté
    logger.info(f"Creation du PDF annote avec {matched_count} annotations")
    try:
        annotated_pdf = add_annotations_to_pdf(pdf_bytes, analyses)
    except Exception as e:
        logger.error(f"Erreur annotation PDF: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de l'annotation du PDF: {e}",
        )

    # Construction du nom de fichier de sortie
    original_name = pdf.filename or "document"
    if original_name.lower().endswith(".pdf"):
        output_name = original_name[:-4] + "_annote.pdf"
    else:
        output_name = original_name + "_annote.pdf"

    logger.info(f"Traitement termine avec succes - Fichier: {output_name}, Annotations: {matched_count}")

    # Construction de la réponse avec analyses détaillées
    analyses_response = []
    for analysis in analyses:
        analysis_dict = {
            "chapter_title": analysis.chapter.title,
            "chapter_pages": f"{analysis.chapter.start_page + 1}-{analysis.chapter.end_page + 1}",
            "matched": analysis.matched,
            "explanation": analysis.explanation,
        }
        if analysis.matched and analysis.csv_entry:
            analysis_dict["matched_subject"] = analysis.csv_entry.sujet
            analysis_dict["comment_added"] = analysis.csv_entry.commentaire
        analyses_response.append(analysis_dict)

    return {
        "pdf_base64": base64.b64encode(annotated_pdf).decode("utf-8"),
        "pdf_filename": output_name,
        "analyses": analyses_response,
        "total_chapters": len(chapters),
        "matched_chapters": matched_count,
    }


@router.post("/preview")
async def preview_pdf(
    pdf: UploadFile = File(..., description="Fichier PDF du contrat"),
    min_title_font_size: Optional[float] = Form(
        default=None,
        description="Taille de police minimale pour détecter les titres de chapitres"
    ),
):
    """
    Prévisualise les chapitres d'un PDF sans l'annoter.

    Args:
        pdf: Fichier PDF à analyser
        min_title_font_size: Taille de police minimale pour les titres

    Returns:
        Informations sur le PDF et aperçu des chapitres détectés
    """
    if not pdf.filename or not pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Le fichier doit être un PDF (.pdf)",
        )

    try:
        pdf_bytes = await pdf.read()
        info = get_pdf_info(pdf_bytes)

        effective_font_size = min_title_font_size or settings.default_min_title_font_size
        chapters = extract_chapters(pdf_bytes, min_title_font_size=effective_font_size)

        return {
            "filename": pdf.filename,
            "page_count": info["page_count"],
            "metadata": info["metadata"],
            "min_title_font_size_used": effective_font_size,
            "chapters_count": len(chapters),
            "chapters": [
                {
                    "title": chapter.title,
                    "content_preview": chapter.content[:300] + "..." if len(chapter.content) > 300 else chapter.content,
                    "start_page": chapter.start_page + 1,
                    "end_page": chapter.end_page + 1,
                    "title_font_size": chapter.title_font_size,
                }
                for chapter in chapters
            ],
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Erreur lors de l'analyse du PDF: {e}",
        )


@router.post("/analyze-fonts")
async def analyze_pdf_fonts(
    pdf: UploadFile = File(..., description="Fichier PDF à analyser"),
):
    """
    Analyse les tailles de police utilisées dans un PDF.

    Utile pour déterminer la valeur optimale de min_title_font_size
    pour la détection des chapitres.

    Args:
        pdf: Fichier PDF à analyser

    Returns:
        Statistiques sur les tailles de police avec exemples de texte
    """
    if not pdf.filename or not pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Le fichier doit être un PDF (.pdf)",
        )

    try:
        pdf_bytes = await pdf.read()
        font_analysis = analyze_font_sizes(pdf_bytes)

        return {
            "filename": pdf.filename,
            "min_font_size": font_analysis["min_size"],
            "max_font_size": font_analysis["max_size"],
            "suggested_title_size": font_analysis["suggested_title_size"],
            "font_sizes": font_analysis["font_sizes"],
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Erreur lors de l'analyse des polices: {e}",
        )
