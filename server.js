"use strict";
const net = require('net');
const express = require('express');
const IntegrationPos = require('integration-pos-service');

// Configuración desde variables de entorno o valores por defecto
const HTTP_PORT = process.env.HTTP_PORT || 8000;
const TCP_PORT = process.env.TCP_PORT || 5454;
const HOST = '0.0.0.0'; // CRÍTICO para Docker

// Configuración de dispositivos
let devicesConfig = { "device002": "192.168.0.20" };

var NetServer = IntegrationPos.initialize({
    port: TCP_PORT,
    host: HOST,
    server: net.createServer(),
    devicesConfig: devicesConfig
});

// Monitorear conexiones TCP
NetServer.server.on('connection', (socket) => {
    console.log(`[TCP] ✓ Conexión desde ${socket.remoteAddress}:${socket.remotePort}`);

    socket.on('close', () => {
        console.log(`[TCP] ✗ Cliente desconectado`);
    });

    socket.on('error', (err) => {
        console.error(`[TCP] Error:`, err.message);
    });
});

NetServer.server.on('error', (err) => {
    console.error(`[TCP] Error del servidor:`, err);
    process.exit(1);
});

NetServer.start();
console.log(`[TCP] ✓ Servidor iniciado en ${HOST}:${TCP_PORT}`);

// Servidor web con Express
const app = express();
app.use(express.json());

// Middleware de logging
app.use((req, res, next) => {
    console.log(`[${new Date().toISOString()}] ${req.method} ${req.url} - IP: ${req.ip}`);
    next();
});

// Función genérica para manejar respuestas del POS
function handlePOSRequest(handler, params, res) {
    console.log(`[HANDLER] ${handler}`, params);

    try {
        NetServer[handler]({
            ...params,
            logger: true,
            response: (response) => {
                console.log('[POS RESPONSE]', response);
                res.json(response);
            },
        });
    } catch (error) {
        console.error('[ERROR]', error);
        res.status(500).json({
            error: 'Error esperando la respuesta del dispositivo.',
            details: error.message
        });
    }
}

// Middleware para validar parámetros
function validateParams(req, res, next) {
    const { device, typePay, importe, reference } = req.params;

    if (device && !devicesConfig[device]) {
        console.error(`[VALIDATION] Dispositivo "${device}" no configurado`);
        return res.status(400).json({
            error: 'Dispositivo no configurado',
            dispositivo: device,
            disponibles: Object.keys(devicesConfig)
        });
    }

    if (typePay && !['chip', 'ctl', 'qr'].includes(typePay)) {
        return res.status(400).json({ error: 'Tipo de pago no válido' });
    }

    if (importe && isNaN(parseFloat(importe))) {
        return res.status(400).json({ error: 'Monto inválido' });
    }

    if (reference && isNaN(parseInt(reference))) {
        return res.status(400).json({ error: 'Referencia inválida' });
    }

    next();
}

// ========== RUTAS ==========
app.post('/anular/:device/:reference', validateParams, (req, res) => {
    const { device, reference } = req.params;
    handlePOSRequest('handleAnnulment', { device, reference: parseInt(reference) }, res);
});

app.get('/cerrar/:device', validateParams, (req, res) => {
    const { device } = req.params;
    handlePOSRequest('handleLotClosuret', { device }, res);
});

app.post('/pago/:device/:typePay/:importe', validateParams, (req, res) => {
    const { device, typePay, importe } = req.params;

    const handlers = {
        chip: "handleChip",
        ctl: "handleCtl",
        qr: "handleQR",
    };

    if (handlers[typePay]) {
        handlePOSRequest(handlers[typePay], {
            device,
            importe: parseFloat(importe)
        }, res);
    } else {
        res.status(400).json({ error: 'Tipo de pago no válido' });
    }
});

