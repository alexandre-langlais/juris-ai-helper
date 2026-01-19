import io
from typing import BinaryIO

import fitz  # PyMuPDF

from app.schemas.models import TextBlock, AnnotationMatch


def extract_text_blocks(pdf_bytes: bytes) -> list[TextBlock]:
    """
    Extrait les blocs de texte d'un PDF avec leurs coordonnées.

    Args:
        pdf_bytes: Contenu binaire du fichier PDF

    Returns:
        Liste de TextBlock avec texte et coordonnées
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text_blocks: list[TextBlock] = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        # Extraction des blocs de texte avec coordonnées
        # Format: (x0, y0, x1, y1, "text", block_no, block_type)
        blocks = page.get_text("blocks")

        for block in blocks:
            # block_type 0 = texte, 1 = image
            if block[6] == 0:  # Type texte uniquement
                text = block[4].strip()
                if text:  # Ignorer les blocs vides
                    text_blocks.append(
                        TextBlock(
                            text=text,
                            page_number=page_num,
                            x0=block[0],
                            y0=block[1],
                            x1=block[2],
                            y1=block[3],
                        )
                    )

    doc.close()
    return text_blocks


def add_annotations_to_pdf(
    pdf_bytes: bytes, matches: list[AnnotationMatch]
) -> bytes:
    """
    Ajoute des annotations Sticky Notes au PDF aux positions des matches.

    Args:
        pdf_bytes: Contenu binaire du PDF original
        matches: Liste des matches texte/sujet avec coordonnées

    Returns:
        Contenu binaire du PDF annoté
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    for match in matches:
        page = doc[match.text_block.page_number]

        # Position de l'annotation (coin supérieur droit du bloc de texte)
        point = fitz.Point(match.text_block.x1, match.text_block.y0)

        # Création de l'annotation Sticky Note
        annot = page.add_text_annot(
            point,
            match.csv_entry.commentaire,
            icon="Note",
        )

        # Personnalisation de l'annotation
        annot.set_info(
            title=f"JurisAnnotate - {match.csv_entry.sujet}",
            content=match.csv_entry.commentaire,
        )
        annot.set_colors(stroke=(1, 0.8, 0))  # Jaune
        annot.update()

    # Sauvegarde en mémoire
    output_buffer = io.BytesIO()
    doc.save(output_buffer)
    doc.close()

    return output_buffer.getvalue()


def get_pdf_info(pdf_bytes: bytes) -> dict:
    """
    Récupère les informations basiques d'un PDF.

    Args:
        pdf_bytes: Contenu binaire du PDF

    Returns:
        Dictionnaire avec les métadonnées du PDF
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    info = {
        "page_count": len(doc),
        "metadata": doc.metadata,
    }
    doc.close()
    return info
