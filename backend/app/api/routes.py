import base64
import json
from typing import Optional, AsyncGenerator

from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from fastapi.responses import StreamingResponse

from app.config import settings
from app.services.pdf_service import (
    extract_chapters,
    add_annotations_to_pdf,
    get_pdf_info,
    get_toc_preview,
)
from app.services.csv_service import parse_spreadsheet
from app.services.ollama_service import (
    analyze_all_chapters,
    analyze_all_chapters_streaming,
    check_ollama_health,
)
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


ALLOWED_SPREADSHEET_EXTENSIONS = (".csv", ".xlsx", ".xls")


@router.post("/preview-subjects")
async def preview_subjects(
    file: UploadFile = File(..., description="Fichier CSV ou Excel avec sujets et commentaires"),
):
    """
    Valide et prévisualise le contenu d'un fichier CSV ou Excel.

    Retourne le nombre de sujets détectés et la liste des sujets.

    Args:
        file: Fichier CSV (.csv) ou Excel (.xlsx, .xls)

    Returns:
        JSON avec:
        - valid: True si le fichier est valide
        - subjects_count: Nombre de sujets détectés
        - subjects: Liste des sujets (limité aux 10 premiers)
        - filename: Nom du fichier
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nom de fichier manquant")

    filename_lower = file.filename.lower()
    if not any(filename_lower.endswith(ext) for ext in ALLOWED_SPREADSHEET_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail=f"Format non supporté. Formats acceptés: {', '.join(ALLOWED_SPREADSHEET_EXTENSIONS)}",
        )

    try:
        file_bytes = await file.read()

        # Vérification de la taille
        max_bytes = settings.max_csv_size_mb * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"Le fichier dépasse la taille maximale de {settings.max_csv_size_mb} Mo",
            )

        entries = parse_spreadsheet(file_bytes, file.filename)

        return {
            "valid": True,
            "subjects_count": len(entries),
            "subjects": [entry.sujet for entry in entries[:10]],  # Limiter à 10 pour l'apercu
            "filename": file.filename,
        }

    except ValueError as e:
        return {
            "valid": False,
            "error": str(e),
            "subjects_count": 0,
            "subjects": [],
            "filename": file.filename,
        }
    except Exception as e:
        logger.error(f"Erreur lors de la preview du fichier: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Erreur lors de la lecture du fichier: {e}",
        )


@router.post("/process")
async def process_pdf(
    pdf: UploadFile = File(..., description="Fichier PDF du contrat"),
    csv: UploadFile = File(..., description="Fichier CSV ou Excel avec sujets et commentaires"),
    model: Optional[str] = Form(
        default=None,
        description="Modèle LLM à utiliser. Utilise le modèle par défaut si non spécifié."
    ),
):
    """
    Traite un PDF et l'annote automatiquement basé sur le fichier de sujets fourni.

    - Extrait les chapitres du PDF via la table des matières
    - Parse le CSV/Excel pour obtenir les sujets et commentaires
    - Utilise l'IA (Ollama) pour analyser chaque chapitre et matcher avec les sujets
    - Insère des annotations Sticky Notes dans le PDF pour les correspondances
    - Retourne le PDF annoté ET les explications de chaque décision du LLM

    Args:
        pdf: Fichier PDF du contrat à annoter (doit contenir une table des matières)
        csv: Fichier CSV ou Excel avec colonnes 'sujet' et 'commentaire'
        model: Modèle LLM à utiliser (optionnel)

    Returns:
        JSON avec:
        - pdf_base64: Le PDF annoté encodé en base64
        - pdf_filename: Nom du fichier de sortie
        - analyses: Liste des analyses pour chaque chapitre avec explications
        - total_chapters: Nombre total de chapitres analysés
        - matched_chapters: Nombre de chapitres avec correspondance
    """
    logger.info(f"Nouvelle requete de traitement - PDF: {pdf.filename}, Sujets: {csv.filename}")

    # Validation des types de fichiers
    if not pdf.filename or not pdf.filename.lower().endswith(".pdf"):
        logger.warning(f"Fichier PDF invalide: {pdf.filename}")
        raise HTTPException(
            status_code=400,
            detail="Le fichier doit être un PDF (.pdf)",
        )

    csv_filename_lower = csv.filename.lower() if csv.filename else ""
    if not any(csv_filename_lower.endswith(ext) for ext in ALLOWED_SPREADSHEET_EXTENSIONS):
        logger.warning(f"Fichier de sujets invalide: {csv.filename}")
        raise HTTPException(
            status_code=400,
            detail=f"Le fichier doit être un CSV ou Excel ({', '.join(ALLOWED_SPREADSHEET_EXTENSIONS)})",
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

    # Parse du fichier de sujets (CSV ou Excel)
    try:
        csv_entries = parse_spreadsheet(csv_bytes, csv.filename or "file.csv")
        logger.info(f"Fichier de sujets parse: {len(csv_entries)} sujets trouves")
    except ValueError as e:
        logger.error(f"Erreur parsing CSV: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    # Extraction des chapitres via la table des matières
    try:
        chapters = extract_chapters(pdf_bytes)
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
            detail="Aucune table des matières détectée dans le PDF. "
                   "Assurez-vous que le document contient un sommaire avec les titres "
                   "de chapitres et leurs numéros de page.",
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


@router.post("/process-stream")
async def process_pdf_stream(
    pdf: UploadFile = File(..., description="Fichier PDF du contrat"),
    csv: UploadFile = File(..., description="Fichier CSV ou Excel avec sujets et commentaires"),
    model: Optional[str] = Form(
        default=None,
        description="Modèle LLM à utiliser. Utilise le modèle par défaut si non spécifié."
    ),
):
    """
    Traite un PDF avec streaming SSE pour le suivi de progression en temps réel.

    Envoie des événements SSE pendant l'analyse:
    - progress: chapitre en cours d'analyse
    - chapter_done: chapitre analysé
    - complete: traitement terminé avec résultat final
    - error: en cas d'erreur
    """
    logger.info(f"Nouvelle requete streaming - PDF: {pdf.filename}, Sujets: {csv.filename}")

    # Validation des types de fichiers
    if not pdf.filename or not pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Le fichier doit être un PDF (.pdf)")

    csv_filename_lower = csv.filename.lower() if csv.filename else ""
    if not any(csv_filename_lower.endswith(ext) for ext in ALLOWED_SPREADSHEET_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail=f"Le fichier doit être un CSV ou Excel ({', '.join(ALLOWED_SPREADSHEET_EXTENSIONS)})",
        )

    # Lecture des fichiers
    try:
        pdf_bytes = await pdf.read()
        csv_bytes = await csv.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la lecture des fichiers: {e}")

    # Vérification de la taille des fichiers
    max_pdf_bytes = settings.max_pdf_size_mb * 1024 * 1024
    max_csv_bytes = settings.max_csv_size_mb * 1024 * 1024

    if len(pdf_bytes) > max_pdf_bytes:
        raise HTTPException(status_code=400, detail=f"Le PDF dépasse la taille maximale de {settings.max_pdf_size_mb} Mo")

    if len(csv_bytes) > max_csv_bytes:
        raise HTTPException(status_code=400, detail=f"Le CSV dépasse la taille maximale de {settings.max_csv_size_mb} Mo")

    # Parse du fichier de sujets (CSV ou Excel)
    try:
        csv_entries = parse_spreadsheet(csv_bytes, csv.filename or "file.csv")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Extraction des chapitres
    try:
        chapters = extract_chapters(pdf_bytes)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de l'extraction des chapitres: {e}")

    if not chapters:
        raise HTTPException(
            status_code=400,
            detail="Aucune table des matières détectée dans le PDF."
        )

    effective_model = model or settings.ollama_model
    original_name = pdf.filename or "document"
    if original_name.lower().endswith(".pdf"):
        output_name = original_name[:-4] + "_annote.pdf"
    else:
        output_name = original_name + "_annote.pdf"

    async def generate_sse() -> AsyncGenerator[str, None]:
        """Générateur SSE pour le streaming de progression."""
        try:
            # Envoyer l'événement de démarrage
            yield f"data: {json.dumps({'type': 'start', 'total_chapters': len(chapters)})}\n\n"

            analyses = []

            # Streamer la progression de l'analyse
            async for event in analyze_all_chapters_streaming(chapters, csv_entries, effective_model):
                if event["type"] == "complete":
                    analyses = event["analyses"]
                else:
                    yield f"data: {json.dumps(event)}\n\n"

            # Créer le PDF annoté
            yield f"data: {json.dumps({'type': 'annotating', 'message': 'Creation du PDF annote...'})}\n\n"

            annotated_pdf = add_annotations_to_pdf(pdf_bytes, analyses)

            # Construire la réponse finale
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

            matched_count = sum(1 for a in analyses if a.matched)

            # Envoyer le résultat final
            final_result = {
                "type": "complete",
                "pdf_base64": base64.b64encode(annotated_pdf).decode("utf-8"),
                "pdf_filename": output_name,
                "analyses": analyses_response,
                "total_chapters": len(chapters),
                "matched_chapters": matched_count,
            }
            yield f"data: {json.dumps(final_result)}\n\n"

        except Exception as e:
            logger.error(f"Erreur streaming: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/preview")
async def preview_pdf(
    pdf: UploadFile = File(..., description="Fichier PDF du contrat"),
):
    """
    Prévisualise les chapitres d'un PDF sans l'annoter.

    Détecte la table des matières et retourne les chapitres qui seront analysés.

    Args:
        pdf: Fichier PDF à analyser

    Returns:
        Informations sur le PDF et aperçu des chapitres détectés via la table des matières
    """
    if not pdf.filename or not pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Le fichier doit être un PDF (.pdf)",
        )

    try:
        pdf_bytes = await pdf.read()
        info = get_pdf_info(pdf_bytes)
        toc_entries = get_toc_preview(pdf_bytes)

        return {
            "filename": pdf.filename,
            "page_count": info["page_count"],
            "metadata": info["metadata"],
            "chapters_count": len(toc_entries),
            "chapters": toc_entries,
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Erreur lors de l'analyse du PDF: {e}",
        )