// ========== DEBUG ENDPOINTS ==========
app.get('/debug/transacciones', (req, res) => {
    try {
        const server = NetServer?.server;

        if (!server) {
            return res.status(503).json({
                status: 'error',
                tcp: 'not_initialized',
                message: 'NetServer no está inicializado'
            });
        }

        const isListening = server.listening === true;
        const address = server.address();

        if (isListening) {
            return res.status(200).json({
                status: 'ok',
                tcp: 'listening',
                port: address?.port || TCP_PORT,
                address: address?.address || HOST,
                message: `Servidor TCP activo en puerto ${address?.port || TCP_PORT}`
            });
        } else {
            return res.status(503).json({
                status: 'error',
                tcp: 'not_listening',
                message: 'El servidor TCP no está escuchando conexiones'
            });
        }
    } catch (error) {
        console.error('Error en /debug/transacciones:', error);
        return res.status(500).json({
            status: 'error',
            tcp: 'check_failed',
            message: error.message
        });
    }
});

app.get('/debug/conexiones', (req, res) => {
    try {
        const server = NetServer?.server;

        if (!server) {
            return res.status(503).json({
                status: 'error',
                message: 'Servidor TCP no inicializado'
            });
        }

        server.getConnections((err, count) => {
            if (err) {
                return res.status(500).json({ error: err.message });
            }

            const address = server.address();

            res.json({
                status: 'ok',
                container: true,
                tcp: {
                    escuchando: server.listening,
                    puerto: address?.port || TCP_PORT,
                    host: address?.address || HOST,
                    conexiones_activas: count || 0
                },
                http: {
                    escuchando: true,
                    puerto: HTTP_PORT,
                    host: HOST
                },
                dispositivos_configurados: devicesConfig,
                mensaje: count > 0
                    ? `✓ ${count} POS conectado(s)`
                    : '✗ Ningún POS conectado al puerto TCP'
            });
        });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

app.get('/health', (req, res) => {
    res.json({
        status: 'healthy',
        uptime: process.uptime(),
        timestamp: new Date().toISOString()
    });
});

app.get('/test', (req, res) => {
    res.json({
        mensaje: '✓ Servidor HTTP funcionando',
        timestamp: new Date().toISOString(),
        tu_ip: req.ip,
        puerto: HTTP_PORT,
        entorno: process.env.NODE_ENV || 'development'
    });
});

app.get('/', (req, res) => {
    res.json({
        servicio: 'POS Integration Server',
        version: '1.0.0',
        status: 'online',
        puertos: {
            http: HTTP_PORT,
            tcp: TCP_PORT
        },
        endpoints: {
            transacciones: [
                'POST /pago/:device/:typePay/:importe',
                'POST /anular/:device/:reference',
                'GET /cerrar/:device'
            ],
            debug: [
                'GET /debug/transacciones',
                'GET /debug/conexiones',
                'GET /health',
                'GET /test'
            ]
        },
        ejemplo: `curl -X POST http://YOUR_IP:${HTTP_PORT}/pago/device002/ctl/70.50`
    });
});

// ========== INICIAR SERVIDOR HTTP ==========
const server = app.listen(HTTP_PORT, HOST, () => {
    console.log(`[HTTP] ✓ Servidor iniciado en ${HOST}:${HTTP_PORT}`);
    console.log(`[INFO] Entorno: ${process.env.NODE_ENV || 'development'}`);
    console.log(`[INFO] Ready to accept connections`);
});

// ========== GRACEFUL SHUTDOWN ==========
const gracefulShutdown = (signal) => {
    console.log(`\n[SHUTDOWN] Señal ${signal} recibida`);

    server.close(() => {
        console.log('[HTTP] Servidor HTTP cerrado');

        NetServer.server.close(() => {
            console.log('[TCP] Servidor TCP cerrado');
            process.exit(0);
        });
    });

    // Force shutdown después de 10 segundos
    setTimeout(() => {
        console.error('[SHUTDOWN] Forzando cierre...');
        process.exit(1);
    }, 10000);
};

process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
process.on('SIGINT', () => gracefulShutdown('SIGINT'));

// ========== ERROR HANDLING ==========
process.on('uncaughtException', (err) => {
    console.error('[UNCAUGHT EXCEPTION]', err);
});

process.on('unhandledRejection', (err) => {
    console.error('[UNHANDLED REJECTION]', err);
});