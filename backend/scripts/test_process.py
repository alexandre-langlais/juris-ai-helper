#!/usr/bin/env python3
"""
Script de test et debug pour la fonction process_pdf.

Usage:
    uv run python scripts/test_process.py <pdf_file> <csv_file> [options]

Exemples:
    uv run python scripts/test_process.py contrat.pdf clauses.csv
    uv run python scripts/test_process.py contrat.pdf clauses.csv --output resultat.pdf
    uv run python scripts/test_process.py contrat.pdf clauses.csv --dry-run
    uv run python scripts/test_process.py contrat.pdf clauses.csv --debug
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Ajouter le dossier parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.logging_config import setup_logging, get_logger
from app.config import settings
from app.services.pdf_service import extract_text_blocks, add_annotations_to_pdf, get_pdf_info
from app.services.csv_service import parse_csv
from app.services.ollama_service import analyze_all_blocks, check_ollama_health


def parse_args():
    parser = argparse.ArgumentParser(
        description="Test et debug du traitement PDF JurisAnnotate",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  %(prog)s contrat.pdf clauses.csv
  %(prog)s contrat.pdf clauses.csv --output resultat.pdf
  %(prog)s contrat.pdf clauses.csv --dry-run --debug
  %(prog)s contrat.pdf clauses.csv --show-blocks
        """,
    )
    parser.add_argument("pdf", type=Path, help="Fichier PDF a traiter")
    parser.add_argument("csv", type=Path, help="Fichier CSV avec sujets et commentaires")
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Fichier PDF de sortie (defaut: <pdf>_annote.pdf)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyser sans generer le PDF annote",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Activer les logs de debug",
    )
    parser.add_argument(
        "--show-blocks",
        action="store_true",
        help="Afficher tous les blocs de texte extraits",
    )
    parser.add_argument(
        "--show-csv",
        action="store_true",
        help="Afficher le contenu du CSV parse",
    )
    parser.add_argument(
        "--skip-ai",
        action="store_true",
        help="Ignorer l'analyse IA (test extraction uniquement)",
    )
    parser.add_argument(
        "--ollama-url",
        type=str,
        help=f"URL Ollama (defaut: {settings.ollama_base_url})",
    )
    parser.add_argument(
        "--model",
        type=str,
        help=f"Modele Ollama (defaut: {settings.ollama_model})",
    )
    return parser.parse_args()


