import io

import fitz  # PyMuPDF

from app.schemas.models import Chapter, ChapterAnalysis


def extract_chapters(pdf_bytes: bytes, min_title_font_size: float = 14.0) -> list[Chapter]:
    """
    Extrait les chapitres d'un PDF en détectant les titres par leur taille de police.

    Un chapitre commence par un titre (texte avec une police >= min_title_font_size)
    et contient tout le texte jusqu'au prochain titre de chapitre.

    Args:
        pdf_bytes: Contenu binaire du fichier PDF
        min_title_font_size: Taille de police minimale pour considérer un texte comme titre de chapitre

    Returns:
        Liste de Chapter avec titre, contenu et coordonnées
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    # Structure pour stocker les éléments de texte avec leur taille de police
    text_elements: list[dict] = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        # Extraction détaillée avec informations de police
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # Type 0 = texte
                continue

            for line in block.get("lines", []):
                line_text = ""
                line_font_size = 0.0
                line_bbox = line.get("bbox", (0, 0, 0, 0))

                for span in line.get("spans", []):
                    span_text = span.get("text", "").strip()
                    span_size = span.get("size", 0.0)

                    if span_text:
                        line_text += span.get("text", "")
                        # Prendre la taille de police maximale de la ligne
                        line_font_size = max(line_font_size, span_size)

                line_text = line_text.strip()
                if line_text:
                    text_elements.append({
                        "text": line_text,
                        "font_size": line_font_size,
                        "page_number": page_num,
                        "x0": line_bbox[0],
                        "y0": line_bbox[1],
                        "x1": line_bbox[2],
                        "y1": line_bbox[3],
                    })

    doc.close()

    # Regroupement en chapitres
    chapters: list[Chapter] = []
    current_chapter: dict | None = None

    for element in text_elements:
        is_title = element["font_size"] >= min_title_font_size

        if is_title:
            # Sauvegarder le chapitre précédent s'il existe
            if current_chapter is not None and current_chapter["content"].strip():
                chapters.append(Chapter(
                    title=current_chapter["title"],
                    content=current_chapter["content"].strip(),
                    start_page=current_chapter["start_page"],
                    end_page=current_chapter["end_page"],
                    title_x0=current_chapter["title_x0"],
                    title_y0=current_chapter["title_y0"],
                    title_x1=current_chapter["title_x1"],
                    title_y1=current_chapter["title_y1"],
                    title_font_size=current_chapter["title_font_size"],
                ))

            # Démarrer un nouveau chapitre
            current_chapter = {
                "title": element["text"],
                "content": "",
                "start_page": element["page_number"],
                "end_page": element["page_number"],
                "title_x0": element["x0"],
                "title_y0": element["y0"],
                "title_x1": element["x1"],
                "title_y1": element["y1"],
                "title_font_size": element["font_size"],
            }
        elif current_chapter is not None:
            # Ajouter le texte au chapitre courant
            current_chapter["content"] += element["text"] + "\n"
            current_chapter["end_page"] = element["page_number"]

    # Sauvegarder le dernier chapitre
    if current_chapter is not None and current_chapter["content"].strip():
        chapters.append(Chapter(
            title=current_chapter["title"],
            content=current_chapter["content"].strip(),
            start_page=current_chapter["start_page"],
            end_page=current_chapter["end_page"],
            title_x0=current_chapter["title_x0"],
            title_y0=current_chapter["title_y0"],
            title_x1=current_chapter["title_x1"],
            title_y1=current_chapter["title_y1"],
            title_font_size=current_chapter["title_font_size"],
        ))

    return chapters


def add_annotations_to_pdf(
    pdf_bytes: bytes, analyses: list[ChapterAnalysis]
) -> bytes:
    """
    Ajoute des annotations Sticky Notes au PDF pour les chapitres avec correspondance.

    Args:
        pdf_bytes: Contenu binaire du PDF original
        analyses: Liste des analyses de chapitres (seuls les matched=True seront annotés)

    Returns:
        Contenu binaire du PDF annoté
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    for analysis in analyses:
        if not analysis.matched or analysis.csv_entry is None:
            continue

        chapter = analysis.chapter
        page = doc[chapter.start_page]

        # Position de l'annotation (coin supérieur droit du titre)
        point = fitz.Point(chapter.title_x1, chapter.title_y0)

        # Création de l'annotation Sticky Note
        annot = page.add_text_annot(
            point,
            analysis.csv_entry.commentaire,
            icon="Note",
        )

        # Personnalisation de l'annotation
        annot.set_info(
            title=f"JurisAnnotate - {analysis.csv_entry.sujet}",
            content=analysis.csv_entry.commentaire,
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


def analyze_font_sizes(pdf_bytes: bytes) -> dict:
    """
    Analyse les tailles de police utilisées dans le PDF.

    Utile pour aider l'utilisateur à déterminer la taille de police
    minimale des titres de chapitres.

    Args:
        pdf_bytes: Contenu binaire du PDF

    Returns:
        Dictionnaire avec:
        - font_sizes: dict des tailles de police avec leur fréquence et exemples de texte
        - min_size: taille minimale trouvée
        - max_size: taille maximale trouvée
        - suggested_title_size: suggestion de taille pour les titres (percentile 90)
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    # Collecter toutes les tailles de police avec des exemples
    font_data: dict[float, dict] = {}

    for page_num in range(len(doc)):
        page = doc[page_num]
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue

            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    size = round(span.get("size", 0.0), 1)
                    text = span.get("text", "").strip()

                    if size > 0 and text:
                        if size not in font_data:
                            font_data[size] = {
                                "count": 0,
                                "examples": [],
                            }
                        font_data[size]["count"] += 1
                        # Garder quelques exemples (max 3)
                        if len(font_data[size]["examples"]) < 3:
                            # Tronquer les exemples longs
                            example = text[:50] + "..." if len(text) > 50 else text
                            if example not in font_data[size]["examples"]:
                                font_data[size]["examples"].append(example)

    doc.close()

    if not font_data:
        return {
            "font_sizes": {},
            "min_size": 0,
            "max_size": 0,
            "suggested_title_size": 14.0,
        }

    sizes = sorted(font_data.keys())

    # Calculer le percentile 90 pour suggérer la taille des titres
    total_count = sum(data["count"] for data in font_data.values())
    cumulative = 0
    suggested_size = sizes[-1]

    for size in sizes:
        cumulative += font_data[size]["count"]
        if cumulative / total_count >= 0.90:
            suggested_size = size
            break

    return {
        "font_sizes": {size: font_data[size] for size in sizes},
        "min_size": sizes[0],
        "max_size": sizes[-1],
        "suggested_title_size": suggested_size,
    }
