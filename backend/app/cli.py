#!/usr/bin/env python3
"""
JurisAnnotate CLI - Outil en ligne de commande pour l'annotation de contrats PDF.

Usage:
    juris process <pdf> <csv> [options]
    juris analyze-fonts <pdf>
    juris preview <pdf> [options]
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.logging_config import setup_logging, get_logger
from app.config import settings
from app.services.pdf_service import (
    extract_chapters,
    add_annotations_to_pdf,
    get_pdf_info,
    analyze_font_sizes,
)
from app.services.csv_service import parse_csv
from app.services.ollama_service import (
    analyze_all_chapters,
    check_ollama_health,
)


def create_parser() -> argparse.ArgumentParser:
    """Cree le parser principal avec les sous-commandes."""
    parser = argparse.ArgumentParser(
        prog="juris",
        description="JurisAnnotate - Annotation automatique de contrats PDF par IA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Activer les logs de debug",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commandes disponibles")

    # Sous-commande: process
    process_parser = subparsers.add_parser(
        "process",
        help="Traiter un PDF et generer les annotations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  juris process contrat.pdf clauses.csv
  juris process contrat.pdf clauses.csv --output resultat.pdf
  juris process contrat.pdf clauses.csv --min-font-size 14
  juris process contrat.pdf clauses.csv --dry-run --debug
        """,
    )
    process_parser.add_argument("pdf", type=Path, help="Fichier PDF a traiter")
    process_parser.add_argument("csv", type=Path, help="Fichier CSV avec sujets et commentaires")
    process_parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Fichier PDF de sortie (defaut: <pdf>_annote.pdf)",
    )
    process_parser.add_argument(
        "--min-font-size",
        type=float,
        default=None,
        help=f"Taille de police min. pour les titres de chapitres (defaut: {settings.default_min_title_font_size})",
    )
    process_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyser sans generer le PDF annote",
    )
    process_parser.add_argument(
        "--show-chapters",
        action="store_true",
        help="Afficher les chapitres extraits avant analyse",
    )
    process_parser.add_argument(
        "--show-csv",
        action="store_true",
        help="Afficher le contenu du CSV parse",
    )
    process_parser.add_argument(
        "--skip-ai",
        action="store_true",
        help="Ignorer l'analyse IA (test extraction uniquement)",
    )
    process_parser.add_argument(
        "--json",
        action="store_true",
        help="Exporter les analyses en JSON",
    )
    process_parser.add_argument(
        "--ollama-url",
        type=str,
        help=f"URL Ollama (defaut: {settings.ollama_base_url})",
    )
    process_parser.add_argument(
        "--model",
        type=str,
        help=f"Modele Ollama (defaut: {settings.ollama_model})",
    )

    # Sous-commande: analyze-fonts
    fonts_parser = subparsers.add_parser(
        "analyze-fonts",
        help="Analyser les tailles de police d'un PDF",
        epilog="""
Exemple:
  juris analyze-fonts contrat.pdf
        """,
    )
    fonts_parser.add_argument("pdf", type=Path, help="Fichier PDF a analyser")
    fonts_parser.add_argument(
        "--detailed",
        action="store_true",
        help="Afficher les exemples de texte pour chaque taille",
    )

    # Sous-commande: preview
    preview_parser = subparsers.add_parser(
        "preview",
        help="Previsualiser les chapitres d'un PDF",
        epilog="""
Exemples:
  juris preview contrat.pdf
  juris preview contrat.pdf --min-font-size 14
        """,
    )
    preview_parser.add_argument("pdf", type=Path, help="Fichier PDF a analyser")
    preview_parser.add_argument(
        "--min-font-size",
        type=float,
        default=None,
        help=f"Taille de police min. pour les titres (defaut: {settings.default_min_title_font_size})",
    )

    return parser


