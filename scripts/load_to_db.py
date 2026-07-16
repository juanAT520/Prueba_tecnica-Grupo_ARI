"""
load_to_db.py
---------------
Carga los CSV procesados (carburantes y matriculaciones) al modelo
relacional en PostgreSQL definido en sql/01_create_schema.sql.

Pasos:
    1. Ejecuta el script de creación de esquema (DROP + CREATE de todas
       las tablas).
    2. Construye las dimensiones (provincia, municipio, tiempo, estación).
    3. Carga las tablas de hechos (matriculaciones, precios carburante).

Requisitos previos:
    - PostgreSQL instalado y en marcha, con la base de datos creada
      (ver README.md, sección PARTE 2).
    - Fichero .env configurado con las credenciales de conexión.
    - Haber ejecutado extract_carburantes.py y transform_matriculaciones.py.

Uso (Windows PowerShell):
    python scripts\\load_to_db.py
"""

import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from db_utils import (
    COD_DGT_A_INE,
    PROVINCIAS,
    municipio_carburantes_a_clave_canonica,
    normaliza_municipio,
)

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
SQL_DIR = PROJECT_ROOT / "sql"

MATRICULACIONES_CSV = PROCESSED_DIR / "matriculaciones_canarias_2026.csv"


def encontrar_csv_carburantes() -> Path:
    """
    Busca el CSV de carburantes más reciente. extract_carburantes.py lo
    guarda en data/raw/ con la fecha de extracción en el nombre
    (carburantes_canarias_YYYYMMDD.csv); si además lo has copiado a
    data/processed/, se prioriza esa copia.
    """
    candidatos = sorted(PROCESSED_DIR.glob("carburantes_canarias_*.csv")) or sorted(
        RAW_DIR.glob("carburantes_canarias_*.csv")
    )
    if not candidatos:
        raise FileNotFoundError(
            "No se encontró ningún carburantes_canarias_*.csv en data/raw ni data/processed. "
            "Ejecuta scripts/extract_carburantes.py primero."
        )
    return candidatos[-1]  # el más reciente por orden alfabético (fecha en el nombre)


def ensure_database_exists():
    """
    Comprueba si la base de datos configurada en .env (DB_NAME) existe en el
    servidor PostgreSQL; si no, la crea. Así el usuario no tiene que abrir
    psql/pgAdmin manualmente para el "CREATE DATABASE" — solo necesita tener
    PostgreSQL instalado y en marcha, con el usuario/contraseña del .env.

    Nota: CREATE DATABASE no puede ejecutarse dentro de una transacción en
    PostgreSQL, por eso se usa una conexión psycopg2 en modo autocommit en
    vez de SQLAlchemy para este paso concreto.
    """
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    dbname = os.getenv("DB_NAME", "grupo_ari")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "")

    # Nos conectamos a la base "postgres" (siempre existe) para poder
    # comprobar/crear la base de datos del proyecto.
    conn = psycopg2.connect(host=host, port=port, dbname="postgres", user=user, password=password)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
            existe = cur.fetchone() is not None
            if existe:
                print(f"[INFO] La base de datos '{dbname}' ya existe.")
            else:
                # No se puede usar parámetros (%s) en CREATE DATABASE; el
                # nombre viene de nuestro propio .env, no de un usuario final,
                # así que el riesgo de inyección SQL aquí es controlado.
                cur.execute(f'CREATE DATABASE "{dbname}"')
                print(f"[OK] Base de datos '{dbname}' creada automáticamente.")
    finally:
        conn.close()


def get_engine():
    engine_name = os.getenv("DB_ENGINE", "postgresql")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    dbname = os.getenv("DB_NAME", "grupo_ari")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "")

    url = f"{engine_name}://{user}:{password}@{host}:{port}/{dbname}"
    return create_engine(url)


def ejecutar_schema(engine):
    sql_path = SQL_DIR / "01_create_schema.sql"
    print(f"[INFO] Ejecutando esquema: {sql_path}")
    sql_text = sql_path.read_text(encoding="utf-8")

    with engine.begin() as conn:
        for statement in sql_text.split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(text(statement))
    print("[OK] Esquema creado.")


def cargar_csvs():
    carburantes_csv = encontrar_csv_carburantes()
    print(f"[INFO] Usando CSV de carburantes: {carburantes_csv}")

    if not MATRICULACIONES_CSV.exists():
        raise FileNotFoundError(
            f"No se encuentra {MATRICULACIONES_CSV}. Ejecuta transform_matriculaciones.py primero."
        )

    carb = pd.read_csv(carburantes_csv)
    mat = pd.read_csv(MATRICULACIONES_CSV)
    return carb, mat


