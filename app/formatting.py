"""Utilidades de formateo de texto para datos extraídos del documento."""

# Partículas que en nombres/apellidos en español suelen ir en minúscula
# cuando están en medio (de, la, del...), pero capitalizadas si abren el campo.
_LOWERCASE_PARTICLES = {"de", "del", "la", "las", "los", "y", "da", "do", "dos", "van", "von"}


def capitalize_name(text: str) -> str:
    """
    Convierte un nombre/apellido de MAYÚSCULAS a formato Título.

    Ejemplos:
        "ALAN GABRIEL"      -> "Alan Gabriel"
        "FREDEZ MATURANA"   -> "Fredez Maturana"
        "DE LA TORRE"       -> "de la Torre"  (partículas en minúscula salvo al inicio)
        "JOSE LUIS"         -> "Jose Luis"

    Maneja también guiones internos: "ANA-MARIA" -> "Ana-Maria".
    """
    if not text:
        return text

    words = text.strip().split()
    result = []
    for i, word in enumerate(words):
        lower = word.lower()
        # Las partículas van en minúscula salvo cuando abren el campo.
        if i > 0 and lower in _LOWERCASE_PARTICLES:
            result.append(lower)
        else:
            result.append(_capitalize_word(lower))
    return " ".join(result)


def _capitalize_word(word: str) -> str:
    """Capitaliza una palabra respetando guiones internos (Ana-Maria)."""
    return "-".join(part.capitalize() for part in word.split("-"))
