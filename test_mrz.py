"""
Test aislado del parser MRZ. Simula la salida del OCR (lista de líneas de texto)
para los 3 documentos de prueba y verifica que parse_mrz extrae bien los datos.

Ejecutar dentro del contenedor:
    docker compose run --rm api python test_mrz.py
"""
from main import parse_mrz

# --- Caso 1: DNI argentino (dorso) + ruido del frente ---
arg_lines = [
    # Ruido del frente que NO debe confundir al parser:
    "REPUBLICA ARGENTINA - MERCOSUR",
    "REGISTRO NACIONAL DE LAS PERSONAS",
    "Apellido / Surname",
    "SANJURJO",
    "Nombre / Name",
    "ALAN GABRIEL",
    "Fecha de nacimiento / Date of birth",
    "Lic. D. Rogelio Frigerio",
    "Ministro del Interior O. Pub. y Vivienda",
    # MRZ real (dorso):
    "IDARG43749627<0<<<<<<<<<<<<<<<<",
    "0111078M3201048ARG<<<<<<<<<<<<2",
    "SANJURJO<<ALAN<GABRIEL<<<<<<<<<",
]

# --- Caso 2: cédula chilena (dorso) ---
chl_lines = [
    "Nacio en: Santiago",
    "Profesion: ASISTENTE SOCIAL",
    "INCHLBA30111850A01<<<<<<<<<<<<<",
    "9903078M3003079CHL80000013<0<3",
    "FREDEZ<MATURANA<<JOAQUIN<LEON<<",
]


def check(title, lines, expected):
    """Parsea y verifica que los campos esperados coincidan."""
    print(f"\n===== {title} =====")
    result = parse_mrz(lines)
    if not result:
        print("  FALLO: parse_mrz devolvió None")
        return False
    ok = True
    for k, v in result.items():
        flag = ""
        if k in expected:
            flag = "  OK" if expected[k] == v else f"  ESPERADO: {expected[k]}"
            if expected[k] != v:
                ok = False
        print(f"  {k:14}: {v}{flag}")
    return ok


EXPECTED_ARG = {
    "name": "ALAN GABRIEL",
    "lastName": "SANJURJO",
    "dni": "43749627",
    "birthDate": "2001-11-07",
    "expiryDate": "2032-01-04",
    "sex": "M",
    "nationality": "ARG",
}

EXPECTED_CHL = {
    "name": "JOAQUIN LEON",
    "lastName": "FREDEZ MATURANA",
    "birthDate": "1999-03-07",
    "expiryDate": "2030-03-07",
    "sex": "M",
    "nationality": "CHL",
}


if __name__ == "__main__":
    results = [
        check("DNI ARGENTINO", arg_lines, EXPECTED_ARG),
        check("CEDULA CHILENA", chl_lines, EXPECTED_CHL),
    ]
    print("\n" + ("TODOS LOS TESTS PASARON" if all(results) else "HAY TESTS FALLIDOS"))
