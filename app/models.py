"""Modelos Pydantic para las respuestas de la API."""

from typing import List, Optional

from pydantic import BaseModel, Field


class DocumentData(BaseModel):
    """Datos extraídos de un documento de identidad."""

    name: str = Field(..., description="Nombre(s) en formato Título", examples=["Alan Gabriel"])
    lastName: str = Field(..., description="Apellido(s) en formato Título", examples=["Sanjurjo"])
    dni: str = Field(..., description="Número de identificación nacional", examples=["42584758"])
    documentNumber: str = Field(..., description="Número de serie del documento")
    birthDate: Optional[str] = Field(None, description="Fecha de nacimiento (YYYY-MM-DD)")
    expiryDate: Optional[str] = Field(None, description="Fecha de vencimiento (YYYY-MM-DD)")
    sex: Optional[str] = Field(None, description="Sexo (M/F)")
    nationality: Optional[str] = Field(None, description="Nacionalidad (código ISO 3166-1 alfa-3)")
    country: Optional[str] = Field(None, description="País emisor (código ISO 3166-1 alfa-3)")
    documentType: str = Field(..., description="Tipo de documento (ID / PASSPORT / UNKNOWN)")
    mrzValid: bool = Field(..., description="True si los dígitos de control del MRZ validaron")
    isExpired: Optional[bool] = Field(None, description="True si el documento está vencido")


class ProcessResponse(BaseModel):
    """Respuesta del endpoint de procesamiento de documentos."""

    sessionId: Optional[str] = None
    status: str = Field(..., description="'approved' o 'rejected'", examples=["approved"])
    validations: List[str] = Field(
        default_factory=list,
        description="Lista de advertencias o motivos de rechazo",
    )
    data: DocumentData
