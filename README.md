# Grupo ARI — Prueba Técnica Para el Puesto de Analista de Datos 

Solución end-to-end que combina precios de carburantes (API del Ministerio)
y matriculaciones de vehículos (DGT) en Canarias, para analizar qué zonas
ofrecen mejores oportunidades comerciales.

## Qué hace

1. **Extrae** precios de carburantes en Las Palmas y Sta. Cruz de Tenerife
   desde la API pública del Ministerio, y matriculaciones de vehículos
   desde los microdatos mensuales de la DGT.
2. **Transforma y limpia** ambas fuentes (parseo de ancho fijo, filtrado
   por año/provincia, normalización de nombres de municipio para poder
   cruzar ambas fuentes pese a usar convenciones de nombres distintas).
3. **Carga** los datos en un modelo relacional (esquema en estrella) sobre
   PostgreSQL, creando la base de datos y las tablas automáticamente.
4. **Visualiza** los resultados en un dashboard de Power BI con KPIs,
   mapa, y un índice de oportunidad comercial por municipio.

## Posibles mejoras futuras

1. Dockerizar el proyecto.
2. Mejorar el frontend y hacerlo un poco más cómodo de usar.

## Stack

Python · PostgreSQL · Power BI Desktop · Flask (panel de control)

## Estructura del proyecto

```
grupo_ari_analista_datos/
├── data/{raw,processed}/     # datos crudos y ya limpios
├── scripts/                  # pipeline de extracción, transformación y carga
├── frontend/                 # panel de control web
├── sql/01_create_schema.sql  # esquema de la base de datos
└── requirements.txt
```

## Instalación

Programas que deben estar instalados previamente: 
1. Python 12+
2. Power BI
3. PostgreSQL

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edita `.env` con la contraseña de tu PostgreSQL local. No hace falta crear
la base de datos a mano: se crea sola en el primer paso de carga.

## Uso por línea de comandos

```powershell
# 0. Sitúate en la raíz del proyecto.
# 1. Precios de carburantes (automático, vía API)
python scripts\obtener_datos_carburantes.py

# 2. Matriculaciones DGT: descarga los ZIP mensuales del portal de la DGT,
#    colócalos en data\raw\, y descomprímelos:
python scripts\descomprimir_matriculaciones.py data\raw\NOMBRE_DEL_ZIP.zip

# 3. Transformar y unificar matriculaciones (detecta todos los .txt de data\raw\)
python scripts\transform_matriculaciones.py

# 4. Crear/actualizar la base de datos y cargar ambas fuentes
python scripts\cargar_a_postgre.py
```

Con los datos ya en PostgreSQL, abre `dashboard/dashboard_grupo_ari.pbix`
en Power BI Desktop (conexión, relaciones y medidas ya incluidas en el
propio archivo).

## Uso con el panel de control (frontend)

Alternativa visual a los comandos anteriores, con salida en vivo y sin
necesidad de escribir nada en la terminal (aparte de la ejecución del script
del frontend):

```powershell
python frontend\app.py
```

Abre **http://localhost:5000** — desde ahí puedes ejecutar cada paso del
pipeline con un botón, y subir los ZIP de matriculaciones directamente
desde el explorador de archivos del navegador.