async def cmd_process(args) -> int:
    """Execute la commande process."""
    logger = get_logger("cli.process")

    # Verification des fichiers
    if not args.pdf.exists():
        print(f"ERREUR: Fichier PDF introuvable: {args.pdf}")
        return 1

    if not args.csv.exists():
        print(f"ERREUR: Fichier CSV introuvable: {args.csv}")
        return 1

    # Override des settings
    if args.ollama_url:
        settings.ollama_base_url = args.ollama_url
    if args.model:
        settings.ollama_model = args.model

    min_font_size = args.min_font_size or settings.default_min_title_font_size

    print("=" * 70)
    print("JurisAnnotate - Traitement PDF")
    print("=" * 70)
    print(f"\nFichier PDF: {args.pdf}")
    print(f"Fichier CSV: {args.csv}")
    print(f"Taille police titres: >= {min_font_size}")
    print(f"Ollama: {settings.ollama_base_url} ({settings.ollama_model})")

    # Lecture des fichiers
    print("\n" + "-" * 50)
    print("ETAPE 1: Lecture des fichiers")
    print("-" * 50)

    pdf_bytes = args.pdf.read_bytes()
    csv_bytes = args.csv.read_bytes()

    print(f"  PDF: {len(pdf_bytes):,} bytes ({len(pdf_bytes) / 1024 / 1024:.2f} Mo)")
    print(f"  CSV: {len(csv_bytes):,} bytes")

    # Informations PDF
    print("\n" + "-" * 50)
    print("ETAPE 2: Analyse du PDF")
    print("-" * 50)

    try:
        pdf_info = get_pdf_info(pdf_bytes)
        print(f"  Nombre de pages: {pdf_info['page_count']}")
        if pdf_info.get("metadata"):
            meta = pdf_info["metadata"]
            if meta.get("title"):
                print(f"  Titre: {meta['title']}")
            if meta.get("author"):
                print(f"  Auteur: {meta['author']}")
    except Exception as e:
        print(f"  ERREUR: {e}")
        return 1

    # Extraction des chapitres
    print("\n" + "-" * 50)
    print("ETAPE 3: Extraction des chapitres")
    print("-" * 50)

    try:
        chapters = extract_chapters(pdf_bytes, min_title_font_size=min_font_size)
        print(f"  Chapitres extraits: {len(chapters)}")

        if not chapters:
            print(f"\n  ATTENTION: Aucun chapitre detecte avec une police >= {min_font_size}")
            print("  Utilisez 'juris analyze-fonts' pour voir les tailles de police du document.")
            return 1

        if args.show_chapters:
            print("\n  --- CHAPITRES ---")
            for i, chapter in enumerate(chapters):
                print(f"\n  [{i + 1}] '{chapter.title}'")
                print(f"      Police: {chapter.title_font_size} pt")
                print(f"      Pages: {chapter.start_page + 1}-{chapter.end_page + 1}")
                content_preview = chapter.content[:150].replace("\n", " ")
                print(f"      Contenu: {content_preview}...")

    except Exception as e:
        print(f"  ERREUR: {e}")
        logger.exception("Erreur extraction chapitres")
        return 1

    # Parse du CSV
    print("\n" + "-" * 50)
    print("ETAPE 4: Parsing du CSV")
    print("-" * 50)

    try:
        csv_entries = parse_csv(csv_bytes)
        print(f"  Sujets trouves: {len(csv_entries)}")

        if args.show_csv:
            print("\n  --- CONTENU CSV ---")
            for i, entry in enumerate(csv_entries):
                print(f"  [{i}] Sujet: {entry.sujet}")
                comment_preview = entry.commentaire[:80] if len(entry.commentaire) > 80 else entry.commentaire
                print(f"      Commentaire: {comment_preview}...")
        else:
            for i, entry in enumerate(csv_entries):
                print(f"  [{i}] {entry.sujet}")

    except ValueError as e:
        print(f"  ERREUR: {e}")
        return 1

    # Analyse IA
    analyses = []
    if not args.skip_ai:
        print("\n" + "-" * 50)
        print("ETAPE 5: Verification connexion Ollama")
        print("-" * 50)

        is_healthy = await check_ollama_health()
        if is_healthy:
            print("  Ollama: CONNECTE")
        else:
            print("  Ollama: NON DISPONIBLE")
            print(f"  Verifiez que Ollama est lance sur {settings.ollama_base_url}")
            print("  Utilisez --skip-ai pour tester sans l'IA")
            return 1

        print("\n" + "-" * 50)
        print("ETAPE 6: Analyse IA des chapitres")
        print("-" * 50)

        print(f"  Demarrage de l'analyse de {len(chapters)} chapitres...")
        print("  (Cela peut prendre plusieurs minutes)\n")

        try:
            analyses = await analyze_all_chapters(chapters, csv_entries)
            matched_count = sum(1 for a in analyses if a.matched)
            print(f"\n  Correspondances trouvees: {matched_count}/{len(chapters)}")

            # Affichage des analyses avec explications
            print("\n  --- ANALYSES DETAILLEES ---")
            for i, analysis in enumerate(analyses):
                status = "MATCH" if analysis.matched else "---"
                print(f"\n  [{i + 1}] {status} - '{analysis.chapter.title}'")
                print(f"      Pages: {analysis.chapter.start_page + 1}-{analysis.chapter.end_page + 1}")

                if analysis.matched and analysis.csv_entry:
                    print(f"      Sujet matche: {analysis.csv_entry.sujet}")

                # Affichage de l'explication (indentee)
                print(f"      Explication LLM:")
                explanation_lines = analysis.explanation.split(". ")
                for line in explanation_lines:
                    if line.strip():
                        print(f"        {line.strip()}.")

        except Exception as e:
            print(f"  ERREUR: {e}")
            logger.exception("Erreur analyse IA")
            return 1

    else:
        print("\n" + "-" * 50)
        print("ETAPE 5-6: Analyse IA IGNOREE (--skip-ai)")
        print("-" * 50)

    # Export JSON si demande
    if args.json and analyses:
        json_output = args.pdf.with_suffix(".analyses.json")
        analyses_data = [
            {
                "chapter_title": a.chapter.title,
                "chapter_pages": f"{a.chapter.start_page + 1}-{a.chapter.end_page + 1}",
                "matched": a.matched,
                "matched_subject": a.csv_entry.sujet if a.matched and a.csv_entry else None,
                "explanation": a.explanation,
            }
            for a in analyses
        ]
        json_output.write_text(json.dumps(analyses_data, ensure_ascii=False, indent=2))
        print(f"\n  Analyses exportees: {json_output}")

    # Generation du PDF
    output_path = None
    matched_analyses = [a for a in analyses if a.matched]

    if not args.dry_run and matched_analyses:
        print("\n" + "-" * 50)
        print("ETAPE 7: Generation du PDF annote")
        print("-" * 50)

        try:
            annotated_pdf = add_annotations_to_pdf(pdf_bytes, analyses)

            if args.output:
                output_path = args.output
            else:
                output_path = args.pdf.with_stem(args.pdf.stem + "_annote")

            output_path.write_bytes(annotated_pdf)
            print(f"  PDF annote: {output_path}")
            print(f"  Taille: {len(annotated_pdf):,} bytes")
            print(f"  Annotations: {len(matched_analyses)}")

        except Exception as e:
            print(f"  ERREUR: {e}")
            logger.exception("Erreur generation PDF")
            return 1

    elif args.dry_run:
        print("\n" + "-" * 50)
        print("ETAPE 7: Generation PDF IGNOREE (--dry-run)")
        print("-" * 50)

    # Resume
    print("\n" + "=" * 70)
    print("RESUME")
    print("=" * 70)
    print(f"  PDF: {args.pdf.name}")
    print(f"  Pages: {pdf_info['page_count']}")
    print(f"  Chapitres detectes: {len(chapters)}")
    print(f"  Sujets CSV: {len(csv_entries)}")
    if not args.skip_ai:
        print(f"  Correspondances: {len(matched_analyses)}")
    if output_path:
        print(f"  Fichier genere: {output_path}")

    print("\nTermine.")
    return 0