def construir_dim_provincia(engine):
    df = pd.DataFrame(
        [
            {"cod_provincia": cod, "cod_provincia_dgt": info["cod_provincia_dgt"], "nombre_provincia": info["nombre_provincia"]}
            for cod, info in PROVINCIAS.items()
        ]
    )
    df.to_sql("dim_provincia", engine, if_exists="append", index=False)
    print(f"[OK] dim_provincia: {len(df)} filas")


def construir_dim_municipio_y_alias(engine, carb: pd.DataFrame, mat: pd.DataFrame):
    # --- Base canónica: municipios de matriculaciones (tienen código INE real) ---
    base = (
        mat[["COD_MUNICIPIO_INE_VEH", "MUNICIPIO", "COD_PROVINCIA_MAT"]]
        .drop_duplicates()
        .rename(
            columns={
                "COD_MUNICIPIO_INE_VEH": "cod_ine_municipio",
                "MUNICIPIO": "nombre_municipio_dgt",
                "COD_PROVINCIA_MAT": "cod_provincia_dgt",
            }
        )
    )
    base["cod_ine_municipio"] = base["cod_ine_municipio"].astype(str)
    base["nombre_municipio_normalizado"] = base["nombre_municipio_dgt"].apply(normaliza_municipio)
    base["cod_provincia"] = base["cod_provincia_dgt"].map(COD_DGT_A_INE)
    base = base.drop(columns=["cod_provincia_dgt"])

    # Puede haber duplicados por nombre normalizado repetido en distinta
    # provincia (raro, pero nos quedamos con el primero de forma determinista)
    base = base.drop_duplicates(subset=["nombre_municipio_normalizado"])

    dim_municipio = base.reset_index(drop=True)
    dim_municipio.insert(0, "municipio_id", range(1, len(dim_municipio) + 1))

    dim_municipio.to_sql("dim_municipio", engine, if_exists="append", index=False)
    print(f"[OK] dim_municipio: {len(dim_municipio)} filas")

    # --- Tabla de alias / auditoría ---
    mapa_clave_a_id = dict(zip(dim_municipio["nombre_municipio_normalizado"], dim_municipio["municipio_id"]))

    alias_rows = []

    # Alias desde matriculaciones (nombre crudo = nombre normalizado, trivial pero se deja documentado)
    for _, row in dim_municipio.iterrows():
        alias_rows.append(
            {
                "fuente": "matriculaciones",
                "nombre_crudo": row["nombre_municipio_dgt"],
                "municipio_id": row["municipio_id"],
            }
        )

    # Alias desde carburantes (usa la función de mapeo con normalización + diccionario de alias)
    municipios_carb = carb["municipio"].drop_duplicates()
    sin_match = []
    for nombre_crudo in municipios_carb:
        clave = municipio_carburantes_a_clave_canonica(nombre_crudo)
        municipio_id = mapa_clave_a_id.get(clave)
        if municipio_id is None:
            sin_match.append(nombre_crudo)
            continue
        alias_rows.append(
            {"fuente": "carburantes", "nombre_crudo": nombre_crudo, "municipio_id": municipio_id}
        )

    if sin_match:
        print(f"[WARN] {len(sin_match)} municipios de carburantes sin correspondencia en matriculaciones: {sin_match}")
        print("[WARN] Revisa/actualiza el diccionario ALIAS en scripts/db_utils.py")

    df_alias = pd.DataFrame(alias_rows)
    df_alias.to_sql("dim_municipio_alias", engine, if_exists="append", index=False)
    print(f"[OK] dim_municipio_alias: {len(df_alias)} filas ({len(sin_match)} sin match)")

    return dim_municipio, mapa_clave_a_id


def construir_dim_tiempo(engine, fechas: pd.Series):
    fechas_validas = pd.to_datetime(fechas.dropna().unique())
    if len(fechas_validas) == 0:
        return
    fecha_min, fecha_max = fechas_validas.min(), fechas_validas.max()

    rango = pd.date_range(fecha_min, fecha_max, freq="D")
    df = pd.DataFrame({"fecha": rango})
    df["anio"] = df["fecha"].dt.year
    df["mes"] = df["fecha"].dt.month
    df["dia"] = df["fecha"].dt.day
    df["trimestre"] = df["fecha"].dt.quarter

    meses_es = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
        7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
    }
    df["nombre_mes"] = df["mes"].map(meses_es)

    df.to_sql("dim_tiempo", engine, if_exists="append", index=False)
    print(f"[OK] dim_tiempo: {len(df)} filas ({fecha_min.date()} a {fecha_max.date()})")


