"""
Servidor ZKTeco — Multi-dispositivo con gestion via API
Los dispositivos se registran, editan y eliminan mediante endpoints REST.
Se persisten en devices.json automaticamente.

Instalar: pip install flask pyopenssl pyzk
"""

from flask import Flask, request, Response
from datetime import datetime
from zk import ZK
import logging, os, json, threading

# ─────────────────────────────────────────────
# Configuracion del servidor Flask
# ─────────────────────────────────────────────
API_HOST     = os.getenv("API_HOST",   "0.0.0.0")
API_PORT     = int(os.getenv("API_PORT",  "5000"))
CERT_FILE    = os.getenv("CERT_FILE",  "cert.pem")
KEY_FILE     = os.getenv("KEY_FILE",   "key.pem")
DEVICES_FILE = os.getenv("DEVICES_FILE", "devices.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)
app = Flask(__name__)

# ─────────────────────────────────────────────
# Tabla de dedos
# ─────────────────────────────────────────────
DEDOS = {
    0: "Pulgar derecho",   1: "Indice derecho",
    2: "Medio derecho",    3: "Anular derecho",
    4: "Menique derecho",  5: "Pulgar izquierdo",
    6: "Indice izquierdo", 7: "Medio izquierdo",
    8: "Anular izquierdo", 9: "Menique izquierdo",
}

# ─────────────────────────────────────────────
# Gestion de dispositivos en memoria + disco
# ─────────────────────────────────────────────
devices_lock = threading.Lock()  # protege lectura/escritura del registro


def load_devices():
    """Carga dispositivos desde devices.json. Si no existe, carga los de ejemplo."""
    if os.path.exists(DEVICES_FILE):
        with open(DEVICES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    # Dispositivos de ejemplo al arrancar por primera vez
    default = {
        "principal": {
            "ip": "192.168.1.205", "port": 4370,
            "password": 0, "timeout": 5,
            "name": "Entrada Principal",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    }
    save_devices(default)
    return default


def save_devices(data):
    """Persiste el registro de dispositivos en disco."""
    with open(DEVICES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# Carga inicial
DEVICES = load_devices()
log.info(f"Dispositivos cargados: {list(DEVICES.keys())}")


def get_lock(device_id):
    """Retorna (creando si no existe) el lock de un dispositivo."""
    with devices_lock:
        if device_id not in _locks:
            _locks[device_id] = threading.Lock()
        return _locks[device_id]


_locks = {k: threading.Lock() for k in DEVICES}


# ─────────────────────────────────────────────
# SSL
# ─────────────────────────────────────────────
def generar_certificado():
    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        log.info("Certificados SSL encontrados.")
        return True
    try:
        from OpenSSL import crypto
        k = crypto.PKey()
        k.generate_key(crypto.TYPE_RSA, 2048)
        cert = crypto.X509()
        cert.get_subject().CN = "ZKTeco Server"
        cert.set_serial_number(1)
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(365 * 24 * 60 * 60)
        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(k)
        cert.sign(k, "sha256")
        with open(CERT_FILE, "wb") as f:
            f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
        with open(KEY_FILE, "wb") as f:
            f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k))
        log.info("Certificados SSL generados.")
        return True
    except ImportError:
        log.warning("pyopenssl no instalado. Corriendo en HTTP.")
        return False
    except Exception as e:
        log.error(f"Error SSL: {e}")
        return False


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def conectar(device_id):
    cfg = DEVICES[device_id]
    zk  = ZK(cfg["ip"], port=cfg["port"], timeout=cfg["timeout"],
             password=cfg["password"], force_udp=False, ommit_ping=False)
    return zk.connect()


def _json(data, status=200):
    return Response(
        json.dumps(data, ensure_ascii=False, indent=2),
        status=status, mimetype="application/json"
    )


def device_not_found(device_id):
    return _json({
        "success": False,
        "error":   f"Dispositivo '{device_id}' no encontrado.",
        "disponibles": list(DEVICES.keys()),
    }), 404


# ═══════════════════════════════════════════════════════════
# GESTION DE DISPOSITIVOS (CRUD)
# ═══════════════════════════════════════════════════════════

@app.route("/devices", methods=["GET"])
def list_devices():
    """Lista todos los dispositivos registrados."""
    with devices_lock:
        data = [
            {
                "id":         k,
                "name":       v["name"],
                "ip":         v["ip"],
                "port":       v["port"],
                "created_at": v.get("created_at", ""),
            }
            for k, v in DEVICES.items()
        ]
    return _json({"success": True, "total": len(data), "data": data})


@app.route("/devices", methods=["POST"])
def add_device():
    """
    Registra un nuevo dispositivo ZKTeco.
    Body JSON:
    {
        "id":       "bodega",           (requerido - identificador unico)
        "name":     "Bodega Principal", (requerido)
        "ip":       "192.168.1.207",    (requerido)
        "port":     4370,               (opcional, default 4370)
        "password": 0,                  (opcional, default 0)
        "timeout":  5                   (opcional, default 5)
    }
    """
    body = request.get_json(silent=True)
    if not body:
        return _json({"success": False, "error": "Body JSON requerido."}, 400)

    device_id = str(body.get("id",   "")).strip().lower().replace(" ", "_")
    name      = str(body.get("name", "")).strip()
    ip        = str(body.get("ip",   "")).strip()

    if not device_id or not name or not ip:
        return _json({"success": False, "error": "id, name e ip son requeridos."}, 400)

    with devices_lock:
        if device_id in DEVICES:
            return _json({"success": False, "error": f"El id '{device_id}' ya existe."}), 409

        DEVICES[device_id] = {
            "ip":         ip,
            "port":       int(body.get("port",     4370)),
            "password":   int(body.get("password", 0)),
            "timeout":    int(body.get("timeout",  5)),
            "name":       name,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        _locks[device_id] = threading.Lock()
        save_devices(DEVICES)

    log.info(f"Dispositivo registrado: [{device_id}] {name} → {ip}")
    return _json({
        "success": True,
        "message": f"Dispositivo '{device_id}' registrado.",
        "data":    DEVICES[device_id],
    })


@app.route("/devices/<device_id>", methods=["GET"])
def get_device(device_id):
    """Retorna la configuracion de un dispositivo."""
    if device_id not in DEVICES:
        return device_not_found(device_id)
    return _json({"success": True, "data": {**DEVICES[device_id], "id": device_id}})


@app.route("/devices/<device_id>", methods=["PUT"])
def update_device(device_id):
    """
    Actualiza la configuracion de un dispositivo.
    Body JSON (todos opcionales):
    { "name": "Nuevo Nombre", "ip": "192.168.1.210", "port": 4370, "password": 0, "timeout": 5 }
    """
    if device_id not in DEVICES:
        return device_not_found(device_id)

    body = request.get_json(silent=True)
    if not body:
        return _json({"success": False, "error": "Body JSON requerido."}, 400)

    with devices_lock:
        cfg = DEVICES[device_id]
        if "name"     in body: cfg["name"]     = str(body["name"]).strip()
        if "ip"       in body: cfg["ip"]       = str(body["ip"]).strip()
        if "port"     in body: cfg["port"]     = int(body["port"])
        if "password" in body: cfg["password"] = int(body["password"])
        if "timeout"  in body: cfg["timeout"]  = int(body["timeout"])
        cfg["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_devices(DEVICES)

    log.info(f"Dispositivo actualizado: [{device_id}]")
    return _json({"success": True, "message": f"Dispositivo '{device_id}' actualizado.", "data": cfg})


@app.route("/devices/<device_id>", methods=["DELETE"])
def remove_device(device_id):
    """Elimina un dispositivo del registro."""
    if device_id not in DEVICES:
        return device_not_found(device_id)

    with devices_lock:
        del DEVICES[device_id]
        _locks.pop(device_id, None)
        save_devices(DEVICES)

    log.info(f"Dispositivo eliminado: [{device_id}]")
    return _json({"success": True, "message": f"Dispositivo '{device_id}' eliminado."})


@app.route("/devices/<device_id>/ping", methods=["GET"])
def ping_device(device_id):
    """Prueba la conexion con el dispositivo."""
    if device_id not in DEVICES:
        return device_not_found(device_id)

    conn = None
    try:
        log.info(f"[{device_id}] Probando conexion...")
        conn = conectar(device_id)
        t    = conn.get_time()
        return _json({
            "success":     True,
            "message":     f"Conexion exitosa con '{device_id}'.",
            "device_time": str(t),
            "ip":          DEVICES[device_id]["ip"],
        })
    except Exception as e:
        log.error(f"[{device_id}] Ping fallido: {e}")
        return _json({"success": False, "error": str(e), "ip": DEVICES[device_id]["ip"]}), 503
    finally:
        if conn:
            conn.disconnect()


# ═══════════════════════════════════════════════════════════
# ASISTENCIAS — todos los dispositivos
# ═══════════════════════════════════════════════════════════

@app.route("/", methods=["GET"])
def health():
    return _json({
        "status":    "online",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_dispositivos": len(DEVICES),
        "dispositivos": {k: {"ip": v["ip"], "name": v["name"]} for k, v in DEVICES.items()},
    })


@app.route("/attendance/all", methods=["GET"])
def get_all_attendance():
    """
    Asistencias de TODOS los dispositivos en paralelo.
    Filtros: ?user_id=5   ?date=2026-03-03
    """
    uid_f  = request.args.get("user_id")
    date_f = request.args.get("date")
    result = []
    errors = {}
    rlock  = threading.Lock()

    def fetch(device_id):
        with get_lock(device_id):
            conn = None
            try:
                conn = conectar(device_id)
                conn.disable_device()
                registros = conn.get_attendance()
                conn.enable_device()
                parcial = []
                for r in registros:
                    ts = r.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    if uid_f  and str(r.user_id) != str(uid_f): continue
                    if date_f and not ts.startswith(date_f):     continue
                    parcial.append({
                        "user_id":     r.user_id,
                        "timestamp":   ts,
                        "status":      r.status,
                        "punch":       r.punch,
                        "device_id":   device_id,
                        "device_name": DEVICES[device_id]["name"],
                    })
                with rlock:
                    result.extend(parcial)
            except Exception as e:
                with rlock:
                    errors[device_id] = str(e)
                log.error(f"[{device_id}] Error fetch: {e}")
            finally:
                if conn:
                    try: conn.enable_device()
                    except: pass
                    conn.disconnect()

    with devices_lock:
        device_ids = list(DEVICES.keys())

    threads = [threading.Thread(target=fetch, args=(d,)) for d in device_ids]
    for t in threads: t.start()
    for t in threads: t.join()
    result.sort(key=lambda x: x["timestamp"], reverse=True)
    return _json({"success": True, "total": len(result), "errors": errors, "data": result})


# ═══════════════════════════════════════════════════════════
# ENDPOINTS POR DISPOSITIVO   /devices/{id}/...
# ═══════════════════════════════════════════════════════════

@app.route("/devices/<device_id>/info", methods=["GET"])
def device_info(device_id):
    """Info tecnica del dispositivo."""
    if device_id not in DEVICES: return device_not_found(device_id)
    with get_lock(device_id):
        conn = None
        try:
            conn = conectar(device_id)
            conn.disable_device()
            data = {
                "id":               device_id,
                "name":             DEVICES[device_id]["name"],
                "ip":               DEVICES[device_id]["ip"],
                "serialnumber":     conn.get_serialnumber(),
                "device_name":      conn.get_device_name(),
                "platform":         conn.get_platform(),
                "firmware_version": conn.get_firmware_version(),
                "users_count":      len(conn.get_users()),
                "device_time":      str(conn.get_time()),
            }
            conn.enable_device()
            return _json({"success": True, "data": data})
        except Exception as e:
            return _json({"success": False, "error": str(e)}), 500
        finally:
            if conn:
                try: conn.enable_device()
                except: pass
                conn.disconnect()


@app.route("/devices/<device_id>/attendance", methods=["GET"])
def get_attendance(device_id):
    """Asistencias de un dispositivo. Filtros: ?user_id=5  ?date=2026-03-03"""
    if device_id not in DEVICES: return device_not_found(device_id)
    uid_f  = request.args.get("user_id")
    date_f = request.args.get("date")
    with get_lock(device_id):
        conn = None
        try:
            conn = conectar(device_id)
            conn.disable_device()
            registros = conn.get_attendance()
            conn.enable_device()
            result = []
            for r in registros:
                ts = r.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                if uid_f  and str(r.user_id) != str(uid_f): continue
                if date_f and not ts.startswith(date_f):     continue
                result.append({
                    "user_id":     r.user_id,
                    "timestamp":   ts,
                    "status":      r.status,
                    "punch":       r.punch,
                    "device_id":   device_id,
                    "device_name": DEVICES[device_id]["name"],
                })
            result.sort(key=lambda x: x["timestamp"], reverse=True)
            return _json({"success": True, "total": len(result), "data": result})
        except Exception as e:
            return _json({"success": False, "error": str(e)}), 500
        finally:
            if conn:
                try: conn.enable_device()
                except: pass
                conn.disconnect()


@app.route("/devices/<device_id>/users", methods=["GET"])
def get_users(device_id):
    """Lista usuarios del dispositivo."""
    if device_id not in DEVICES: return device_not_found(device_id)
    with get_lock(device_id):
        conn = None
        try:
            conn = conectar(device_id)
            conn.disable_device()
            users = conn.get_users()
            conn.enable_device()
            result = [{
                "uid": u.uid, "user_id": u.user_id, "name": u.name,
                "privilege": u.privilege, "card": u.card, "device_id": device_id,
            } for u in users]
            return _json({"success": True, "total": len(result), "data": result})
        except Exception as e:
            return _json({"success": False, "error": str(e)}), 500
        finally:
            if conn:
                try: conn.enable_device()
                except: pass
                conn.disconnect()


@app.route("/devices/<device_id>/users", methods=["POST"])
def create_user(device_id):
    """
    Crea un usuario en el dispositivo.
    Body: { "user_id": "123", "name": "Juan", "password": "", "privilege": 0, "card": 0 }
    """
    if device_id not in DEVICES: return device_not_found(device_id)
    body = request.get_json(silent=True)
    if not body: return _json({"success": False, "error": "Body JSON requerido."}, 400)
    user_id   = str(body.get("user_id",  "")).strip()
    name      = str(body.get("name",     "")).strip()
    password  = str(body.get("password", "")).strip()
    privilege = int(body.get("privilege", 0))
    card      = int(body.get("card",      0))
    if not user_id or not name:
        return _json({"success": False, "error": "user_id y name son requeridos."}, 400)
    with get_lock(device_id):
        conn = None
        try:
            conn = conectar(device_id)
            conn.disable_device()
            for u in conn.get_users():
                if str(u.user_id) == str(user_id):
                    conn.enable_device()
                    return _json({"success": False, "error": f"user_id '{user_id}' ya existe."}), 409
            conn.set_user(uid=None, name=name, privilege=privilege,
                          password=password, group_id="", user_id=user_id, card=card)
            conn.enable_device()
            return _json({"success": True, "message": "Usuario registrado.",
                          "data": {"user_id": user_id, "name": name, "device_id": device_id}})
        except Exception as e:
            return _json({"success": False, "error": str(e)}), 500
        finally:
            if conn:
                try: conn.enable_device()
                except: pass
                conn.disconnect()


@app.route("/devices/<device_id>/users/<user_id>", methods=["PUT"])
def update_user(device_id, user_id):
    """Actualiza un usuario. Body: { name, password, privilege, card }"""
    if device_id not in DEVICES: return device_not_found(device_id)
    body = request.get_json(silent=True)
    if not body: return _json({"success": False, "error": "Body JSON requerido."}, 400)
    with get_lock(device_id):
        conn = None
        try:
            conn = conectar(device_id)
            conn.disable_device()
            u = next((u for u in conn.get_users() if str(u.user_id) == str(user_id)), None)
            if not u:
                conn.enable_device()
                return _json({"success": False, "error": f"Usuario '{user_id}' no encontrado."}), 404
            conn.set_user(uid=u.uid, name=body.get("name", u.name),
                          privilege=int(body.get("privilege", u.privilege)),
                          password=body.get("password", u.password),
                          group_id=u.group_id, user_id=u.user_id,
                          card=int(body.get("card", u.card)))
            conn.enable_device()
            return _json({"success": True, "message": f"Usuario '{user_id}' actualizado."})
        except Exception as e:
            return _json({"success": False, "error": str(e)}), 500
        finally:
            if conn:
                try: conn.enable_device()
                except: pass
                conn.disconnect()


@app.route("/devices/<device_id>/users/<user_id>", methods=["DELETE"])
def delete_user(device_id, user_id):
    """Elimina un usuario del dispositivo."""
    if device_id not in DEVICES: return device_not_found(device_id)
    with get_lock(device_id):
        conn = None
        try:
            conn = conectar(device_id)
            conn.disable_device()
            u = next((u for u in conn.get_users() if str(u.user_id) == str(user_id)), None)
            if not u:
                conn.enable_device()
                return _json({"success": False, "error": f"Usuario '{user_id}' no encontrado."}), 404
            conn.delete_user(uid=u.uid)
            conn.enable_device()
            return _json({"success": True, "message": f"Usuario '{user_id}' eliminado."})
        except Exception as e:
            return _json({"success": False, "error": str(e)}), 500
        finally:
            if conn:
                try: conn.enable_device()
                except: pass
                conn.disconnect()


@app.route("/devices/<device_id>/users/<user_id>/enroll-finger", methods=["POST"])
def enroll_finger(device_id, user_id):
    """
    Activa el modo enrolamiento de huella en el dispositivo.
    Body: { "finger_index": 0 }  (0-9)
    """
    if device_id not in DEVICES: return device_not_found(device_id)
    body         = request.get_json(silent=True) or {}
    finger_index = int(body.get("finger_index", 0))
    if not (0 <= finger_index <= 9):
        return _json({"success": False, "error": "finger_index debe ser 0-9."}, 400)
    with get_lock(device_id):
        conn = None
        try:
            conn = conectar(device_id)
            conn.disable_device()
            u = next((u for u in conn.get_users() if str(u.user_id) == str(user_id)), None)
            if not u:
                conn.enable_device()
                return _json({"success": False, "error": f"Usuario '{user_id}' no encontrado."}), 404
            conn.enroll_user(uid=u.uid, temp_id=finger_index)
            conn.enable_device()
            return _json({
                "success": True,
                "message": "Modo enrolamiento activado. El usuario debe poner el dedo 3 veces.",
                "data": {
                    "user_id":      user_id,
                    "device_id":    device_id,
                    "finger_index": finger_index,
                    "finger_name":  DEDOS[finger_index],
                },
            })
        except Exception as e:
            return _json({"success": False, "error": str(e)}), 500
        finally:
            if conn:
                try: conn.enable_device()
                except: pass
                conn.disconnect()


@app.route("/devices/<device_id>/users/<user_id>/fingers", methods=["GET"])
def get_fingers(device_id, user_id):
    """Huellas registradas de un usuario en el dispositivo."""
    if device_id not in DEVICES: return device_not_found(device_id)
    with get_lock(device_id):
        conn = None
        try:
            conn = conectar(device_id)
            conn.disable_device()
            u = next((u for u in conn.get_users() if str(u.user_id) == str(user_id)), None)
            if not u:
                conn.enable_device()
                return _json({"success": False, "error": f"Usuario '{user_id}' no encontrado."}), 404
            templates = conn.get_templates()
            conn.enable_device()
            huellas = [
                {"finger_index": t.fid, "finger_name": DEDOS.get(t.fid, f"Dedo {t.fid}"), "valid": t.valid}
                for t in templates if str(t.uid) == str(u.uid)
            ]
            return _json({"success": True, "user_id": user_id, "name": u.name,
                           "device_id": device_id, "total_fingers": len(huellas), "data": huellas})
        except Exception as e:
            return _json({"success": False, "error": str(e)}), 500
        finally:
            if conn:
                try: conn.enable_device()
                except: pass
                conn.disconnect()


@app.route("/devices/<device_id>/time", methods=["GET"])
def get_time(device_id):
    """Hora actual del dispositivo."""
    if device_id not in DEVICES: return device_not_found(device_id)
    with get_lock(device_id):
        conn = None
        try:
            conn = conectar(device_id)
            t = conn.get_time()
            return _json({"success": True, "device_id": device_id, "device_time": str(t)})
        except Exception as e:
            return _json({"success": False, "error": str(e)}), 500
        finally:
            if conn: conn.disconnect()


@app.route("/devices/<device_id>/sync-time", methods=["POST"])
def sync_time(device_id):
    """Sincroniza la hora del dispositivo con el servidor."""
    if device_id not in DEVICES: return device_not_found(device_id)
    with get_lock(device_id):
        conn = None
        try:
            conn = conectar(device_id)
            conn.set_time(datetime.now())
            return _json({"success": True, "message": f"[{device_id}] Hora sincronizada."})
        except Exception as e:
            return _json({"success": False, "error": str(e)}), 500
        finally:
            if conn: conn.disconnect()


# ── Inicio ────────────────────────────────────
if __name__ == "__main__":
    ssl_ok = generar_certificado()
    proto  = "https" if ssl_ok else "http"

    log.info(f"{'='*58}")
    log.info(f"  Servidor ZKTeco — Multi-dispositivo dinamico")
    log.info(f"  {proto}://{API_HOST}:{API_PORT}")
    log.info(f"  Dispositivos activos: {len(DEVICES)}")
    for did, cfg in DEVICES.items():
        log.info(f"    [{did}]  {cfg['name']}  →  {cfg['ip']}:{cfg['port']}")
    log.info(f"{'='*58}")
    log.info(f"  Gestion de dispositivos:")
    log.info(f"  GET    /devices                  → listar")
    log.info(f"  POST   /devices                  → agregar")
    log.info(f"  GET    /devices/{{id}}              → ver uno")
    log.info(f"  PUT    /devices/{{id}}              → editar")
    log.info(f"  DELETE /devices/{{id}}              → eliminar")
    log.info(f"  GET    /devices/{{id}}/ping         → probar conexion")
    log.info(f"{'='*58}")
    log.info(f"  Operaciones:")
    log.info(f"  GET    /attendance/all            → todos los dispositivos")
    log.info(f"  GET    /devices/{{id}}/attendance   → un dispositivo")
    log.info(f"  GET    /devices/{{id}}/users        → listar usuarios")
    log.info(f"  POST   /devices/{{id}}/users        → crear usuario")
    log.info(f"  PUT    /devices/{{id}}/users/{{uid}}  → actualizar usuario")
    log.info(f"  DELETE /devices/{{id}}/users/{{uid}}  → eliminar usuario")
    log.info(f"  POST   /devices/{{id}}/users/{{uid}}/enroll-finger")
    log.info(f"  GET    /devices/{{id}}/users/{{uid}}/fingers")
    log.info(f"{'='*58}")

    if ssl_ok:
        app.run(host=API_HOST, port=API_PORT, debug=False, ssl_context=(CERT_FILE, KEY_FILE))
    else:
        app.run(host=API_HOST, port=API_PORT, debug=False)