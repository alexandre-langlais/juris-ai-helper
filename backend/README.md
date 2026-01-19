# JurisAnnotate Backend

Backend FastAPI pour l'annotation automatique de contrats PDF par IA.

## Prerequis

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (gestionnaire de paquets Python)

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

## Endpoints API

| Methode | Route | Description |
|---------|-------|-------------|
| `GET` | `/health` | Verification de sante de l'API |
| `GET` | `/api/ollama/health` | Verification connexion Ollama |
| `POST` | `/api/process` | Traitement PDF + CSV → PDF annote |
| `POST` | `/api/preview` | Informations sur un PDF |

### Exemple d'utilisation

```bash
# Verifier que l'API fonctionne
curl http://localhost:8000/health

# Traiter un PDF
curl -X POST http://localhost:8000/api/process \
  -F "pdf=@contrat.pdf" \
  -F "csv=@annotations.csv" \
  -o contrat_annote.pdf
```

### Format du fichier CSV

Le fichier CSV doit contenir les colonnes `sujet` et `commentaire`:

```csv
sujet,commentaire
Clause de confidentialite,Verifier la duree de confidentialite (standard: 5 ans)
Clause de non-concurrence,Attention: clause potentiellement abusive si trop restrictive
Conditions de paiement,S'assurer que les delais sont conformes a la politique interne
```

## Tests

### Tests unitaires

```bash
uv run pytest
```

### Script de test CLI

Un script de test en ligne de commande est disponible pour debuguer le traitement PDF:

```bash
# Test complet avec un PDF et CSV
uv run python scripts/test_process.py contrat.pdf scripts/exemple_clauses.csv

# Test sans l'IA (extraction PDF uniquement)
uv run python scripts/test_process.py contrat.pdf scripts/exemple_clauses.csv --skip-ai

# Voir tous les blocs de texte extraits
uv run python scripts/test_process.py contrat.pdf scripts/exemple_clauses.csv --show-blocks --skip-ai

# Mode debug avec logs detailles
uv run python scripts/test_process.py contrat.pdf scripts/exemple_clauses.csv --debug

# Dry-run (analyse sans generer le PDF)
uv run python scripts/test_process.py contrat.pdf scripts/exemple_clauses.csv --dry-run

# Specifier l'URL Ollama et le modele
uv run python scripts/test_process.py contrat.pdf scripts/exemple_clauses.csv \
  --ollama-url http://localhost:11434 --model mistral
```

Options disponibles:
| Option | Description |
|--------|-------------|
| `-o, --output` | Fichier PDF de sortie |
| `--dry-run` | Analyser sans generer le PDF |
| `--debug` | Activer les logs de debug |
| `--show-blocks` | Afficher les blocs de texte extraits |
| `--show-csv` | Afficher le contenu du CSV |
| `--skip-ai` | Ignorer l'analyse IA |
| `--ollama-url` | URL du service Ollama |
| `--model` | Modele Ollama a utiliser |

## Docker

```bash
docker build -t juris-backend .
docker run -p 8000:8000 juris-backend
```
