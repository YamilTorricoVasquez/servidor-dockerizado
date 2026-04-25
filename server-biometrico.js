/**
 * Servidor ZKTeco - Dispositivo único con gestión vía API
 * Instalación: npm install express zkteco-js
 */

const express = require('express');
const fs = require('fs');
const path = require('path');
const ZKLib = require('zkteco-js');

// ─────────────────────────────────────────────
// Configuración del servidor
// ─────────────────────────────────────────────
const API_HOST = process.env.API_HOST || '0.0.0.0';
const API_PORT = parseInt(process.env.API_PORT || '9000');
const DEVICE_FILE = process.env.DEVICE_FILE || 'device.json';

const app = express();
app.use(express.json());

// ─────────────────────────────────────────────
// Tabla de dedos
// ─────────────────────────────────────────────
const DEDOS = {
    0: "Pulgar derecho",
    1: "Índice derecho",
    2: "Medio derecho",
    3: "Anular derecho",
    4: "Meñique derecho",
    5: "Pulgar izquierdo",
    6: "Índice izquierdo",
    7: "Medio izquierdo",
    8: "Anular izquierdo",
    9: "Meñique izquierdo"
};

// ─────────────────────────────────────────────
// Gestión del dispositivo único
// ─────────────────────────────────────────────
let DEVICE = null;
let zkInstance = null;

function loadDevice() {
    if (fs.existsSync(DEVICE_FILE)) {
        const data = fs.readFileSync(DEVICE_FILE, 'utf-8');
        return JSON.parse(data);
    }
    // Dispositivo por defecto
    const defaultDevice = {
        ip: "192.168.1.205",
        port: 4370,
        timeout: 5000,
        name: "Entrada Principal",
        created_at: new Date().toISOString()
    };
    saveDevice(defaultDevice);
    return defaultDevice;
}

function saveDevice(data) {
    fs.writeFileSync(DEVICE_FILE, JSON.stringify(data, null, 2), 'utf-8');
}

function deleteDevice() {
    if (fs.existsSync(DEVICE_FILE)) {
        fs.unlinkSync(DEVICE_FILE);
    }
    DEVICE = null;
}

// Cargar dispositivo al iniciar
DEVICE = loadDevice();
console.log(`[INFO] Dispositivo cargado: ${DEVICE.name} (${DEVICE.ip}:${DEVICE.port})`);

// ─────────────────────────────────────────────
// Helpers de conexión
// ─────────────────────────────────────────────
async function conectar() {
    if (!DEVICE) {
        throw new Error('No hay dispositivo configurado');
    }

    const zk = new ZKLib(DEVICE.ip, DEVICE.port, DEVICE.timeout, 4000);

    try {
        await zk.createSocket();
        zkInstance = zk;
        return zk;
    } catch (err) {
        throw new Error(`Error al conectar: ${err.message}`);
    }
}

async function desconectar(zk) {
    if (zk) {
        try {
            await zk.disconnect();
        } catch (err) {
            console.error('[ERROR] Error al desconectar:', err.message);
        }
    }
}

function jsonResponse(res, data, status = 200) {
    res.status(status).json(data);
}

// ═══════════════════════════════════════════════════════════
// GESTIÓN DEL DISPOSITIVO
// ═══════════════════════════════════════════════════════════

app.get('/device', (req, res) => {
    if (!DEVICE) {
        return jsonResponse(res, {
            success: false,
            error: 'No hay dispositivo configurado'
        }, 404);
    }

    jsonResponse(res, {
        success: true,
        data: DEVICE
    });
});

app.post('/device', (req, res) => {
    const { name, ip, port, timeout } = req.body;

    if (!name || !ip) {
        return jsonResponse(res, {
            success: false,
            error: 'name e ip son requeridos'
        }, 400);
    }

    DEVICE = {
        ip: ip.trim(),
        port: parseInt(port || 4370),
        timeout: parseInt(timeout || 5000),
        name: name.trim(),
        created_at: new Date().toISOString()
    };

    saveDevice(DEVICE);

    console.log(`[INFO] Dispositivo configurado: ${DEVICE.name} → ${DEVICE.ip}:${DEVICE.port}`);

    jsonResponse(res, {
        success: true,
        message: 'Dispositivo configurado correctamente',
        data: DEVICE
    });
});

