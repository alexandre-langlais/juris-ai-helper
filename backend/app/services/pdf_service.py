import io
import re

import fitz  # PyMuPDF

from app.schemas.models import Chapter, ChapterAnalysis
from app.logging_config import get_logger

logger = get_logger(__name__)


def extract_toc_from_bookmarks(doc: fitz.Document) -> list[tuple[str, int]]:
    """
    Extrait la table des matières depuis les signets/bookmarks du PDF.

    Args:
        doc: Document PyMuPDF ouvert

    Returns:
        Liste de tuples (titre, page) ou liste vide si pas de signets
    """
    toc = doc.get_toc()
    if not toc:
        return []

    # Le TOC de PyMuPDF retourne [level, title, page]
    # On ne garde que le titre et la page (0-indexed)
    entries = []
    for entry in toc:
        level, title, page = entry[0], entry[1], entry[2]
        # On prend tous les niveaux de titres
        if page > 0:  # Page valide
            entries.append((title.strip(), page - 1))  # Convertir en 0-indexed

    logger.info(f"TOC extrait depuis les signets: {len(entries)} entrees")
    return entries


def extract_toc_from_text(doc: fitz.Document, max_pages: int = 10) -> list[tuple[str, int]]:
    """
    Extrait la table des matières en analysant le texte des premières pages.

    Recherche des patterns typiques de TOC comme:
    - "Titre du chapitre ............... 12"
    - "1. Introduction                    5"
    - "Article 1 - Objet .............. 3"

    Args:
        doc: Document PyMuPDF ouvert
        max_pages: Nombre maximum de pages à analyser pour trouver le TOC

    Returns:
        Liste de tuples (titre, page)
    """
    entries = []
    toc_found = False

    # Patterns pour détecter les entrées de TOC
    # Pattern: texte suivi de points/espaces puis d'un numéro de page
    toc_patterns = [
        # "Titre ............... 12" ou "Titre          12"
        re.compile(r'^(.+?)[\s.]{3,}(\d+)\s*$'),
        # "1. Titre ............ 12" ou "1.2.3 Titre ..... 12"
        re.compile(r'^(\d+(?:\.\d+)*\.?\s+.+?)[\s.]{3,}(\d+)\s*$'),
        # "Article 1 - Titre ... 12"
        re.compile(r'^((?:Article|Chapitre|Section|Titre)\s+\d+.+?)[\s.]{3,}(\d+)\s*$', re.IGNORECASE),
    ]

    # Mots-clés indiquant le début d'un sommaire
    toc_start_keywords = ['sommaire', 'table des matières', 'table of contents', 'index']

    pages_to_check = min(max_pages, len(doc))

    for page_num in range(pages_to_check):
        page = doc[page_num]
        text = page.get_text()
        lines = text.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Vérifier si on trouve un indicateur de début de TOC
            line_lower = line.lower()
            if any(kw in line_lower for kw in toc_start_keywords):
                toc_found = True
                continue

            # Si on a trouvé le début du TOC, chercher les entrées
            if toc_found or page_num < 5:  # Toujours chercher dans les 5 premières pages
                for pattern in toc_patterns:
                    match = pattern.match(line)
                    if match:
                        title = match.group(1).strip()
                        page_ref = int(match.group(2))

                        # Filtrer les titres trop courts ou les faux positifs
                        if len(title) >= 3 and page_ref > 0 and page_ref <= len(doc):
                            # Nettoyer le titre (enlever les points de suite)
                            title = re.sub(r'\.+$', '', title).strip()
                            entries.append((title, page_ref - 1))  # 0-indexed
                        break

    # Dédupliquer et trier par page
    seen = set()
    unique_entries = []
    for title, page in entries:
        key = (title.lower(), page)
        if key not in seen:
            seen.add(key)
            unique_entries.append((title, page))

    unique_entries.sort(key=lambda x: x[1])

    logger.info(f"TOC extrait depuis le texte: {len(unique_entries)} entrees")
    return unique_entries