async def cmd_analyze_fonts(args) -> int:
    """Execute la commande analyze-fonts."""
    if not args.pdf.exists():
        print(f"ERREUR: Fichier PDF introuvable: {args.pdf}")
        return 1

    print("=" * 70)
    print("JurisAnnotate - Analyse des tailles de police")
    print("=" * 70)
    print(f"\nFichier: {args.pdf}")

    pdf_bytes = args.pdf.read_bytes()

    try:
        analysis = analyze_font_sizes(pdf_bytes)
    except Exception as e:
        print(f"ERREUR: {e}")
        return 1

    print(f"\nTaille minimale: {analysis['min_size']}")
    print(f"Taille maximale: {analysis['max_size']}")
    print(f"Taille suggeree pour titres: {analysis['suggested_title_size']}")

    print("\n" + "-" * 50)
    print("TAILLES DE POLICE")
    print("-" * 50)

    for size, data in sorted(analysis["font_sizes"].items()):
        print(f"\n  {size} pt ({data['count']} occurrences)")
        if args.detailed and data["examples"]:
            for example in data["examples"]:
                print(f"    - {example}")

    print("\n" + "-" * 50)
    print("CONSEIL")
    print("-" * 50)
    print(f"  Pour traiter ce document, essayez:")
    print(f"  juris process fichier.pdf fichier.csv --min-font-size {analysis['suggested_title_size']}")

    return 0


