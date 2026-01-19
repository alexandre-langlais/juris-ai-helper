import csv
import io

from app.schemas.models import CSVEntry


def parse_csv(csv_bytes: bytes) -> list[CSVEntry]:
    """
    Parse un fichier CSV contenant les sujets et commentaires.

    Le CSV doit avoir les colonnes: sujet, commentaire
    La première ligne est considérée comme l'en-tête.

    Args:
        csv_bytes: Contenu binaire du fichier CSV

    Returns:
        Liste de CSVEntry

    Raises:
        ValueError: Si le format CSV est invalide
    """
    try:
        # Décodage du CSV (UTF-8 avec fallback Latin-1)
        try:
            content = csv_bytes.decode("utf-8")
        except UnicodeDecodeError:
            content = csv_bytes.decode("latin-1")

        # Lecture du CSV
        reader = csv.DictReader(io.StringIO(content))

        # Vérification des colonnes requises
        if reader.fieldnames is None:
            raise ValueError("Le fichier CSV est vide")

        # Normalisation des noms de colonnes (minuscules, sans espaces)
        normalized_fields = {
            field.lower().strip(): field for field in reader.fieldnames
        }

        # Recherche des colonnes sujet et commentaire
        sujet_col = None
        commentaire_col = None

        for normalized, original in normalized_fields.items():
            if normalized in ("sujet", "subject", "clause", "topic"):
                sujet_col = original
            elif normalized in ("commentaire", "comment", "annotation", "note"):
                commentaire_col = original

        if not sujet_col:
            raise ValueError(
                "Colonne 'sujet' non trouvée. "
                "Colonnes acceptées: sujet, subject, clause, topic"
            )
        if not commentaire_col:
            raise ValueError(
                "Colonne 'commentaire' non trouvée. "
                "Colonnes acceptées: commentaire, comment, annotation, note"
            )

        # Extraction des entrées
        entries: list[CSVEntry] = []
        for row in reader:
            sujet = row.get(sujet_col, "").strip()
            commentaire = row.get(commentaire_col, "").strip()

            if sujet and commentaire:
                entries.append(CSVEntry(sujet=sujet, commentaire=commentaire))

        if not entries:
            raise ValueError("Aucune entrée valide trouvée dans le CSV")

        return entries

    except csv.Error as e:
        raise ValueError(f"Erreur de parsing CSV: {e}")