app.put('/device', (req, res) => {
    if (!DEVICE) {
        return jsonResponse(res, {
            success: false,
            error: 'No hay dispositivo configurado'
        }, 404);
    }

    const { name, ip, port, timeout } = req.body;

    if (name) DEVICE.name = name.trim();
    if (ip) DEVICE.ip = ip.trim();
    if (port) DEVICE.port = parseInt(port);
    if (timeout) DEVICE.timeout = parseInt(timeout);

    DEVICE.updated_at = new Date().toISOString();
    saveDevice(DEVICE);

    console.log(`[INFO] Dispositivo actualizado: ${DEVICE.name}`);

    jsonResponse(res, {
        success: true,
        message: 'Dispositivo actualizado',
        data: DEVICE
    });
});

app.delete('/device', (req, res) => {
    if (!DEVICE) {
        return jsonResponse(res, {
            success: false,
            error: 'No hay dispositivo configurado'
        }, 404);
    }

    const deviceName = DEVICE.name;
    deleteDevice();

    console.log(`[INFO] Dispositivo eliminado: ${deviceName}`);

    jsonResponse(res, {
        success: true,
        message: 'Dispositivo eliminado'
    });
});

app.get('/device/ping', async (req, res) => {
    if (!DEVICE) {
        return jsonResponse(res, {
            success: false,
            error: 'No hay dispositivo configurado'
        }, 404);
    }

    let zk = null;
    try {
        console.log(`[INFO] Probando conexión con ${DEVICE.ip}...`);
        zk = await conectar();
        const deviceTime = await zk.getTime();

        jsonResponse(res, {
            success: true,
            message: 'Conexión exitosa',
            device_time: deviceTime.toString(),
            ip: DEVICE.ip
        });
    } catch (err) {
        console.error(`[ERROR] Ping fallido: ${err.message}`);
        jsonResponse(res, {
            success: false,
            error: err.message,
            ip: DEVICE.ip
        }, 503);
    } finally {
        await desconectar(zk);
    }
});

// ═══════════════════════════════════════════════════════════
// ENDPOINTS DE OPERACIÓN
// ═══════════════════════════════════════════════════════════

app.get('/', (req, res) => {
    jsonResponse(res, {
        status: 'online',
        timestamp: new Date().toISOString(),
        device: DEVICE ? {
            name: DEVICE.name,
            ip: DEVICE.ip,
            port: DEVICE.port
        } : null
    });
});

app.get('/device/info', async (req, res) => {
    if (!DEVICE) {
        return jsonResponse(res, {
            success: false,
            error: 'No hay dispositivo configurado'
        }, 404);
    }

    let zk = null;
    try {
        zk = await conectar();
        await zk.disableDevice();

        const users = await zk.getUsers();
        const info = await zk.getInfo();

        await zk.enableDevice();

        jsonResponse(res, {
            success: true,
            data: {
                name: DEVICE.name,
                ip: DEVICE.ip,
                port: DEVICE.port,
                serialnumber: info.serialNumber || '',
                firmware_version: info.fwVersion || '',
                platform: info.platform || '',
                users_count: users.data.length,
                device_time: new Date().toISOString()
            }
        });
    } catch (err) {
        jsonResponse(res, {
            success: false,
            error: err.message
        }, 500);
    } finally {
        if (zk) {
            try {
                await zk.enableDevice();
            } catch (e) { }
        }
        await desconectar(zk);
    }
});