async def main():
    args = parse_args()

    # Configuration du debug
    if args.debug:
        settings.debug = True

    setup_logging()
    logger = get_logger("test_process")

    # Override des settings si specifie
    if args.ollama_url:
        settings.ollama_base_url = args.ollama_url
    if args.model:
        settings.ollama_model = args.model

    print("=" * 60)
    print("JurisAnnotate - Test de traitement PDF")
    print("=" * 60)

    # Verification des fichiers
    if not args.pdf.exists():
        print(f"ERREUR: Fichier PDF introuvable: {args.pdf}")
        sys.exit(1)

    if not args.csv.exists():
        print(f"ERREUR: Fichier CSV introuvable: {args.csv}")
        sys.exit(1)

    print(f"\nFichier PDF: {args.pdf}")
    print(f"Fichier CSV: {args.csv}")
    print(f"Ollama URL: {settings.ollama_base_url}")
    print(f"Modele: {settings.ollama_model}")

    # Lecture des fichiers
    print("\n" + "-" * 40)
    print("ETAPE 1: Lecture des fichiers")
    print("-" * 40)

    pdf_bytes = args.pdf.read_bytes()
    csv_bytes = args.csv.read_bytes()

    print(f"  PDF: {len(pdf_bytes):,} bytes ({len(pdf_bytes) / 1024 / 1024:.2f} Mo)")
    print(f"  CSV: {len(csv_bytes):,} bytes")

    # Informations PDF
    print("\n" + "-" * 40)
    print("ETAPE 2: Analyse du PDF")
    print("-" * 40)

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
        sys.exit(1)

    # Extraction des blocs
    print("\n" + "-" * 40)
    print("ETAPE 3: Extraction des blocs de texte")
    print("-" * 40)

    try:
        text_blocks = extract_text_blocks(pdf_bytes)
        print(f"  Blocs extraits: {len(text_blocks)}")

        # Stats par page
        pages = {}
        for block in text_blocks:
            pages[block.page_number] = pages.get(block.page_number, 0) + 1
        print(f"  Repartition: {dict(sorted(pages.items()))}")

        # Blocs analysables (>= 20 caracteres)
        analyzable = [b for b in text_blocks if len(b.text) >= 20]
        print(f"  Blocs analysables (>= 20 car.): {len(analyzable)}")

        if args.show_blocks:
            print("\n  --- BLOCS DE TEXTE ---")
            for i, block in enumerate(text_blocks):
                text_preview = block.text[:80].replace("\n", " ")
                if len(block.text) > 80:
                    text_preview += "..."
                print(f"  [{i}] Page {block.page_number} ({len(block.text)} car.): {text_preview}")

    except Exception as e:
        print(f"  ERREUR: {e}")
        logger.exception("Erreur extraction PDF")
        sys.exit(1)

    # Parse du CSV
    print("\n" + "-" * 40)
    print("ETAPE 4: Parsing du CSV")
    print("-" * 40)

    try:
        csv_entries = parse_csv(csv_bytes)
        print(f"  Sujets trouves: {len(csv_entries)}")

        if args.show_csv:
            print("\n  --- CONTENU CSV ---")
            for i, entry in enumerate(csv_entries):
                print(f"  [{i}] Sujet: {entry.sujet}")
                print(f"      Commentaire: {entry.commentaire[:60]}...")

        else:
            for i, entry in enumerate(csv_entries):
                print(f"  [{i}] {entry.sujet}")

    except ValueError as e:
        print(f"  ERREUR: {e}")
        sys.exit(1)

    # Verification Ollama
    if not args.skip_ai:
        print("\n" + "-" * 40)
        print("ETAPE 5: Verification connexion Ollama")
        print("-" * 40)

        is_healthy = await check_ollama_health()
        if is_healthy:
            print(f"  Ollama: CONNECTE")
        else:
            print(f"  Ollama: NON DISPONIBLE")
            print(f"  Verifiez que Ollama est lance sur {settings.ollama_base_url}")
            print(f"  Utilisez --skip-ai pour tester sans l'IA")
            sys.exit(1)

        # Analyse IA
        print("\n" + "-" * 40)
        print("ETAPE 6: Analyse IA des blocs")
        print("-" * 40)

        print(f"  Demarrage de l'analyse de {len(analyzable)} blocs...")
        print(f"  (Cela peut prendre plusieurs minutes)\n")

        try:
            matches = await analyze_all_blocks(text_blocks, csv_entries)
            print(f"\n  Correspondances trouvees: {len(matches)}")

            if matches:
                print("\n  --- MATCHES ---")
                for i, match in enumerate(matches):
                    print(f"  [{i}] Page {match.text_block.page_number}: {match.csv_entry.sujet}")
                    text_preview = match.text_block.text[:60].replace("\n", " ")
                    print(f"      Texte: {text_preview}...")

        except Exception as e:
            print(f"  ERREUR: {e}")
            logger.exception("Erreur analyse IA")
            sys.exit(1)

    else:
        print("\n" + "-" * 40)
        print("ETAPE 5-6: Analyse IA IGNOREE (--skip-ai)")
        print("-" * 40)
        matches = []

    # Generation du PDF
    if not args.dry_run and matches:
        print("\n" + "-" * 40)
        print("ETAPE 7: Generation du PDF annote")
        print("-" * 40)

        try:
            annotated_pdf = add_annotations_to_pdf(pdf_bytes, matches)

            # Fichier de sortie
            if args.output:
                output_path = args.output
            else:
                output_path = args.pdf.with_stem(args.pdf.stem + "_annote")

            output_path.write_bytes(annotated_pdf)
            print(f"  PDF annote: {output_path}")
            print(f"  Taille: {len(annotated_pdf):,} bytes")
            print(f"  Annotations: {len(matches)}")

        except Exception as e:
            print(f"  ERREUR: {e}")
            logger.exception("Erreur generation PDF")
            sys.exit(1)

    elif args.dry_run:
        print("\n" + "-" * 40)
        print("ETAPE 7: Generation PDF IGNOREE (--dry-run)")
        print("-" * 40)

    # Resume
    print("\n" + "=" * 60)
    print("RESUME")
    print("=" * 60)
    print(f"  PDF: {args.pdf.name}")
    print(f"  Pages: {pdf_info['page_count']}")
    print(f"  Blocs de texte: {len(text_blocks)}")
    print(f"  Sujets CSV: {len(csv_entries)}")
    if not args.skip_ai:
        print(f"  Correspondances: {len(matches)}")
    if not args.dry_run and matches:
        print(f"  Fichier genere: {output_path}")

    print("\nTermine.")


if __name__ == "__main__":
    asyncio.run(main())
