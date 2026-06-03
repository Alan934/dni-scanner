"""
Autenticación HTTP Basic para los endpoints protegidos.

Las credenciales se definen por variables de entorno:
    API_USERNAME  (default: "admin")
    API_PASSWORD  (sin default: si no se define, la API rechaza todo)

La comparación usa secrets.compare_digest para evitar ataques de temporización.
"""

import os
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

_basic = HTTPBasic()

# Las credenciales se leen al iniciar el proceso.
_USERNAME = os.environ.get("API_USERNAME", "admin")
_PASSWORD = os.environ.get("API_PASSWORD")


def require_auth(credentials: HTTPBasicCredentials = Depends(_basic)) -> str:
    """
    Dependencia de FastAPI que valida las credenciales HTTP Basic.
    Devuelve el nombre de usuario autenticado o lanza 401.
    """
    if not _PASSWORD:
        # Falla cerrada: si no se configuró la contraseña, no se autoriza nada.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Autenticación no configurada (falta API_PASSWORD).",
        )

    user_ok = secrets.compare_digest(credentials.username, _USERNAME)
    pass_ok = secrets.compare_digest(credentials.password, _PASSWORD)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
