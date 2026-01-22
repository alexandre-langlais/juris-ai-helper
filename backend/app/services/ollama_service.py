import json
import httpx

from app.config import settings
from app.schemas.models import CSVEntry, Chapter, ChapterAnalysis
from app.logging_config import get_logger

logger = get_logger(__name__)


SYSTEM_PROMPT = """Tu es un assistant juridique spécialisé dans l'analyse de contrats.
Ta tâche est d'analyser un chapitre complet d'un contrat et de déterminer s'il correspond à l'un des sujets fournis.

Un chapitre comprend un titre et son contenu textuel complet.

RÈGLES STRICTES:
1. Réponds UNIQUEMENT avec un JSON valide.
2. Le JSON doit contenir les champs suivants:
   - "match": true si le chapitre correspond à un sujet, false sinon
   - "sujet_index": l'index (0-based) du sujet correspondant, ou null si pas de correspondance
   - "explanation": une explication détaillée en français de ta décision (2-3 phrases)

3. Format de réponse:
   Si correspondance: {"match": true, "sujet_index": <index>, "explanation": "<explication>"}
   Si pas de correspondance: {"match": false, "sujet_index": null, "explanation": "<explication>"}

4. Analyse le titre ET le contenu pour déterminer la correspondance.
5. Ne fais correspondre que si le chapitre traite CLAIREMENT et DIRECTEMENT du sujet.
6. En cas de doute, réponds avec match: false.
7. L'explication doit justifier clairement pourquoi tu as fait ce choix."""


async def check_ollama_health() -> bool:
    """
    Vérifie si le service Ollama est accessible.

    Returns:
        True si Ollama répond, False sinon
    """
    try:
        logger.debug(f"Verification connexion Ollama sur {settings.ollama_base_url}")
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.ollama_base_url}/api/tags")
            if response.status_code == 200:
                logger.debug("Ollama accessible")
                return True
            logger.warning(f"Ollama a repondu avec le code {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Erreur connexion Ollama: {e}")
        return False


async def analyze_chapter(
    chapter: Chapter, csv_entries: list[CSVEntry], model: str | None = None
) -> ChapterAnalysis:
    """
    Analyse un chapitre pour trouver une correspondance avec les sujets CSV.

    Args:
        chapter: Chapitre à analyser (titre + contenu)
        csv_entries: Liste des entrées CSV (sujets/commentaires)
        model: Modèle LLM à utiliser (utilise le modèle par défaut si None)

    Returns:
        ChapterAnalysis avec le résultat de l'analyse et l'explication
    """
    effective_model = model or settings.ollama_model
    # Construction de la liste des sujets pour le prompt
    sujets_list = "\n".join(
        [f"{i}. {entry.sujet}" for i, entry in enumerate(csv_entries)]
    )

    user_prompt = f"""SUJETS À RECHERCHER:
{sujets_list}

CHAPITRE DU CONTRAT À ANALYSER:

TITRE: {chapter.title}

CONTENU:
\"\"\"
{chapter.content}
\"\"\"

Analyse ce chapitre complet (titre + contenu) et détermine s'il correspond à l'un des sujets ci-dessus.
Fournis une explication détaillée de ta décision.
Réponds uniquement avec le JSON demandé."""

    try:
        async with httpx.AsyncClient(
            timeout=settings.ollama_timeout
        ) as client:
            response = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": effective_model,
                    "prompt": user_prompt,
                    "system": SYSTEM_PROMPT,
                    "stream": False,
                    "format": "json",
                },
            )

            if response.status_code != 200:
                logger.warning(f"Ollama a repondu avec le code {response.status_code}")
                return ChapterAnalysis(
                    chapter=chapter,
                    matched=False,
                    csv_entry=None,
                    explanation=f"Erreur: Ollama a répondu avec le code {response.status_code}",
                )

            result = response.json()
            ai_response = result.get("response", "")
            logger.debug(f"Reponse IA: {ai_response[:200]}...")

            # Parse de la réponse JSON de l'IA
            try:
                parsed = json.loads(ai_response)
                explanation = parsed.get("explanation", "Aucune explication fournie par le LLM.")

                if parsed.get("match") and parsed.get("sujet_index") is not None:
                    sujet_index = int(parsed["sujet_index"])
                    if 0 <= sujet_index < len(csv_entries):
                        matched_entry = csv_entries[sujet_index]
                        logger.info(f"Match trouve: '{matched_entry.sujet}' pour le chapitre '{chapter.title}'")
                        return ChapterAnalysis(
                            chapter=chapter,
                            matched=True,
                            csv_entry=matched_entry,
                            explanation=explanation,
                        )
                    else:
                        logger.warning(f"Index de sujet invalide: {sujet_index}")
                        return ChapterAnalysis(
                            chapter=chapter,
                            matched=False,
                            csv_entry=None,
                            explanation=f"Erreur: index de sujet invalide ({sujet_index}). {explanation}",
                        )

                # Pas de correspondance
                logger.debug(f"Pas de match pour le chapitre '{chapter.title}'")
                return ChapterAnalysis(
                    chapter=chapter,
                    matched=False,
                    csv_entry=None,
                    explanation=explanation,
                )

            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(f"Erreur parsing reponse IA: {e}")
                return ChapterAnalysis(
                    chapter=chapter,
                    matched=False,
                    csv_entry=None,
                    explanation=f"Erreur lors du parsing de la réponse IA: {e}",
                )

    except httpx.TimeoutException:
        logger.warning(f"Timeout Ollama apres {settings.ollama_timeout}s")
        return ChapterAnalysis(
            chapter=chapter,
            matched=False,
            csv_entry=None,
            explanation=f"Timeout: le LLM n'a pas répondu dans les {settings.ollama_timeout} secondes.",
        )
    except Exception as e:
        logger.error(f"Erreur lors de l'appel Ollama: {e}")
        return ChapterAnalysis(
            chapter=chapter,
            matched=False,
            csv_entry=None,
            explanation=f"Erreur lors de l'appel au LLM: {e}",
        )


async def analyze_all_chapters(
    chapters: list[Chapter], csv_entries: list[CSVEntry], model: str | None = None
) -> list[ChapterAnalysis]:
    """
    Analyse tous les chapitres et retourne les résultats avec explications.

    Args:
        chapters: Liste des chapitres extraits du PDF
        csv_entries: Liste des entrées CSV
        model: Modèle LLM à utiliser (utilise le modèle par défaut si None)

    Returns:
        Liste des analyses pour chaque chapitre
    """
    analyses: list[ChapterAnalysis] = []
    total_chapters = len(chapters)

    logger.info(f"Analyse de {total_chapters} chapitres")

    for i, chapter in enumerate(chapters, 1):
        logger.debug(f"Analyse chapitre {i}/{total_chapters}: '{chapter.title}'")
        analysis = await analyze_chapter(chapter, csv_entries, model)
        analyses.append(analysis)

        # Log de progression tous les 5 chapitres
        if i % 5 == 0:
            matched_count = sum(1 for a in analyses if a.matched)
            logger.info(f"Progression: {i}/{total_chapters} chapitres analyses, {matched_count} matches trouves")

    matched_count = sum(1 for a in analyses if a.matched)
    logger.info(f"Analyse terminee: {matched_count} correspondances sur {total_chapters} chapitres")
    return analyses
