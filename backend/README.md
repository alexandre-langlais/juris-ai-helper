# JurisAnnotate Backend

Backend FastAPI pour l'annotation automatique de contrats PDF par IA.

L'application analyse les chapitres d'un PDF (détectés via la taille de police des titres) et les compare aux sujets définis dans un fichier CSV. Pour chaque correspondance trouvée, une annotation est ajoutée au PDF avec le commentaire associé.

## Prerequis

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (gestionnaire de paquets Python)
- [Ollama](https://ollama.ai/) avec un modele LLM (llama3, mistral, etc.)

### Installation de uv

```bash
# Linux / macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# Ou avec pip
pip install uv
```

## Installation

```bash
cd backend

# Creer l'environnement virtuel et installer les dependances
uv sync

# Ou pour installer avec les dependances de developpement
uv sync --dev
```

## Lancement

### Mode developpement

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Mode production

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Configuration

Copiez le fichier `.env.example` vers `.env` et ajustez les valeurs:

```bash
cp .env.example .env
```

Variables disponibles:

| Variable | Description | Defaut |
|----------|-------------|--------|
| `JURIS_DEBUG` | Mode debug | `false` |
| `JURIS_OLLAMA_BASE_URL` | URL du service Ollama | `http://ollama-service:11434` |
| `JURIS_OLLAMA_MODEL` | Modele Ollama a utiliser | `llama3` |
| `JURIS_OLLAMA_TIMEOUT` | Timeout des requetes Ollama (secondes) | `120` |
| `JURIS_MAX_PDF_SIZE_MB` | Taille max des PDF (Mo) | `50` |
| `JURIS_MAX_CSV_SIZE_MB` | Taille max des CSV (Mo) | `5` |
| `JURIS_DEFAULT_MIN_TITLE_FONT_SIZE` | Taille de police min. pour titres de chapitres | `14.0` |

## Endpoints API

| Methode | Route | Description |
|---------|-------|-------------|
| `GET` | `/health` | Verification de sante de l'API |
| `GET` | `/api/ollama/health` | Verification connexion Ollama |
| `POST` | `/api/process` | Traitement PDF + CSV → PDF annote + analyses |
| `POST` | `/api/preview` | Apercu des chapitres d'un PDF |
| `POST` | `/api/analyze-fonts` | Analyse des tailles de police du PDF |

### Endpoint `/api/process`

Traite un PDF et retourne:
- Le PDF annote (encode en base64)
- Les analyses detaillees de chaque chapitre avec **explications du LLM**

```bash
curl -X POST http://localhost:8000/api/process \
  -F "pdf=@contrat.pdf" \
  -F "csv=@clauses.csv" \
  -F "min_title_font_size=14.0"
```

**Reponse exemple:**

```json
{
  "pdf_base64": "JVBERi0xLjQK...",
  "pdf_filename": "contrat_annote.pdf",
  "total_chapters": 8,
  "matched_chapters": 3,
  "analyses": [
    {
      "chapter_title": "1. Confidentialite",
      "chapter_pages": "2-3",
      "matched": true,
      "matched_subject": "Clause de confidentialite",
      "comment_added": "Verifier la duree...",
      "explanation": "Ce chapitre traite explicitement de la confidentialite des informations echangees entre les parties. Le titre et le contenu mentionnent les obligations de secret professionnel."
    },
    {
      "chapter_title": "2. Prix et paiement",
      "chapter_pages": "4-5",
      "matched": false,
      "explanation": "Ce chapitre concerne les modalites de paiement et la tarification. Il ne correspond a aucun des sujets recherches dans le fichier CSV."
    }
  ]
}
```

### Format du fichier CSV

Le fichier CSV doit contenir les colonnes `sujet` et `commentaire`:

```csv
sujet,commentaire
Clause de confidentialite,Verifier la duree de confidentialite (standard: 5 ans)
Clause de non-concurrence,Attention: clause potentiellement abusive si trop restrictive
Conditions de paiement,S'assurer que les delais sont conformes a la politique interne
```

## CLI

JurisAnnotate inclut une interface en ligne de commande.

### Commandes disponibles

```bash
# Afficher l'aide
uv run juris --help

# Aide pour une commande specifique
uv run juris process --help
```

### Commande `process` - Traiter un PDF

```bash
# Traitement complet
uv run juris process contrat.pdf clauses.csv

# Avec taille de police personnalisee
uv run juris process contrat.pdf clauses.csv --min-font-size 12

# Fichier de sortie specifique
uv run juris process contrat.pdf clauses.csv --output resultat.pdf

# Exporter les analyses en JSON
uv run juris process contrat.pdf clauses.csv --json

# Test sans IA (extraction chapitres uniquement)
uv run juris process contrat.pdf clauses.csv --skip-ai --show-chapters

# Dry-run avec debug
uv run juris process contrat.pdf clauses.csv --dry-run --debug
```

**Options:**

| Option | Description |
|--------|-------------|
| `-o, --output` | Fichier PDF de sortie |
| `--min-font-size` | Taille de police min. pour les titres (defaut: 14.0) |
| `--dry-run` | Analyser sans generer le PDF |
| `--show-chapters` | Afficher les chapitres extraits |
| `--show-csv` | Afficher le contenu du CSV |
| `--skip-ai` | Ignorer l'analyse IA |
| `--json` | Exporter les analyses en JSON |
| `--ollama-url` | URL du service Ollama |
| `--model` | Modele Ollama a utiliser |
| `--debug` | Activer les logs de debug |

**Sortie avec explications:**

```
--- ANALYSES DETAILLEES ---

  [1] MATCH - 'Clause de confidentialite'
      Pages: 2-3
      Sujet matche: Clause de confidentialite
      Explication LLM:
        Ce chapitre traite explicitement de la confidentialite.
        Le contenu mentionne les obligations de secret professionnel.

  [2] --- - 'Conditions financieres'
      Pages: 4-5
      Explication LLM:
        Ce chapitre concerne les modalites de paiement.
        Il ne correspond a aucun des sujets recherches.
```

### Commande `analyze-fonts` - Analyser les polices

Utile pour determiner la taille de police a utiliser.

```bash
# Analyse basique
uv run juris analyze-fonts contrat.pdf

# Avec exemples de texte pour chaque taille
uv run juris analyze-fonts contrat.pdf --detailed
```

### Commande `preview` - Previsualiser les chapitres

```bash
# Apercu avec taille par defaut
uv run juris preview contrat.pdf

# Avec taille personnalisee
uv run juris preview contrat.pdf --min-font-size 12
```

### Workflow recommande

```bash
# 1. Analyser les tailles de police
uv run juris analyze-fonts contrat.pdf --detailed

# 2. Previsualiser les chapitres detectes
uv run juris preview contrat.pdf --min-font-size 14

# 3. Traiter le document
uv run juris process contrat.pdf clauses.csv --min-font-size 14
```

## Tests

### Tests unitaires

```bash
uv run pytest
```

## Docker

```bash
docker build -t juris-backend .
docker run -p 8000:8000 juris-backend
```
