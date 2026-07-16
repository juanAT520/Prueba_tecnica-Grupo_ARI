"""
db_utils.py
------------
Utilidades compartidas para el proceso de carga a base de datos:
normalización de nombres de municipio y tabla de alias entre las dos
fuentes (DGT matriculaciones y datos de gasolineras), ya que los nombres 
no son equivalentes al 100%.

Ejemplo:
    Nombres en los datos de la DGT:
        "S C TENERIFE", "LAS PALMAS G C", "LOS LLANOS A"
    Nombnres en los datos de las gasolineras:
        "Santa Cruz de Tenerife", "Las Palmas de Gran Canaria",
        "Los Llanos de Aridane"
"""

"""Módulo para trabajar con expresiones regulares"""
import re
import unicodedata

import pandas as pd


def normaliza_texto(s) -> str | None:
    """Elimina los espacios de más, pone todo en mayúsculas y quita los acentos."""
    if pd.isna(s):
        return None
    s = str(s).strip().upper()
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("utf-8")


def normaliza_municipio(s) -> str | None:
    """
    Normaliza un nombre de municipio y reordena el artículo cuando viene
    al final entre paréntesis, p.ej. "OROTAVA (LA)" -> "LA OROTAVA".
    """
    s = normaliza_texto(s)
    if s is None:
        return None
    m = re.match(r"^(.*)\s\((EL|LA|LOS|LAS)\)$", s)
    if m:
        s = f"{m.group(2)} {m.group(1)}".strip()
    return s


# ---------------------------------------------------------------------
# En este bloque creo los alias: a la izquierda de los dos puntos (:)
# está el nombre tal cómo aparece en los datos de carburantes. A la derecha
# el nombre tal cómo aparece en los datos de matriculaciones.
# ---------------------------------------------------------------------
ALIAS_MUNICIPIO_CARBURANTES_A_MATRICULACIONES = {
    "BUENAVISTA DEL NORTE": "BUENAVISTA",
    "FUENCALIENTE DE LA PALMA": "FUENCALIENTE",
    "GRANADILLA DE ABONA": "GRANADILLA",
    "ICOD DE LOS VINOS": "ICOD",
    "LA MATANZA DE ACENTEJO": "LA MATANZA",
    "LA VICTORIA DE ACENTEJO": "LA VICTORIA",
    "LOS LLANOS DE ARIDANE": "LOS LLANOS A",
    "PUERTO DE LA CRUZ": "PUERTO CRUZ",
    "SAN ANDRES Y SAUCES": "S A Y SAUCES",
    "SAN CRISTOBAL DE LA LAGUNA": "LA LAGUNA",
    "SAN JUAN DE LA RAMBLA": "S JUAN RAMBLA",
    "SAN MIGUEL DE ABONA": "SAN MIGUEL",
    "SAN SEBASTIAN DE LA GOMERA": "S S GOMERA",
    "SANTA CRUZ DE LA PALMA": "S C LA PALMA",
    "SANTA CRUZ DE TENERIFE": "S C TENERIFE",
    "LAS PALMAS DE GRAN CANARIA": "LAS PALMAS G C",
    "SAN BARTOLOME DE TIRAJANA": "S BARTOLOME TIRAJANA",
    "SANTA MARIA DE GUIA DE GRAN CANARIA": "S MARIA DE GUIA G C",
    "SANTA LUCIA DE TIRAJANA": "SANTA LUCIA",
    "SANTA MARIA DE GUIA": "S MARIA DE GUIA G C",
    "VALSEQUILLO DE GRAN CANARIA": "VALSEQUILLO G C",
    "ALDEA (LA)": "LA ALDEA DE SAN NICOLAS",
    "LA ALDEA": "LA ALDEA DE SAN NICOLAS",
    "VEGA DE SAN MATEO": "SAN MATEO",
}


def normalizar_municipio_carburantes(nombre_municipio_carburantes: str) -> str | None:
    """
    Recibe los nombres de los municipios del fichero de carburantes y los transforma
    para poder encontrarlos en el fichjero de matriculaciones.
    """
    norm = normaliza_municipio(nombre_municipio_carburantes)
    if norm is None:
        return None
    return ALIAS_MUNICIPIO_CARBURANTES_A_MATRICULACIONES.get(norm, norm)

"""
En el fichero de la DGT el código de provincia es '35' o '38' mientras que en el fichero
de carburantes es 'GC' y 'TF'.
"""
PROVINCIAS = {
    "35": {"cod_provincia_dgt": "GC", "nombre_provincia": "Las Palmas"},
    "38": {"cod_provincia_dgt": "TF", "nombre_provincia": "Santa Cruz de Tenerife"},
}

# Creo los alias para los códigos de provincia. A la izquierda de los dos puntos (:) los datos
# del fichero de carburamtes, a la derecha los de matriculaciones.
COD_DGT_A_INE = {"GC": "35", "TF": "38"}
