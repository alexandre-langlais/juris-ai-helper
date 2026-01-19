from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import Response

from app.config import settings
from app.services.pdf_service import extract_text_blocks, add_annotations_to_pdf, get_pdf_info
from app.services.csv_service import parse_csv
from app.services.ollama_service import analyze_all_blocks, check_ollama_health
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


@router.post("/process")
async def process_pdf(
    pdf: UploadFile = File(..., description="Fichier PDF du contrat"),
    csv: UploadFile = File(..., description="Fichier CSV avec sujets et commentaires"),
):
    """
    Traite un PDF et l'annote automatiquement basé sur le CSV fourni.

    - Extrait le texte du PDF par blocs avec coordonnées
    - Parse le CSV pour obtenir les sujets et commentaires
    - Utilise l'IA (Ollama) pour matcher les blocs avec les sujets
    - Insère des annotations Sticky Notes dans le PDF
    - Retourne le PDF annoté

    Args:
        pdf: Fichier PDF du contrat à annoter
        csv: Fichier CSV avec colonnes 'sujet' et 'commentaire'

    Returns:
        Le fichier PDF annoté en téléchargement
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

    # Extraction des blocs de texte du PDF
    try:
        text_blocks = extract_text_blocks(pdf_bytes)
        logger.info(f"PDF extrait: {len(text_blocks)} blocs de texte trouves")
    except Exception as e:
        logger.error(f"Erreur extraction PDF: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Erreur lors de l'extraction du PDF: {e}",
        )

    if not text_blocks:
        logger.warning("Aucun texte extractible dans le PDF")
        raise HTTPException(
            status_code=400,
            detail="Aucun texte extractible trouvé dans le PDF",
        )

    # Analyse des blocs avec l'IA
    logger.info("Demarrage de l'analyse IA des blocs de texte...")
    try:
        matches = await analyze_all_blocks(text_blocks, csv_entries)
        logger.info(f"Analyse terminee: {len(matches)} correspondances trouvees")
    except Exception as e:
        logger.error(f"Erreur analyse IA: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de l'analyse IA: {e}",
        )

    # Création du PDF annoté
    if matches:
        logger.info(f"Creation du PDF annote avec {len(matches)} annotations")
        try:
            annotated_pdf = add_annotations_to_pdf(pdf_bytes, matches)
        except Exception as e:
            logger.error(f"Erreur annotation PDF: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Erreur lors de l'annotation du PDF: {e}",
            )
    else:
        logger.info("Aucune correspondance trouvee, retour du PDF original")
        annotated_pdf = pdf_bytes

    # Construction du nom de fichier de sortie
    original_name = pdf.filename or "document"
    if original_name.lower().endswith(".pdf"):
        output_name = original_name[:-4] + "_annote.pdf"
    else:
        output_name = original_name + "_annote.pdf"

    logger.info(f"Traitement termine avec succes - Fichier: {output_name}, Annotations: {len(matches)}")

    return Response(
        content=annotated_pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{output_name}"',
            "X-Annotations-Count": str(len(matches)),
        },
    )


@router.post("/preview")
async def preview_pdf(
    pdf: UploadFile = File(..., description="Fichier PDF du contrat"),
):
    """
    Prévisualise les informations d'un PDF sans l'annoter.

    Args:
        pdf: Fichier PDF à analyser

    Returns:
        Informations sur le PDF (nombre de pages, métadonnées)
    """
    if not pdf.filename or not pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Le fichier doit être un PDF (.pdf)",
        )

    try:
        pdf_bytes = await pdf.read()
        info = get_pdf_info(pdf_bytes)
        text_blocks = extract_text_blocks(pdf_bytes)

        return {
            "filename": pdf.filename,
            "page_count": info["page_count"],
            "text_blocks_count": len(text_blocks),
            "metadata": info["metadata"],
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Erreur lors de l'analyse du PDF: {e}",
        )