async def cmd_preview(args) -> int:
    """Execute la commande preview."""
    if not args.pdf.exists():
        print(f"ERREUR: Fichier PDF introuvable: {args.pdf}")
        return 1

    min_font_size = args.min_font_size or settings.default_min_title_font_size

    print("=" * 70)
    print("JurisAnnotate - Apercu des chapitres")
    print("=" * 70)
    print(f"\nFichier: {args.pdf}")
    print(f"Taille police min.: {min_font_size}")

    pdf_bytes = args.pdf.read_bytes()

    try:
        pdf_info = get_pdf_info(pdf_bytes)
        chapters = extract_chapters(pdf_bytes, min_title_font_size=min_font_size)
    except Exception as e:
        print(f"ERREUR: {e}")
        return 1

    print(f"\nNombre de pages: {pdf_info['page_count']}")
    print(f"Chapitres detectes: {len(chapters)}")

    if pdf_info.get("metadata"):
        meta = pdf_info["metadata"]
        if meta.get("title"):
            print(f"Titre: {meta['title']}")
        if meta.get("author"):
            print(f"Auteur: {meta['author']}")

    print("\n" + "-" * 50)
    print("CHAPITRES")
    print("-" * 50)

    if not chapters:
        print(f"\n  Aucun chapitre detecte avec une police >= {min_font_size}")
        print("  Utilisez 'juris analyze-fonts' pour voir les tailles disponibles.")
    else:
        for i, chapter in enumerate(chapters):
            print(f"\n  {i + 1}. {chapter.title}")
            print(f"     Police: {chapter.title_font_size} pt")
            print(f"     Pages: {chapter.start_page + 1}-{chapter.end_page + 1}")
            content_preview = chapter.content[:200].replace("\n", " ")
            print(f"     Apercu: {content_preview}...")

    return 0


async def async_main() -> int:
    """Point d'entree async."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    # Configuration du debug
    if args.debug:
        settings.debug = True

    setup_logging()

    # Dispatch des commandes
    if args.command == "process":
        return await cmd_process(args)
    elif args.command == "analyze-fonts":
        return await cmd_analyze_fonts(args)
    elif args.command == "preview":
        return await cmd_preview(args)
    else:
        parser.print_help()
        return 1


def main():
    """Point d'entree principal."""
    sys.exit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
