"""
Servidor Minimalista ZKTeco Push (ADMS/iClock)
Solo para recibir asistencias del MB560-VL
"""

from flask import Flask, request, Response
from datetime import datetime
import logging
import os

# ====================== CONFIGURACIÓN ======================
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "5000"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

app = Flask(__name__)

# Lista para guardar las asistencias recibidas (en memoria)
attendance_records = []

# ====================== ENDPOINT PRINCIPAL ======================
@app.route("/iclock/cdata", methods=["POST", "GET"])
def zkteco_cdata():
    """
    Endpoint principal que recibe los datos del dispositivo MB560-VL
    """
    sn = request.args.get("SN", "Desconocido")
    table = request.args.get("table", "")
    stamp = request.args.get("Stamp", "")

    log.info(f"📡 PUSH recibido | SN={sn} | Table={table} | Stamp={stamp}")

    # Respuesta a peticiones GET (verificación de conexión)
    if request.method == "GET":
        return Response("OK", status=200, mimetype="text/plain")

    # Procesar datos enviados por POST
    if request.data:
        try:
            raw_data = request.data.decode("utf-8", errors="ignore").strip()
            
            if table == "ATTLOG" and raw_data:
                lines = raw_data.splitlines()
                for line in lines:
                    if not line.strip():
                        continue
                    
                    parts = line.strip().split("\t")
                    if len(parts) >= 2:
                        user_id = parts[0]
                        timestamp = parts[1]
                        
                        record = {
                            "sn": sn,
                            "user_id": user_id,
                            "timestamp": timestamp,
                            "verified": parts[2] if len(parts) > 2 else None,
                            "status": parts[3] if len(parts) > 3 else None,
                            "received_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "raw": line
                        }
                        
                        attendance_records.append(record)
                        log.info(f"✅ Asistencia guardada → Usuario: {user_id} | Hora: {timestamp} | Dispositivo: {sn}")

            else:
                log.info(f"📋 Otros datos recibidos (tabla: {table}):\n{raw_data[:400]}...")

        except Exception as e:
            log.error(f"❌ Error al procesar datos: {e}")

    # Respuesta obligatoria que el dispositivo ZKTeco espera
    return Response("OK", status=200, mimetype="text/plain")


# ====================== ENDPOINT AUXILIAR ======================
@app.route("/iclock/getrequest", methods=["GET"])
def zkteco_getrequest():
    """Heartbeat - El dispositivo pregunta si hay comandos pendientes"""
    sn = request.args.get("SN", "Desconocido")
    log.debug(f"❤️ Heartbeat recibido del dispositivo SN={sn}")
    return Response("OK", status=200, mimetype="text/plain")


# ====================== RUTAS ÚTILES ======================
@app.route("/", methods=["GET"])
def home():
    return f"""
    <h1>Servidor Push ZKTeco MB560-VL</h1>
    <p><strong>Estado:</strong> ✅ Activo</p>
    <p><strong>Asistencias recibidas:</strong> {len(attendance_records)}</p>
    <p><strong>URL Push:</strong> http://TU_IP:{API_PORT}/iclock/cdata</p>
    <hr>
    <a href="/attendance">Ver últimas asistencias</a>
    """

@app.route("/attendance", methods=["GET"])
def show_attendance():
    """Ver las últimas asistencias recibidas"""
    limit = int(request.args.get("limit", 50))
    recent = attendance_records[-limit:]
    
    html = f"<h1>Últimas {len(recent)} asistencias</h1><table border='1'>"
    html += "<tr><th>Dispositivo</th><th>Usuario</th><th>Hora</th><th>Recibido</th></tr>"
    
    for r in reversed(recent):
        html += f"<tr><td>{r['sn']}</td><td>{r['user_id']}</td><td>{r['timestamp']}</td><td>{r['received_at']}</td></tr>"
    
    html += "</table>"
    return html


# ====================== INICIO ======================
if __name__ == "__main__":
    log.info("=" * 60)
    log.info("🚀 Servidor Push ZKTeco MB560-VL iniciado")
    log.info(f"   Escuchando en → http://0.0.0.0:{API_PORT}")
    log.info(f"   URL para configurar en el dispositivo:")
    log.info(f"   → http://TU_IP_DEL_SERVIDOR:{API_PORT}/iclock/cdata")
    log.info("=" * 60)

    app.run(host=API_HOST, port=API_PORT, debug=False)