app.get('/attendance', async (req, res) => {
    if (!DEVICE) {
        return jsonResponse(res, {
            success: false,
            error: 'No hay dispositivo configurado'
        }, 404);
    }

    const { user_id, date } = req.query;
    let zk = null;

    try {
        zk = await conectar();
        await zk.disableDevice();

        const attendance = await zk.getAttendances();
        await zk.enableDevice();

        let result = attendance.data.map(r => ({
            user_id: r.deviceUserId,
            timestamp: r.recordTime,
            status: r.verifyMode || 0,
            punch: r.inOutMode || 0,
            device_name: DEVICE.name
        }));

        // Filtros
        if (user_id) {
            result = result.filter(r => r.user_id.toString() === user_id.toString());
        }
        if (date) {
            result = result.filter(r => r.timestamp.startsWith(date));
        }

        result.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

        jsonResponse(res, {
            success: true,
            total: result.length,
            data: result
        });
    } catch (err) {
        jsonResponse(res, {
            success: false,
            error: err.message
        }, 500);
    } finally {
        if (zk) {
            try {
                await zk.enableDevice();
            } catch (e) { }
        }
        await desconectar(zk);
    }
});

app.get('/users', async (req, res) => {
    if (!DEVICE) {
        return jsonResponse(res, {
            success: false,
            error: 'No hay dispositivo configurado'
        }, 404);
    }

    let zk = null;
    try {
        zk = await conectar();
        await zk.disableDevice();

        const users = await zk.getUsers();
        await zk.enableDevice();

        const result = users.data.map(u => ({
            uid: u.uid,
            user_id: u.userId,
            name: u.name,
            privilege: u.role || 0,
            password: u.password || '',
            card: u.cardno || 0
        }));

        jsonResponse(res, {
            success: true,
            total: result.length,
            data: result
        });
    } catch (err) {
        jsonResponse(res, {
            success: false,
            error: err.message
        }, 500);
    } finally {
        if (zk) {
            try {
                await zk.enableDevice();
            } catch (e) { }
        }
        await desconectar(zk);
    }
});

app.post('/users', async (req, res) => {
    if (!DEVICE) {
        return jsonResponse(res, {
            success: false,
            error: 'No hay dispositivo configurado'
        }, 404);
    }

    const { user_id, name, password, privilege, card } = req.body;

    if (!user_id || !name) {
        return jsonResponse(res, {
            success: false,
            error: 'user_id y name son requeridos'
        }, 400);
    }

    let zk = null;
    try {
        zk = await conectar();
        await zk.disableDevice();

        const users = await zk.getUsers();
        const existe = users.data.find(u => u.userId.toString() === user_id.toString());

        if (existe) {
            await zk.enableDevice();
            return jsonResponse(res, {
                success: false,
                error: `user_id '${user_id}' ya existe`
            }, 409);
        }

        await zk.setUser(user_id, {
            name: name,
            password: password || '',
            role: privilege || 0,
            cardno: card || 0
        });

        await zk.enableDevice();

        jsonResponse(res, {
            success: true,
            message: 'Usuario registrado',
            data: { user_id, name }
        });
    } catch (err) {
        jsonResponse(res, {
            success: false,
            error: err.message
        }, 500);
    } finally {
        if (zk) {
            try {
                await zk.enableDevice();
            } catch (e) { }
        }
        await desconectar(zk);
    }
});

app.put('/users/:user_id', async (req, res) => {
    if (!DEVICE) {
        return jsonResponse(res, {
            success: false,
            error: 'No hay dispositivo configurado'
        }, 404);
    }

    const { user_id } = req.params;
    const { name, password, privilege, card } = req.body;

    let zk = null;
    try {
        zk = await conectar();
        await zk.disableDevice();

        const users = await zk.getUsers();
        const usuario = users.data.find(u => u.userId.toString() === user_id.toString());

        if (!usuario) {
            await zk.enableDevice();
            return jsonResponse(res, {
                success: false,
                error: `Usuario '${user_id}' no encontrado`
            }, 404);
        }

        await zk.setUser(user_id, {
            name: name || usuario.name,
            password: password !== undefined ? password : usuario.password,
            role: privilege !== undefined ? privilege : usuario.role,
            cardno: card !== undefined ? card : usuario.cardno
        });

        await zk.enableDevice();

        jsonResponse(res, {
            success: true,
            message: `Usuario '${user_id}' actualizado`
        });
    } catch (err) {
        jsonResponse(res, {
            success: false,
            error: err.message
        }, 500);
    } finally {
        if (zk) {
            try {
                await zk.enableDevice();
            } catch (e) { }
        }
        await desconectar(zk);
    }
});

