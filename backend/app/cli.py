#!/usr/bin/env python3
"""
JurisAnnotate CLI - Outil en ligne de commande pour l'annotation de contrats PDF.

Usage:
    juris process <pdf> <csv> [options]
    juris preview <pdf>
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
    get_toc_preview,
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

    # Sous-commande: preview
    preview_parser = subparsers.add_parser(
        "preview",
        help="Previsualiser les chapitres d'un PDF (via table des matieres)",
        epilog="""
Exemple:
  juris preview contrat.pdf
        """,
    )
    preview_parser.add_argument("pdf", type=Path, help="Fichier PDF a analyser")

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

    print("=" * 70)
    print("JurisAnnotate - Traitement PDF")
    print("=" * 70)
    print(f"\nFichier PDF: {args.pdf}")
    print(f"Fichier CSV: {args.csv}")
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

    # Extraction des chapitres via table des matieres
    print("\n" + "-" * 50)
    print("ETAPE 3: Extraction des chapitres (via table des matieres)")
    print("-" * 50)

    try:
        chapters = extract_chapters(pdf_bytes)
        print(f"  Chapitres extraits: {len(chapters)}")

        if not chapters:
            print("\n  ATTENTION: Aucun chapitre detecte.")
            print("  Assurez-vous que le PDF contient une table des matieres.")
            print("  Utilisez 'juris preview' pour verifier la detection.")
            return 1

        if args.show_chapters:
            print("\n  --- CHAPITRES ---")
            for i, chapter in enumerate(chapters):
                print(f"\n  [{i + 1}] '{chapter.title}'")
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


async def cmd_preview(args) -> int:
    """Execute la commande preview."""
    if not args.pdf.exists():
        print(f"ERREUR: Fichier PDF introuvable: {args.pdf}")
        return 1

    print("=" * 70)
    print("JurisAnnotate - Apercu des chapitres (table des matieres)")
    print("=" * 70)
    print(f"\nFichier: {args.pdf}")

    pdf_bytes = args.pdf.read_bytes()

    try:
        pdf_info = get_pdf_info(pdf_bytes)
        toc_entries = get_toc_preview(pdf_bytes)
    except Exception as e:
        print(f"ERREUR: {e}")
        return 1

    print(f"\nNombre de pages: {pdf_info['page_count']}")
    print(f"Chapitres detectes: {len(toc_entries)}")

    if pdf_info.get("metadata"):
        meta = pdf_info["metadata"]
        if meta.get("title"):
            print(f"Titre: {meta['title']}")
        if meta.get("author"):
            print(f"Auteur: {meta['author']}")

    print("\n" + "-" * 50)
    print("TABLE DES MATIERES DETECTEE")
    print("-" * 50)

    if not toc_entries:
        print("\n  Aucune table des matieres detectee.")
        print("  Assurez-vous que le document contient un sommaire avec les titres")
        print("  de chapitres et leurs numeros de page.")
    else:
        for i, entry in enumerate(toc_entries):
            print(f"\n  {i + 1}. {entry['title']}")
            print(f"     Page: {entry['page']}")

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
