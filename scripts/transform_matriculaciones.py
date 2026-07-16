"""
transform_matriculaciones.py
------------------------------
Analiza el fichero de matrículas (export_mensual_mat_YYYYMM.txt),
aplicando el diseño de registro oficial que aparece en la documentacón de la DGT:

    https://sedeapl.dgt.gob.es/IEST_INTER/pdfs/disenoRegistro/vehiculos/matriculaciones/MATRICULACIONES_MATRABA.pdf

Filtra:
    - Año de matriculación (FEC_MATRICULA) = 2026
    - COD_PROVINCIA_MAT en ('GC', 'TF')
      GC = Las Palmas (cód. 35) / TF = Santa Cruz de Tenerife (cód. 38)

Entrada:
    Busca automáticamente todos los ficheros
    data/raw/**/export_mensual_mat_*.txt  (o *.txt en data/raw directamente)

Salida:
    data/processed/matriculaciones_canarias_2026.csv
"""

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

ANIO_OBJETIVO = 2026
PROVINCIAS_MAT_OBJETIVO = {"GC", "TF"}  # Las Palmas / Sta. Cruz de Tenerife

# ---------------------------------------------------------------------
# Cada uno de los campos que aparecen en el fichero 'raw' de matriculaciones
# y la longitud asignada para ese campo.
# ---------------------------------------------------------------------
CAMPOS = [
    ("FEC_MATRICULA", 8),
    ("COD_CLASE_MAT", 1),
    ("FEC_TRAMITACION", 8),
    ("MARCA_ITV", 30),
    ("MODELO_ITV", 22),
    ("COD_PROCEDENCIA_ITV", 1),
    ("BASTIDOR_ITV", 21),
    ("COD_TIPO", 2),
    ("COD_PROPULSION_ITV", 1),
    ("CILINDRADA_ITV", 5),
    ("POTENCIA_ITV", 6),
    ("TARA", 6),
    ("PESO_MAX", 6),
    ("NUM_PLAZAS", 3),
    ("IND_PRECINTO", 2),
    ("IND_EMBARGO", 2),
    ("NUM_TRANSMISIONES", 2),
    ("NUM_TITULARES", 2),
    ("LOCALIDAD_VEHICULO", 24),
    ("COD_PROVINCIA_VEH", 2),
    ("COD_PROVINCIA_MAT", 2),
    ("CLAVE_TRAMITE", 1),
    ("FEC_TRAMITE", 8),
    ("CODIGO_POSTAL", 5),
    ("FEC_PRIM_MATRICULACION", 8),
    ("IND_NUEVO_USADO", 1),
    ("PERSONA_FISICA_JURIDICA", 1),
    ("CODIGO_ITV", 9),
    ("SERVICIO", 3),
    ("COD_MUNICIPIO_INE_VEH", 5),
    ("MUNICIPIO", 30),
    ("KW_ITV", 7),
    ("NUM_PLAZAS_MAX", 3),
    ("CO2_ITV", 5),
    ("RENTING", 1),
    ("COD_TUTELA", 1),
    ("COD_POSESION", 1),
    ("IND_BAJA_DEF", 1),
    ("IND_BAJA_TEMP", 1),
    ("IND_SUSTRACCION", 1),
    ("BAJA_TELEMATICA", 11),
    ("TIPO_ITV", 25),
    ("VARIANTE_ITV", 25),
    ("VERSION_ITV", 35),
    ("FABRICANTE_ITV", 70),
    ("MASA_ORDEN_MARCHA_ITV", 6),
    ("MASA_MAX_TECNICA_ADMISIBLE_ITV", 6),
    ("CATEGORIA_HOMOLOGACION_EUROPEA_ITV", 4),
    ("CARROCERIA", 4),
    ("PLAZAS_PIE", 3),
    ("NIVEL_EMISIONES_EURO_ITV", 8),
    ("CONSUMO_WH_KM_ITV", 4),
    ("CLASIFICACION_REGLAMENTO_VEHICULOS_ITV", 4),
    ("CATEGORIA_VEHICULO_ELECTRICO", 4),
    ("AUTONOMIA_VEHICULO_ELECTRICO", 6),
    ("MARCA_VEHICULO_BASE", 30),
    ("FABRICANTE_VEHICULO_BASE", 50),
    ("TIPO_VEHICULO_BASE", 35),
    ("VARIANTE_VEHICULO_BASE", 25),
    ("VERSION_VEHICULO_BASE", 35),
    ("DISTANCIA_EJES_12_ITV", 4),
    ("VIA_ANTERIOR_ITV", 4),
    ("VIA_POSTERIOR_ITV", 4),
    ("TIPO_ALIMENTACION_ITV", 1),
    ("CONTRASENA_HOMOLOGACION_ITV", 25),
    ("ECO_INNOVACION_ITV", 1),
    ("REDUCCION_ECO_ITV", 4),
    ("CODIGO_ECO_ITV", 25),
    ("FEC_PROCESO", 8),
]

# Columnas que nos interesan para el análisis de negocio (el resto se
# descarta tras el parseo para mantener el CSV manejable). Ajustable.
COLUMNAS_UTILES = [
    "FEC_MATRICULA",
    "COD_CLASE_MAT",
    "MARCA_ITV",
    "MODELO_ITV",
    "COD_TIPO",
    "COD_PROPULSION_ITV",
    "LOCALIDAD_VEHICULO",
    "COD_PROVINCIA_VEH",
    "COD_PROVINCIA_MAT",
    "CODIGO_POSTAL",
    "IND_NUEVO_USADO",
    "PERSONA_FISICA_JURIDICA",
    "SERVICIO",
    "COD_MUNICIPIO_INE_VEH",
    "MUNICIPIO",
    "CO2_ITV",
]


