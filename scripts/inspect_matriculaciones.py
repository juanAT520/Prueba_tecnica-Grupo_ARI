"""
inspect_matriculaciones.py
---------------------------
Descomprime el ZIP de "Microdatos de Matriculaciones de Vehículos" descargado
manualmente desde la web de la DGT / datos.gob.es, y muestra un resumen
(columnas, tipos, primeras filas) para poder diseñar el script de
transformación (Parte 2).

Uso (Windows PowerShell), tras colocar el ZIP descargado en data/raw/:
    python scripts\\inspect_matriculaciones.py data\\raw\\NOMBRE_DEL_FICHERO.zip
"""

import sys
import zipfile
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"


def descomprimir(zip_path: Path) -> list[Path]:
    extract_dir = RAW_DIR / zip_path.stem
    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_dir)
        nombres = z.namelist()

    print(f"[OK] Descomprimido en: {extract_dir}")
    print(f"[INFO] Ficheros encontrados: {nombres}")

    return [extract_dir / n for n in nombres]


def inspeccionar(ficheros: list[Path]):
    for f in ficheros:
        if f.suffix.lower() not in (".csv", ".txt"):
            continue

        print(f"\n{'='*70}")
        print(f"Fichero: {f.name}")
        print(f"{'='*70}")

        # Los microdatos de DGT suelen venir separados por ';' y en latin-1
        try:
            df = pd.read_csv(f, sep=";", encoding="latin-1", nrows=1000, low_memory=False)
        except Exception as e:
            print(f"[WARN] Fallo leyendo con ';'/latin-1 ({e}), probando con ',' / utf-8")
            df = pd.read_csv(f, sep=",", encoding="utf-8", nrows=1000, low_memory=False)

        print(f"Columnas ({len(df.columns)}):")
        for col in df.columns:
            print(f"  - {col}  (dtype: {df[col].dtype})")

        print("\nPrimeras filas:")
        print(df.head())

        if "COD_PROVINCIA_MAT" in df.columns:
            print("\nValores únicos de COD_PROVINCIA_MAT (muestra):")
            print(df["COD_PROVINCIA_MAT"].astype(str).unique()[:20])


def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts\\inspect_matriculaciones.py <ruta_al_zip>")
        sys.exit(1)

    zip_path = Path(sys.argv[1])
    if not zip_path.exists():
        print(f"[ERROR] No existe el fichero: {zip_path}")
        sys.exit(1)

    ficheros = descomprimir(zip_path)
    inspeccionar(ficheros)


if __name__ == "__main__":
    main()