app.delete('/users/:user_id', async (req, res) => {
    if (!DEVICE) {
        return jsonResponse(res, {
            success: false,
            error: 'No hay dispositivo configurado'
        }, 404);
    }

    const { user_id } = req.params;
    let zk = null;

    try {
        zk = await conectar();
        await zk.disableDevice();

        const users = await zk.getUsers();
        const usuario = users.data.find(u => u.userId.toString() === user_id.toString());

        if (!usuario) {
            await zk.enableDevice();
            return jsonResponse(res, {
                success: false,
                error: `Usuario '${user_id}' no encontrado`
            }, 404);
        }

        await zk.deleteUser(usuario.uid);
        await zk.enableDevice();

        jsonResponse(res, {
            success: true,
            message: `Usuario '${user_id}' eliminado`
        });
    } catch (err) {
        jsonResponse(res, {
            success: false,
            error: err.message
        }, 500);
    } finally {
        if (zk) {
            try {
                await zk.enableDevice();
            } catch (e) { }
        }
        await desconectar(zk);
    }
});

app.get('/time', async (req, res) => {
    if (!DEVICE) {
        return jsonResponse(res, {
            success: false,
            error: 'No hay dispositivo configurado'
        }, 404);
    }

    let zk = null;
    try {
        zk = await conectar();
        const deviceTime = await zk.getTime();

        jsonResponse(res, {
            success: true,
            device_time: deviceTime.toString()
        });
    } catch (err) {
        jsonResponse(res, {
            success: false,
            error: err.message
        }, 500);
    } finally {
        await desconectar(zk);
    }
});

app.post('/sync-time', async (req, res) => {
    if (!DEVICE) {
        return jsonResponse(res, {
            success: false,
            error: 'No hay dispositivo configurado'
        }, 404);
    }

    let zk = null;
    try {
        zk = await conectar();
        await zk.setTime(new Date());

        jsonResponse(res, {
            success: true,
            message: 'Hora sincronizada'
        });
    } catch (err) {
        jsonResponse(res, {
            success: false,
            error: err.message
        }, 500);
    } finally {
        await desconectar(zk);
    }
});

// ── Inicio ────────────────────────────────────
app.listen(API_PORT, API_HOST, () => {
    console.log('='.repeat(58));
    console.log('  Servidor ZKTeco - Dispositivo único');
    console.log(`  http://${API_HOST}:${API_PORT}`);
    if (DEVICE) {
        console.log(`  Dispositivo: ${DEVICE.name} → ${DEVICE.ip}:${DEVICE.port}`);
    } else {
        console.log('  Sin dispositivo configurado');
    }
    console.log('='.repeat(58));
    console.log('  Gestión del dispositivo:');
    console.log('  GET    /device                → ver configuración');
    console.log('  POST   /device                → configurar');
    console.log('  PUT    /device                → actualizar');
    console.log('  DELETE /device                → eliminar');
    console.log('  GET    /device/ping           → probar conexión');
    console.log('  GET    /device/info           → info técnica');
    console.log('='.repeat(58));
    console.log('  Operaciones:');
    console.log('  GET    /attendance            → asistencias');
    console.log('  GET    /users                 → listar usuarios');
    console.log('  POST   /users                 → crear usuario');
    console.log('  PUT    /users/:user_id        → actualizar usuario');
    console.log('  DELETE /users/:user_id        → eliminar usuario');
    console.log('  GET    /time                  → hora del dispositivo');
    console.log('  POST   /sync-time             → sincronizar hora');
    console.log('='.repeat(58));
});