from flask import Flask, request, Response
from datetime import datetime
import logging
import os
import psycopg2

# ================= CONFIG =================
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "5000"))

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

log = logging.getLogger(__name__)

app = Flask(__name__)

# ================= DB =================
def get_db():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id SERIAL PRIMARY KEY,
        sn TEXT,
        user_id TEXT,
        timestamp TEXT,
        verified TEXT,
        status TEXT,
        received_at TEXT,
        raw TEXT
    )
    """)

    conn.commit()
    cur.close()
    conn.close()

init_db()

# ================= PUSH =================
@app.route("/iclock/cdata", methods=["POST", "GET"])
def zkteco_cdata():

    sn = request.args.get("SN", "Desconocido")
    table = request.args.get("table", "")
    stamp = request.args.get("Stamp", "")

    log.info(f"📡 PUSH | SN={sn} | Table={table} | Stamp={stamp}")

    if request.method == "GET":
        return Response("OK", 200)

    if request.data:

        raw_data = request.data.decode("utf-8", errors="ignore").strip()

        if table == "ATTLOG":

            lines = raw_data.splitlines()

            for line in lines:
                if not line.strip():
                    continue

                parts = line.split("\t")

                if len(parts) >= 2:

                    record = {
                        "sn": sn,
                        "user_id": parts[0],
                        "timestamp": parts[1],
                        "verified": parts[2] if len(parts) > 2 else None,
                        "status": parts[3] if len(parts) > 3 else None,
                        "received_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "raw": line
                    }

                    # GUARDAR EN POSTGRES
                    conn = get_db()
                    cur = conn.cursor()

                    cur.execute("""
                        INSERT INTO attendance 
                        (sn, user_id, timestamp, verified, status, received_at, raw)
                        VALUES (%s,%s,%s,%s,%s,%s,%s)
                    """, (
                        record["sn"],
                        record["user_id"],
                        record["timestamp"],
                        record["verified"],
                        record["status"],
                        record["received_at"],
                        record["raw"]
                    ))

                    conn.commit()
                    cur.close()
                    conn.close()

                    log.info(f"✅ Guardado usuario {record['user_id']}")

    return Response("OK", 200)

# ================= HEARTBEAT =================
@app.route("/iclock/getrequest", methods=["GET"])
def heartbeat():
    return Response("OK", 200)

# ================= VIEW =================
@app.route("/attendance", methods=["GET"])
def show():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT sn, user_id, timestamp, received_at
        FROM attendance
        ORDER BY id DESC
        LIMIT 50
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    html = "<h1>Asistencias</h1><table border=1>"
    html += "<tr><th>SN</th><th>User</th><th>Hora</th><th>Recibido</th></tr>"

    for r in rows:
        html += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td></tr>"

    html += "</table>"

    return html

# ================= RUN =================
if __name__ == "__main__":
    log.info("🚀 Servidor ZKTeco iniciado")
    app.run(host=API_HOST, port=API_PORT)