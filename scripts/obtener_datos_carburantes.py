"""
obtener_datos_carburantes.py
-----------------------
Recoge los precios de carburantes de la API del Ministerio
y filtra los resultados para las provincias de Las Palmas 
y Santa Cruz de Tenerife.

Salida:
    data/raw/carburantes_canarias_YYYYMMDD.csv
    data/raw/carburantes_canarias_YYYYMMDD.json  (respaldo del crudo)
"""

import json
import os

"""Gestión de conexiones seguras"""
import ssl
import time
from datetime import datetime

"""Módulo que hace más cómodo el manejo de archivos y carpetas"""
from pathlib import Path

import pandas as pd
import requests

"""Módulo para importar la conexión a la base de datos de un fichero .env"""
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

# ---------------------------------------------------------------------
# El servidor sedeaplicaciones.minetur.gob.es tiene una configuración TLS
# algo anticuada (requiere "legacy renegotiation"), lo que provoca
# ConnectionResetError con las versiones recientes de OpenSSL/Python en
# Windows. Este adaptador relaja esa restricción únicamente para este host.
# ---------------------------------------------------------------------
class LegacyTLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        # Permite renegociación insegura/legacy (algunos servidores gob.es la exigen)
        ctx.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)  # fallback si la constante no existe
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        kwargs["ssl_context"] = ctx
        self.poolmanager = PoolManager(*args, **kwargs)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# ---------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------
load_dotenv()

API_URL = os.getenv(
    "CARBURANTES_URL",
    "https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/PreciosCarburantes/EstacionesTerrestres/",
)

# Códigos de provincia para limitar los datos recibidos a únicamente los de 
# las provincias de Canarias.
IDS_PROVINCIA_OBJETIVO = {"35", "38"}

# _file_ es la ruta del archivo actual.
RAIZ_DE_PROYECTO = Path(__file__).resolve().parent.parent
CARPETA_RAW = RAIZ_DE_PROYECTO / os.getenv("DATA_RAW_DIR", "data/raw")
# Si la carpeta 'raw' no existe, la crea.
CARPETA_RAW.mkdir(parents=True, exist_ok=True)

CARPETA_PROCESSED = RAIZ_DE_PROYECTO / os.getenv("DATA_PROCESSED_DIR", "data/processed")
CARPETA_PROCESSED.mkdir(parents=True, exist_ok=True)


def obtener_datos_carburantes(url: str = API_URL, intentos: int = 4) -> dict:
    """Llama a la API y devuelve el JSON crudo. Tiene control de errores
     para manejar el problema del TLS del servidor del Ministerio."""
    print(f"[INFO] Solicitando datos a: {url}")

    session = requests.Session()
    session.mount("https://", LegacyTLSAdapter())

    ultimo_error = None
    for intento in range(1, intentos + 1):
        try:
            resp = session.get(url, headers=HEADERS, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            print(f"[INFO] Respuesta recibida. Total estaciones (nacional): {len(data.get('ListaEESSPrecio', []))}")
            return data
        except requests.exceptions.RequestException as e:
            ultimo_error = e
            espera = 3 * intento
            print(f"[WARN] Intento {intento}/{intentos} falló ({e}). Reintentando en {espera}s...")
            time.sleep(espera)

    raise RuntimeError(
        f"No se pudo conectar a la API tras {intentos} intentos. Último error: {ultimo_error}\n"
        f"Sugerencias: comprueba que https://sedeaplicaciones.minetur.gob.es funciona en tu "
        f"navegador, revisa el antivirus/firewall (puede estar interceptando el TLS), o "
        f"vuelve a intentarlo en unos minutos (el servidor puede estar limitando peticiones)."
    )


def filtrar_canarias(data: dict) -> pd.DataFrame:
    """Filtra la lista de carburantes para quedarnos solo con las estaciones
     de servicio de Canarias."""
    estaciones = data.get("ListaEESSPrecio", [])
    df = pd.DataFrame(estaciones)

    if df.empty:
        raise ValueError("La API no devolvió estaciones. Revisa el endpoint o tu conexión.")

    # Normalizamos el código de provincia (puede venir como "35"/"38" o con
    # ceros/espacios) y filtramos por código INE, no por texto.
    df["IDProvincia_norm"] = df["IDProvincia"].astype(str).str.strip()

    df_canarias = df[df["IDProvincia_norm"].isin(IDS_PROVINCIA_OBJETIVO)].copy()
    df_canarias.drop(columns=["IDProvincia_norm"], inplace=True)

    print(f"[INFO] Estaciones en Canarias (Las Palmas + Sta. Cruz de Tenerife): {len(df_canarias)}")
    if not df_canarias.empty:
        print("[INFO] Reparto por provincia:")
        print(df_canarias["Provincia"].value_counts())
    return df_canarias


def limpiar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    """Renombra y tipa columnas relevantes."""
    # Mapeo de columnas originales a nombres normalizados
    rename_map = {
        "IDEESS": "id_estacion",
        "Rótulo": "rotulo",
        "Dirección": "direccion",
        "Localidad": "localidad",
        "Municipio": "municipio",
        "Provincia": "provincia",
        "C.P.": "codigo_postal",
        "Latitud": "latitud",
        "Longitud (WGS84)": "longitud",
        "Precio Gasoleo A": "precio_gasoleo_a",
        "Precio Gasoleo Premium": "precio_gasoleo_premium",
        "Precio Gasolina 95 E5": "precio_gasolina_95_e5",
        "Precio Gasolina 98 E5": "precio_gasolina_98_e5",
        "Precio Gases licuados del petróleo": "precio_glp",
        "Precio Gas Natural Comprimido": "precio_gnc",
        "Rotulo": "rotulo",
        "Tipo Venta": "tipo_venta",
        "Horario": "horario",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # Columnas numéricas: la API las devuelve como texto con coma decimal
    posibles_precios = [c for c in df.columns if c.startswith("precio_")]
    for col in posibles_precios:
        df[col] = (
            df[col]
            .astype(str)
            .str.replace(",", ".", regex=False)
            .replace({"": None, "nan": None})
        )
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if "latitud" in df.columns:
        df["latitud"] = df["latitud"].astype(str).str.replace(",", ".", regex=False)
        df["latitud"] = pd.to_numeric(df["latitud"], errors="coerce")
    if "longitud" in df.columns:
        df["longitud"] = df["longitud"].astype(str).str.replace(",", ".", regex=False)
        df["longitud"] = pd.to_numeric(df["longitud"], errors="coerce")

    df["fecha_extraccion"] = datetime.now().strftime("%Y-%m-%d")
    return df


def main():
    hoy = datetime.now().strftime("%Y%m%d")

    datos_sin_procesar = obtener_datos_carburantes()

    ruta_json = CARPETA_RAW / f"carburantes_raw_{hoy}.json"
    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(datos_sin_procesar, f, ensure_ascii=False, indent=2)
    print(f"[OK] JSON crudo guardado en: {ruta_json}")

    df_canarias = filtrar_canarias(datos_sin_procesar)
    df_canarias = limpiar_columnas(df_canarias)

    csv_path = CARPETA_PROCESSED / f"carburantes_canarias_{hoy}.csv"
    df_canarias.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"[OK] CSV filtrado (Canarias) guardado en: {csv_path}")
    print(df_canarias.head())


if __name__ == "__main__":
    main()
