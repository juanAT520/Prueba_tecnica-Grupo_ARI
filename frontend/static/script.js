// script.js
// ----------
// Lógica del panel de control. No usa ningún framework, solo JavaScript
// normal del navegador. Se apoya en dos piezas:
//   - fetch(): para peticiones normales (subir ficheros, listar ZIP).
//   - EventSource: para recibir la salida de los scripts de Python en
//     vivo, línea a línea, según se va generando (Server-Sent Events).

const log = document.getElementById("log");
const pasosEl = document.querySelectorAll(".paso");
const siguientePasoEl = document.getElementById("siguiente-paso");

const NOMBRES_PASOS = {
  1: "1. Extraer precios de carburantes",
  2: "2. Subir y descomprimir ZIP de matriculaciones",
  3: "3. Transformar matriculaciones",
  4: "4. Cargar a base de datos",
};

let ultimosZipsSubidos = [];

function escribirLog(texto) {
  log.textContent += "\n" + texto;
  log.scrollTop = log.scrollHeight; // autoscroll hacia abajo
}

function marcarPaso(numero, estado) {
  // estado: "activo" o "hecho"
  const el = document.querySelector(`.paso[data-paso="${numero}"]`);
  if (!el) return;
  el.classList.remove("activo", "hecho");
  el.classList.add(estado);
}

function actualizarSiguientePaso(numeroCompletado) {
  const siguiente = numeroCompletado + 1;
  if (NOMBRES_PASOS[siguiente]) {
    siguientePasoEl.innerHTML = `Siguiente paso sugerido: <strong>${NOMBRES_PASOS[siguiente]}</strong>`;
  } else {
    siguientePasoEl.innerHTML = `<strong>Pipeline completo.</strong> Abre ahora el archivo .pbix en Power BI Desktop para ver el dashboard.`;
  }
}

// Ejecuta uno de los scripts principales (carburantes / transformar / cargar)
// y va mostrando su salida en el panel de log en tiempo real.
function ejecutarPaso(nombreInterno, numeroPaso) {
  marcarPaso(numeroPaso, "activo");
  escribirLog(`\n--- Ejecutando paso ${numeroPaso}: ${nombreInterno} ---`);
  desactivarBotones(true);

  const origen = new EventSource(`/run/${nombreInterno}`);

  origen.onmessage = (evento) => {
    if (evento.data === "[FIN_OK]") {
      escribirLog("--- Paso completado correctamente ---");
      marcarPaso(numeroPaso, "hecho");
      actualizarSiguientePaso(numeroPaso);
      origen.close();
      desactivarBotones(false);
    } else if (evento.data.startsWith("[FIN_ERROR]")) {
      escribirLog(`--- ERROR: ${evento.data} ---`);
      origen.close();
      desactivarBotones(false);
    } else {
      escribirLog(evento.data);
    }
  };

  origen.onerror = () => {
    escribirLog("--- Conexión con el servidor interrumpida ---");
    origen.close();
    desactivarBotones(false);
  };
}

// Descomprime e inspecciona un ZIP concreto ya subido a data/raw/
function inspeccionarZip(nombreZip) {
  return new Promise((resolve) => {
    escribirLog(`\n--- Descomprimiendo ${nombreZip} ---`);
    const origen = new EventSource(`/run/inspeccionar?zip=${encodeURIComponent(nombreZip)}`);
    origen.onmessage = (evento) => {
      if (evento.data === "[FIN_OK]" || evento.data.startsWith("[FIN_ERROR]")) {
        escribirLog(evento.data === "[FIN_OK]" ? `--- ${nombreZip} listo ---` : evento.data);
        origen.close();
        resolve();
      } else {
        escribirLog(evento.data);
      }
    };
    origen.onerror = () => { origen.close(); resolve(); };
  });
}

// Sube al servidor los ZIP elegidos con el explorador de archivos
document.getElementById("input-zips").addEventListener("change", async (evento) => {
  const ficheros = evento.target.files;
  if (ficheros.length === 0) return;

  const datosFormulario = new FormData();
  for (const f of ficheros) datosFormulario.append("zips", f);

  escribirLog(`\n--- Subiendo ${ficheros.length} fichero(s) ZIP ---`);
  const respuesta = await fetch("/upload-zips", { method: "POST", body: datosFormulario });
  const resultado = await respuesta.json();
  ultimosZipsSubidos = resultado.guardados;

  const lista = document.getElementById("lista-zips");
  lista.innerHTML = "";
  resultado.guardados.forEach((nombre) => {
    const item = document.createElement("li");
    item.textContent = nombre;
    lista.appendChild(item);
  });

  escribirLog(`--- ${resultado.guardados.length} fichero(s) guardados en data/raw/ ---`);
  document.getElementById("btn-descomprimir").disabled = resultado.guardados.length === 0;
});

// Descomprime, uno detrás de otro, todos los ZIP que hay ahora mismo en data/raw/
async function descomprimirTodos() {
  if (ultimosZipsSubidos.length === 0) {
    escribirLog("\n--- No hay ZIP recién subidos que descomprimir ---");
    return;
  }

  marcarPaso(2, "activo");
  desactivarBotones(true);

  for (const nombreZip of ultimosZipsSubidos) {
    await inspeccionarZip(nombreZip);
  }

  escribirLog("--- ZIP seleccionados descomprimidos ---");
  marcarPaso(2, "hecho");
  actualizarSiguientePaso(2);
  desactivarBotones(false);
}

// Evita que se lancen varios scripts a la vez sin querer
function desactivarBotones(desactivar) {
  document.querySelectorAll("button").forEach((b) => (b.disabled = desactivar));
  if (!desactivar) {
    // Vuelve a activar "Descomprimir" solo si ya hay ZIP subidos
    const hayZips = document.getElementById("lista-zips").children.length > 0;
    document.getElementById("btn-descomprimir").disabled = !hayZips;
  }
}