def find_title_position(page: fitz.Page, title: str) -> float | None:
    """
    Recherche la position Y d'un titre sur une page.

    Args:
        page: Page PyMuPDF
        title: Titre à rechercher

    Returns:
        Coordonnée Y du titre ou None si non trouvé
    """
    # Nettoyer le titre pour la recherche
    search_title = title.strip()

    # Rechercher le titre exact d'abord
    text_instances = page.search_for(search_title)
    if text_instances:
        # Prendre la première occurrence
        return text_instances[0].y0

    # Essayer avec les premiers mots du titre (au moins 3 mots ou 20 caractères)
    words = search_title.split()
    if len(words) > 3:
        partial_title = " ".join(words[:4])
        text_instances = page.search_for(partial_title)
        if text_instances:
            return text_instances[0].y0

    # Essayer avec le début du titre (premiers 30 caractères)
    if len(search_title) > 30:
        partial_title = search_title[:30]
        text_instances = page.search_for(partial_title)
        if text_instances:
            return text_instances[0].y0

    return None


def extract_chapters(pdf_bytes: bytes) -> list[Chapter]:
    """
    Extrait les chapitres d'un PDF en utilisant la table des matières.

    Tente d'abord d'extraire le TOC depuis les signets PDF, puis depuis
    l'analyse textuelle des premières pages.

    Args:
        pdf_bytes: Contenu binaire du fichier PDF

    Returns:
        Liste de Chapter avec titre, contenu et pages
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)

    # Essayer d'abord les signets
    toc_entries = extract_toc_from_bookmarks(doc)

    # Si pas de signets, analyser le texte
    if not toc_entries:
        logger.info("Pas de signets trouves, analyse du texte pour trouver le TOC")
        toc_entries = extract_toc_from_text(doc)

    if not toc_entries:
        logger.warning("Aucune table des matieres trouvee dans le PDF")
        doc.close()
        return []

    # Extraire le contenu de chaque chapitre
    chapters: list[Chapter] = []

    for i, (title, start_page) in enumerate(toc_entries):
        # Déterminer la page de fin (page avant le prochain chapitre ou fin du doc)
        if i + 1 < len(toc_entries):
            end_page = toc_entries[i + 1][1] - 1
        else:
            end_page = total_pages - 1

        # S'assurer que les pages sont valides
        start_page = max(0, min(start_page, total_pages - 1))
        end_page = max(start_page, min(end_page, total_pages - 1))

        # Trouver la position Y du titre sur la page de début
        page = doc[start_page]
        title_y = find_title_position(page, title)

        # Extraire le texte des pages du chapitre
        content_parts = []
        for page_num in range(start_page, end_page + 1):
            page = doc[page_num]
            page_text = page.get_text()
            if page_text.strip():
                content_parts.append(page_text)

        content = "\n".join(content_parts).strip()

        # Ne pas ajouter les chapitres vides
        if content:
            chapters.append(Chapter(
                title=title,
                content=content,
                start_page=start_page,
                end_page=end_page,
                title_y=title_y,
            ))

    doc.close()
    logger.info(f"Extraction terminee: {len(chapters)} chapitres extraits")
    return chapters


def add_annotations_to_pdf(
    pdf_bytes: bytes, analyses: list[ChapterAnalysis]
) -> bytes:
    """
    Ajoute des annotations Sticky Notes au PDF pour les chapitres avec correspondance.

    Les annotations sont placées au niveau du titre de chaque chapitre.

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
        page_rect = page.rect

        # Position Y de l'annotation: au niveau du titre si trouvé, sinon en haut
        if chapter.title_y is not None:
            y_pos = chapter.title_y
        else:
            # Fallback: essayer de retrouver le titre sur la page
            title_y = find_title_position(page, chapter.title)
            y_pos = title_y if title_y is not None else 30

        # Position X: à droite de la page (avec une petite marge)
        x_pos = page_rect.width - 25

        point = fitz.Point(x_pos, y_pos)

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


def get_toc_preview(pdf_bytes: bytes) -> list[dict]:
    """
    Retourne un aperçu de la table des matières détectée.

    Args:
        pdf_bytes: Contenu binaire du PDF

    Returns:
        Liste de dictionnaires avec titre et page de chaque entrée du TOC
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    # Essayer d'abord les signets
    toc_entries = extract_toc_from_bookmarks(doc)

    # Si pas de signets, analyser le texte
    if not toc_entries:
        toc_entries = extract_toc_from_text(doc)

    doc.close()

    return [
        {"title": title, "page": page + 1}  # 1-indexed pour l'affichage
        for title, page in toc_entries
    ]
