"""
Script de diagnóstico (no es un test): muestra qué líneas extrae el OCR de cada
imagen real y qué devuelve el parser MRZ. Útil para depurar lecturas fallidas.

Uso:
    docker compose exec api python tests/debug_ocr.py
"""

import glob
import os

from app.mrz_parser import _extract_mrz_candidates, parse_mrz
from app.ocr import extract_lines_from_image

IMAGES_DIR = os.path.join(os.path.dirname(__file__), "DNIs")


def main():
    for path in sorted(glob.glob(os.path.join(IMAGES_DIR, "*.jpg"))):
        print("\n" + "=" * 70)
        print(os.path.basename(path))
        print("=" * 70)
        with open(path, "rb") as f:
            lines = extract_lines_from_image(f.read())

        print("--- LÍNEAS OCR ---")
        for ln in lines:
            print(f"   {ln!r}")

        print("--- CANDIDATAS MRZ (normalizadas) ---")
        for c in _extract_mrz_candidates(lines):
            print(f"   [{len(c):2}] {c}")

        result = parse_mrz(lines)
        print("--- PARSE_MRZ ---")
        print(f"   {result}")


if __name__ == "__main__":
    main()
