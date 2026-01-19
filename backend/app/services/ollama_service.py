import json
import httpx

from app.config import settings
from app.schemas.models import TextBlock, CSVEntry, AnnotationMatch
from app.logging_config import get_logger

logger = get_logger(__name__)


SYSTEM_PROMPT = """Tu es un assistant juridique spécialisé dans l'analyse de contrats.
Ta tâche est de déterminer si un bloc de texte d'un contrat correspond à l'un des sujets fournis.

RÈGLES STRICTES:
1. Réponds UNIQUEMENT avec un JSON valide.
2. Si le texte correspond à un sujet, réponds: {"match": true, "sujet_index": <index du sujet>}
3. Si le texte ne correspond à aucun sujet, réponds: {"match": false, "sujet_index": null}
4. Le sujet_index est l'index (0-based) du sujet dans la liste fournie.
5. Ne fais correspondre que si le texte traite CLAIREMENT et DIRECTEMENT du sujet.
6. En cas de doute, réponds {"match": false, "sujet_index": null}."""


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


async def analyze_text_block(
    text_block: TextBlock, csv_entries: list[CSVEntry]
) -> AnnotationMatch | None:
    """
    Analyse un bloc de texte pour trouver une correspondance avec les sujets CSV.

    Args:
        text_block: Bloc de texte à analyser
        csv_entries: Liste des entrées CSV (sujets/commentaires)

    Returns:
        AnnotationMatch si une correspondance est trouvée, None sinon
    """
    # Construction de la liste des sujets pour le prompt
    sujets_list = "\n".join(
        [f"{i}. {entry.sujet}" for i, entry in enumerate(csv_entries)]
    )

    user_prompt = f"""SUJETS À RECHERCHER:
{sujets_list}

TEXTE DU CONTRAT À ANALYSER:
\"\"\"
{text_block.text}
\"\"\"

Analyse ce texte et détermine s'il correspond à l'un des sujets ci-dessus.
Réponds uniquement avec le JSON demandé."""

    try:
        async with httpx.AsyncClient(
            timeout=settings.ollama_timeout
        ) as client:
            response = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": user_prompt,
                    "system": SYSTEM_PROMPT,
                    "stream": False,
                    "format": "json",
                },
            )

            if response.status_code != 200:
                logger.warning(f"Ollama a repondu avec le code {response.status_code}")
                return None

            result = response.json()
            ai_response = result.get("response", "")
            logger.debug(f"Reponse IA: {ai_response[:100]}...")

            # Parse de la réponse JSON de l'IA
            try:
                parsed = json.loads(ai_response)
                if parsed.get("match") and parsed.get("sujet_index") is not None:
                    sujet_index = int(parsed["sujet_index"])
                    if 0 <= sujet_index < len(csv_entries):
                        matched_sujet = csv_entries[sujet_index].sujet
                        logger.info(f"Match trouve: '{matched_sujet}' pour le bloc page {text_block.page_number}")
                        return AnnotationMatch(
                            text_block=text_block,
                            csv_entry=csv_entries[sujet_index],
                            confidence=1.0,
                        )
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(f"Erreur parsing reponse IA: {e}")
                return None

    except httpx.TimeoutException:
        logger.warning(f"Timeout Ollama apres {settings.ollama_timeout}s")
        return None
    except Exception as e:
        logger.error(f"Erreur lors de l'appel Ollama: {e}")
        return None

    return None


async def analyze_all_blocks(
    text_blocks: list[TextBlock], csv_entries: list[CSVEntry]
) -> list[AnnotationMatch]:
    """
    Analyse tous les blocs de texte pour trouver les correspondances.

    Args:
        text_blocks: Liste des blocs de texte extraits du PDF
        csv_entries: Liste des entrées CSV

    Returns:
        Liste des matches trouvés
    """
    matches: list[AnnotationMatch] = []
    blocks_to_analyze = [b for b in text_blocks if len(b.text) >= 20]
    total_blocks = len(blocks_to_analyze)

    logger.info(f"Analyse de {total_blocks} blocs de texte (ignores: {len(text_blocks) - total_blocks} blocs trop courts)")

    for i, block in enumerate(blocks_to_analyze, 1):
        logger.debug(f"Analyse bloc {i}/{total_blocks} (page {block.page_number})")
        match = await analyze_text_block(block, csv_entries)
        if match:
            matches.append(match)

        # Log de progression tous les 10 blocs
        if i % 10 == 0:
            logger.info(f"Progression: {i}/{total_blocks} blocs analyses, {len(matches)} matches trouves")

    logger.info(f"Analyse terminee: {len(matches)} correspondances sur {total_blocks} blocs")
    return matches