def build_colspecs(campos: list[tuple[str, int]]) -> tuple[list[tuple[int, int]], list[str]]:
    """Convierte la lista (nombre, longitud) en colspecs [(inicio, fin), ...] para pandas."""
    colspecs = []
    nombres = []
    pos = 0
    for nombre, longitud in campos:
        colspecs.append((pos, pos + longitud))
        nombres.append(nombre)
        pos += longitud
    return colspecs, nombres


def encontrar_ficheros() -> list[Path]:
    ficheros = sorted(RAW_DIR.rglob("export_mensual_mat_*.txt"))
    if not ficheros:
        # fallback: cualquier .txt dentro de data/raw
        ficheros = sorted(RAW_DIR.rglob("*.txt"))
    return ficheros


def parsear_fichero(path: Path, colspecs, nombres) -> pd.DataFrame:
    print(f"[INFO] Parseando: {path.name}")
    df = pd.read_fwf(
        path,
        colspecs=colspecs,
        names=nombres,
        encoding="latin-1",
        dtype=str,
    )
    # Quitamos posibles espacios en blanco de cada campo string
    for col in df.columns:
        df[col] = df[col].str.strip()
    return df


def filtrar_y_limpiar(df: pd.DataFrame) -> pd.DataFrame:
    # FEC_MATRICULA viene como DDMMYYYY (texto de 8 caracteres)
    df = df[df["FEC_MATRICULA"].str.len() == 8].copy()
    df["anio_matriculacion"] = df["FEC_MATRICULA"].str[4:8]
    df["mes_matriculacion"] = df["FEC_MATRICULA"].str[2:4]
    df["dia_matriculacion"] = df["FEC_MATRICULA"].str[0:2]

    df = df[df["anio_matriculacion"] == str(ANIO_OBJETIVO)]
    df = df[df["COD_PROVINCIA_MAT"].isin(PROVINCIAS_MAT_OBJETIVO)]

    # --- Filtro de calidad de datos adicional ---
    # COD_PROVINCIA_MAT indica dónde se TRAMITÓ la matriculación, pero
    # COD_PROVINCIA_VEH indica el domicilio REAL del vehículo/titular.
    # Existen casos (flotas de renting/alquiler) donde la matriculación se
    # tramita en Canarias pero el vehículo está domiciliado en la
    # península (p.ej. Móstoles, Ferrol, Benalmádena). Como el objetivo del
    # análisis es geográfico ("zonas de Canarias"), estos registros se
    # excluyen: no representan volumen de mercado canario.
    antes = len(df)
    df = df[df["COD_PROVINCIA_VEH"].isin(PROVINCIAS_MAT_OBJETIVO)]
    excluidos = antes - len(df)
    if excluidos:
        print(f"[INFO] Excluidos {excluidos} registros con vehículo domiciliado fuera de Canarias "
              f"(matriculación tramitada en Canarias pero COD_PROVINCIA_VEH fuera de GC/TF, p.ej. flotas/renting)")

    print(f"[INFO] Registros tras filtro año={ANIO_OBJETIVO} y provincia GC/TF: {len(df)}")

    # Fecha real de matriculación en formato ISO
    df["fecha_matriculacion"] = pd.to_datetime(
        df["anio_matriculacion"] + "-" + df["mes_matriculacion"] + "-" + df["dia_matriculacion"],
        format="%Y-%m-%d",
        errors="coerce",
    )

    # Mapeo de provincia a nombre legible
    mapa_provincia = {"GC": "Las Palmas", "TF": "Santa Cruz de Tenerife"}
    df["provincia_matriculacion"] = df["COD_PROVINCIA_MAT"].map(mapa_provincia)

    # CO2 numérico (viene con formato ZZZZZ, puede tener espacios/ceros)
    df["CO2_ITV"] = pd.to_numeric(df["CO2_ITV"], errors="coerce")

    columnas_finales = [
        "fecha_matriculacion",
        "anio_matriculacion",
        "mes_matriculacion",
    ] + [c for c in COLUMNAS_UTILES if c != "FEC_MATRICULA"] + ["provincia_matriculacion"]

    return df[columnas_finales]


def main():
    colspecs, nombres = build_colspecs(CAMPOS)
    ficheros = encontrar_ficheros()

    if not ficheros:
        print(f"[ERROR] No se encontraron ficheros .txt en {RAW_DIR}. "
              f"Asegúrate de haber descomprimido el ZIP con inspect_matriculaciones.py primero.")
        return

    dfs = []
    for f in ficheros:
        df_raw = parsear_fichero(f, colspecs, nombres)
        df_filtrado = filtrar_y_limpiar(df_raw)
        dfs.append(df_filtrado)

    df_final = pd.concat(dfs, ignore_index=True)
    df_final = df_final.drop_duplicates()

    out_path = PROCESSED_DIR / "matriculaciones_canarias_2026.csv"
    df_final.to_csv(out_path, index=False, encoding="utf-8-sig")

    print(f"\n[OK] CSV final guardado en: {out_path}")
    print(f"[OK] Total de registros: {len(df_final)}")
    print("\nResumen por provincia:")
    print(df_final["provincia_matriculacion"].value_counts())
    print("\nMuestra:")
    print(df_final.head())


if __name__ == "__main__":
    main()