def construir_dim_estacion(engine, carb: pd.DataFrame, mapa_clave_a_id: dict):
    df = carb.copy()
    df["municipio_id"] = df["municipio"].apply(
        lambda x: mapa_clave_a_id.get(municipio_carburantes_a_clave_canonica(x))
    )

    dim_estacion = df.rename(
        columns={
            "id_estacion": "id_estacion",
            "rotulo": "rotulo",
            "direccion": "direccion",
            "horario": "horario",
            "latitud": "latitud",
            "longitud": "longitud",
            "Margen": "margen",
            "tipo_venta": "tipo_venta",
            "codigo_postal": "codigo_postal",
        }
    )[
        ["id_estacion", "rotulo", "direccion", "horario", "latitud", "longitud",
         "margen", "tipo_venta", "codigo_postal", "municipio_id"]
    ].drop_duplicates(subset=["id_estacion"])

    dim_estacion.to_sql("dim_estacion", engine, if_exists="append", index=False)
    print(f"[OK] dim_estacion: {len(dim_estacion)} filas")


def cargar_fact_matriculaciones(engine, mat: pd.DataFrame, mapa_clave_a_id: dict):
    df = mat.copy()
    df["municipio_norm"] = df["MUNICIPIO"].apply(normaliza_municipio)
    df["municipio_id"] = df["municipio_norm"].map(mapa_clave_a_id)
    df["cod_provincia"] = df["COD_PROVINCIA_MAT"].map(COD_DGT_A_INE)

    fact = df.rename(
        columns={
            "fecha_matriculacion": "fecha_matriculacion",
            "MARCA_ITV": "marca",
            "MODELO_ITV": "modelo",
            "COD_TIPO": "cod_tipo_vehiculo",
            "COD_PROPULSION_ITV": "cod_propulsion",
            "IND_NUEVO_USADO": "ind_nuevo_usado",
            "PERSONA_FISICA_JURIDICA": "persona_fisica_juridica",
            "SERVICIO": "servicio",
            "CO2_ITV": "co2",
            "CODIGO_POSTAL": "codigo_postal",
        }
    )[
        ["fecha_matriculacion", "municipio_id", "cod_provincia", "marca", "modelo",
         "cod_tipo_vehiculo", "cod_propulsion", "ind_nuevo_usado", "persona_fisica_juridica",
         "servicio", "co2", "codigo_postal"]
    ]

    fact.to_sql("fact_matriculaciones", engine, if_exists="append", index=False, chunksize=5000)
    print(f"[OK] fact_matriculaciones: {len(fact)} filas")


def cargar_fact_precios_carburante(engine, carb: pd.DataFrame, mapa_clave_a_id: dict):
    df = carb.copy()
    df["municipio_id"] = df["municipio"].apply(
        lambda x: mapa_clave_a_id.get(municipio_carburantes_a_clave_canonica(x))
    )
    df["cod_provincia"] = df["IDProvincia"].astype(str)

    fact = df.rename(
        columns={
            "id_estacion": "id_estacion",
            "fecha_extraccion": "fecha_extraccion",
            "precio_gasoleo_a": "precio_gasoleo_a",
            "precio_gasoleo_premium": "precio_gasoleo_premium",
            "precio_gasolina_95_e5": "precio_gasolina_95_e5",
            "precio_gasolina_98_e5": "precio_gasolina_98_e5",
            "precio_glp": "precio_glp",
            "precio_gnc": "precio_gnc",
        }
    )[
        ["id_estacion", "municipio_id", "cod_provincia", "fecha_extraccion",
         "precio_gasoleo_a", "precio_gasoleo_premium", "precio_gasolina_95_e5",
         "precio_gasolina_98_e5", "precio_glp", "precio_gnc"]
    ]

    fact.to_sql("fact_precios_carburante", engine, if_exists="append", index=False)
    print(f"[OK] fact_precios_carburante: {len(fact)} filas")


def main():
    ensure_database_exists()

    engine = get_engine()

    ejecutar_schema(engine)

    carb, mat = cargar_csvs()

    construir_dim_provincia(engine)
    dim_municipio, mapa_clave_a_id = construir_dim_municipio_y_alias(engine, carb, mat)

    todas_fechas = pd.concat(
        [pd.to_datetime(mat["fecha_matriculacion"]), pd.to_datetime(carb["fecha_extraccion"])]
    )
    construir_dim_tiempo(engine, todas_fechas)

    construir_dim_estacion(engine, carb, mapa_clave_a_id)

    cargar_fact_matriculaciones(engine, mat, mapa_clave_a_id)
    cargar_fact_precios_carburante(engine, carb, mapa_clave_a_id)

    print("\n[OK] Carga completa.")


if __name__ == "__main__":
    main()
