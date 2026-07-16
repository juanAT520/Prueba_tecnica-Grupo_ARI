"""
app.py
-------
Panel de control web del proyecto Grupo ARI. Es un backend mínimo (Flask)
que:
  - Ejecuta los scripts del pipeline como subprocesos.
  - Transmite su salida en vivo al navegador mediante Server-Sent Events
    (SSE), para que se vea igual que en una terminal.
  - Permite subir los ZIP de matriculaciones descargados manualmente desde
    el navegador (sin tener que copiarlos a mano a data/raw/).

No sustituye a los scripts en sí (siguen siendo los mismos de siempre); es
solo una interfaz visual por encima para facilitar la ejecución y el
seguimiento del proceso.

Uso (Windows PowerShell, con el entorno virtual activado):
    pip install -r requirements.txt   (ya incluye Flask)
    python frontend\\app.py
Luego abre en el navegador: http://localhost:5000
"""

import subprocess
import sys
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
RAW_DIR = PROJECT_ROOT / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, static_folder="static", static_url_path="/static")

# Pasos del pipeline que el panel puede ejecutar (nombre interno -> script real)
SCRIPTS = {
    "carburantes": "obtener_datos_carburantes.py",
    "transformar": "transform_matriculaciones.py",
    "cargar": "cargar_a_postgre.py",
}


def stream_script(script_name: str, extra_args=None):
    """Ejecuta un script y va transmitiendo su salida línea a línea (formato SSE)."""
    cmd = [sys.executable, str(SCRIPTS_DIR / script_name)] + (extra_args or [])
    proceso = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    for linea in proceso.stdout:
        yield f"data: {linea.rstrip()}\n\n"
    proceso.wait()
    if proceso.returncode == 0:
        yield "data: [FIN_OK]\n\n"
    else:
        yield f"data: [FIN_ERROR] El proceso terminó con código {proceso.returncode}\n\n"


@app.route("/")
def index():
    return send_from_directory(str(Path(__file__).parent / "templates"), "index.html")


@app.route("/run/<paso>")
def run_step(paso):
    """Lanza uno de los scripts principales del pipeline y transmite su salida."""
    if paso not in SCRIPTS:
        return jsonify({"error": "Paso desconocido"}), 404
    return Response(stream_script(SCRIPTS[paso]), mimetype="text/event-stream")


@app.route("/run/inspeccionar")
def run_inspeccionar():
    """Descomprime e inspecciona un ZIP concreto de matriculaciones ya subido."""
    zip_name = request.args.get("zip", "")
    zip_path = RAW_DIR / zip_name
    if not zip_name or not zip_path.exists() or zip_path.suffix.lower() != ".zip":
        return jsonify({"error": f"ZIP no válido: {zip_name}"}), 400
    return Response(
        stream_script("descomprimir_matriculaciones.py", [str(zip_path)]),
        mimetype="text/event-stream",
    )


@app.route("/upload-zips", methods=["POST"])
def upload_zips():
    """Recibe los ZIP seleccionados desde el explorador de archivos del navegador
    y los guarda directamente en data/raw/, tal como si el usuario los hubiera
    copiado ahí a mano."""
    guardados = []
    for f in request.files.getlist("zips"):
        if f.filename.lower().endswith(".zip"):
            destino = RAW_DIR / Path(f.filename).name  # sin ruta, solo el nombre
            f.save(destino)
            guardados.append(destino.name)
    return jsonify({"guardados": guardados})


@app.route("/list-zips")
def list_zips():
    return jsonify({"zips": sorted(p.name for p in RAW_DIR.glob("*.zip"))})


if __name__ == "__main__":
    print("Panel de control disponible en: http://localhost:5000")
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
