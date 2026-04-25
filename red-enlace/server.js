"use strict";
const net = require('net');
const express = require('express');
const IntegrationPos = require('integration-pos-service');
const console = require('console');
// Configuración de dispositivos
let devicesConfig = {
    device002: { name: "POS Ventura 01" },
    device003: { name: "POS Las Brisas 01" }
};
var NetServer = IntegrationPos.initialize({
    port: 5454,
    host: '0.0.0.0',
    server: net.createServer(),
    devicesConfig: devicesConfig
});
NetServer.start();
console.log("Servidor TCP iniciado en el puerto 5454");
// Servidor web con Express
const app = express();
app.listen(8000, '0.0.0.0', () => console.log("Servidor web iniciado en el puerto 8000"));
// Función genérica para manejar respuestas del POS
function handlePOSRequest(handler, params, res) {
    try {
        NetServer[handler]({
            ...params,
            logger: true,
            response: (response) => {
                console.log(response);
                res.json(response);
            },
        });
    } catch (error) {
        console.error('Error esperando la respuesta:', error);
        res.status(500).send({
            error: 'Error esperando la respuesta del dispositivo.'
        });
    }
}
// Middleware para validar parámetros
function validateParams(req, res, next) {
    const { device, typePay, importe, reference } = req.params;
    if (device && !devicesConfig[device]) {
        return res.status(400).send({ error: 'Dispositivo no configurado' });
    }
    if (typePay && !['chip', 'ctl', 'qr'].includes(typePay)) {
        return res.status(400).send({ error: 'Tipo de pago no válido' });
    }
    if (importe && isNaN(parseFloat(importe))) {
        return res.status(400).send({ error: 'Monto inválido' });
    }
    if (reference && isNaN(parseInt(reference))) {
        return res.status(400).send({ error: 'Referencia inválida' });
    }
    next();
}
// Rutas
app.post('/anular/:device/:reference', validateParams, (req, res) => {
    const { device, reference } = req.params;
    handlePOSRequest('handleAnnulment', { device, reference: parseInt(reference) },
        res);
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
        handlePOSRequest(handlers[typePay], { device, importe }, res);
    } else {
        res.status(400).send({ error: 'Tipo de pago no válido' });
    }
});
// Ruta mejorada y más robusta
app.get('/debug/transacciones', (req, res) => {
    try {
        const server = NetServer?.server;
        console.log('Verificando estado del servidor TCP:')
        if (!server) {
            return res.status(503).json({
                status: 'error',
                tcp: 'not_initialized',
                message: 'NetServer no está inicializado'
            });
        }

        const isListening = server.listening === true;
        const address = server.address ? server.address() : null;

        if (isListening) {
            return res.status(200).json({
                status: 'ok',
                tcp: 'listening',
                port: address?.port || 5454,
                address: address?.address || '0.0.0.0',
                message: `Servidor TCP activo en puerto ${address?.port || 5454}`
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
            message: error.message || 'Error interno al verificar estado'
        });
    }
});