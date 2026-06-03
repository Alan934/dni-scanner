"""
Validaciones de negocio sobre los datos extraídos del documento.

Las fechas se comparan contra la fecha actual en Mendoza, Argentina
(zona horaria America/Argentina/Mendoza), que es donde se usan los sistemas.
"""

from datetime import date, datetime
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo

# Zona horaria de referencia para todas las comparaciones de fecha.
LOCAL_TZ = ZoneInfo("America/Argentina/Mendoza")


def today_local() -> date:
    """Fecha de hoy en la zona horaria de Mendoza."""
    return datetime.now(LOCAL_TZ).date()


def _parse_iso(value: Optional[str]) -> Optional[date]:
    """Convierte 'YYYY-MM-DD' a date, o None si no es parseable."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def validate_document(data: dict) -> Tuple[bool, bool, List[str]]:
    """
    Aplica las validaciones de negocio sobre los datos del documento.

    Devuelve una tupla (approved, is_expired, validations):
      - approved: False solo ante un problema bloqueante.
      - is_expired: True si la fecha de vencimiento ya pasó.
      - validations: lista de mensajes (advertencias y/o motivos).
    """
    validations: List[str] = []
    today = today_local()

    # --- Vencimiento ---
    is_expired = False
    expiry = _parse_iso(data.get("expiryDate"))
    if expiry is None:
        validations.append("No se pudo determinar la fecha de vencimiento.")
    elif expiry < today:
        is_expired = True
        validations.append(f"El documento está vencido (venció el {expiry.isoformat()}).")

    # --- Coherencia de la fecha de nacimiento ---
    birth = _parse_iso(data.get("birthDate"))
    if birth is None:
        validations.append("No se pudo determinar la fecha de nacimiento.")
    elif birth > today:
        validations.append("La fecha de nacimiento es futura (dato inconsistente).")

    # --- Confianza del MRZ ---
    if not data.get("mrzValid", False):
        validations.append(
            "Los dígitos de control del MRZ no validaron al 100% "
            "(posible error de lectura OCR); revisar los datos."
        )

    # El documento vencido se aprueba igual pero queda marcado (decisión del cliente).
    approved = True
    return approved, is_expired, validations
