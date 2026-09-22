const express = require('express');
const { 
    default: makeWASocket, 
    DisconnectReason, 
    useMultiFileAuthState, 
    fetchLatestBaileysVersion 
} = require('@whiskeysockets/baileys');
const qrcode = require('qrcode-terminal');
const pino = require('pino');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;
const AUTH_DIR = path.join(__dirname, 'auth_session');

app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true, limit: '50mb' }));

let sock = null;
let connectionStatus = 'initializing'; // 'initializing', 'qr_ready', 'connected', 'disconnected'

function formatJid(target) {
    if (!target) return null;
    let clean = target.toString().trim();
    
    // Group JID: e.g. 120363028192839123@g.us or 628815877681-1590807322@g.us
    if (clean.endsWith('@g.us')) {
        return clean.replace(/\s+/g, '');
    }
    
    // User JID: already has @s.whatsapp.net
    if (clean.endsWith('@s.whatsapp.net')) {
        return clean.replace(/\s+/g, '');
    }

    // Otherwise treat as phone number:
    clean = clean.replace(/[^0-9]/g, '');
    if (clean.startsWith('0')) {
        clean = '62' + clean.slice(1);
    } else if (clean.startsWith('8')) {
        clean = '62' + clean;
    }
    
    if (!clean || clean.length < 7) return null;
    return `${clean}@s.whatsapp.net`;
}

function parseTargets(input) {
    if (!input) return [];
    if (Array.isArray(input)) {
        return input.map(formatJid).filter(Boolean);
    }

    const str = input.toString().trim();
    const results = [];

    // 1. Extract JIDs (e.g. ...@g.us, ...@s.whatsapp.net)
    const jidMatches = str.match(/[\w\-]+@(g\.us|s\.whatsapp\.net)/g) || [];
    for (const jid of jidMatches) {
        if (!results.includes(jid)) {
            results.push(jid);
        }
    }

    // 2. Remove extracted JIDs from the string so we can safely extract phone numbers
    let remaining = str;
    for (const jid of jidMatches) {
        remaining = remaining.replace(jid, ' ');
    }

    // 3. Extract phone numbers (handles 08..., 628..., +628...) regardless of comma, dot, or space separators
    const phoneMatches = remaining.match(/(?:\+?62|0)[0-9]{8,14}/g) || [];
    for (const phone of phoneMatches) {
        const formatted = formatJid(phone);
        if (formatted && !results.includes(formatted)) {
            results.push(formatted);
        }
    }

    // 4. Fallback: if regex didn't catch, try splitting by comma, semicolon, space, newline
    if (results.length === 0) {
        const items = str.split(/[,;\s\n]+/).map(t => t.trim()).filter(Boolean);
        for (const it of items) {
            const f = formatJid(it);
            if (f && !results.includes(f)) {
                results.push(f);
            }
        }
    }

    return results;
}

async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
    const { version } = await fetchLatestBaileysVersion();

    sock = makeWASocket({
        version,
        logger: pino({ level: 'silent' }),
        printQRInTerminal: false,
        auth: state,
        defaultQueryTimeoutMs: 30000,
        browser: ['Briefin Market Bot', 'Desktop', '1.0.0']
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            connectionStatus = 'qr_ready';
            console.log('\n======================================================');
            console.log('📌 SCAN QR CODE INI MENGGUNAKAN WHATSAPP ANDA:');
            console.log('Buka WA di HP -> Titik Tiga / Pengaturan -> Perangkat Tertaut -> Tautkan Perangkat');
            console.log('======================================================\n');
            qrcode.generate(qr, { small: true });
        }

        if (connection === 'close') {
            const statusCode = lastDisconnect?.error?.output?.statusCode;
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
            connectionStatus = 'disconnected';
            console.log(`[WA-GATEWAY] Koneksi terputus (status code: ${statusCode}). Mencoba reconnect: ${shouldReconnect}`);

            if (shouldReconnect) {
                setTimeout(connectToWhatsApp, 3000);
            } else {
                console.log('[WA-GATEWAY] Sesi logout. Menghapus folder auth_session untuk pairing ulang...');
                fs.rmSync(AUTH_DIR, { recursive: true, force: true });
                setTimeout(connectToWhatsApp, 3000);
            }
        } else if (connection === 'open') {
            connectionStatus = 'connected';
            console.log('\n======================================================');
            console.log('✅ WHATSAPP BERHASIL TERHUBUNG!');
            console.log(`🚀 Gateway aktif di http://localhost:${PORT}`);
            console.log('======================================================\n');
        }
    });
}

// Friendly landing page for browser testing
app.get('/', (req, res) => {
    res.send(`
        <html>
        <head><title>Briefin WhatsApp Gateway</title></head>
        <body style="font-family: sans-serif; padding: 40px; text-align: center; background: #f4f6f8;">
            <div style="background: white; border-radius: 12px; padding: 30px; max-width: 500px; margin: auto; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                <h2 style="color: #128C7E;">Briefin WhatsApp Gateway</h2>
                <p>Status: <b style="color: ${connectionStatus === 'connected' ? 'green' : 'orange'}; font-size: 1.2em;">
                    ${connectionStatus.toUpperCase()}
                </b></p>
                <p style="color: #555;">Endpoint <code>/send</code> menerima request <b>HTTP POST</b> dari skrip Briefin.</p>
            </div>
        </body>
        </html>
    `);
});

// Browser test for /send
app.get('/send', (req, res) => {
    res.status(405).send(`
        <html>
        <body style="font-family: sans-serif; padding: 30px; text-align: center;">
            <h3>⚠️ Method Not Allowed (GET /send)</h3>
            <p>Endpoint <code>/send</code> memerlukan request <b>HTTP POST</b> dari skrip Python Briefin, bukan dibuka langsung di browser.</p>
            <p>Status Gateway: <b>${connectionStatus}</b></p>
            <p><a href="/">Kembali ke Home</a></p>
        </body>
        </html>
    `);
});

// Check status endpoint (JSON)
app.get('/status', (req, res) => {
    res.json({
        status: connectionStatus,
        connected: connectionStatus === 'connected'
    });
});

// Send message endpoint (supports group JID + individual numbers with commas, dots, spaces)
app.post('/send', async (req, res) => {
    const { target, message, image_path } = req.body;

    if (!target) {
        return res.status(400).json({ status: false, error: 'Parameter "target" diperlukan.' });
    }

    if (connectionStatus !== 'connected' || !sock) {
        return res.status(503).json({ 
            status: false, 
            error: `WhatsApp belum terhubung (Status saat ini: ${connectionStatus}). Silakan scan QR code terlebih dahulu.` 
        });
    }

    const jids = parseTargets(target);
    if (jids.length === 0) {
        return res.status(400).json({ status: false, error: 'Format target tidak valid.' });
    }

    let imageBuffer = null;
    if (image_path) {
        const resolvedPath = path.isAbsolute(image_path) ? image_path : path.resolve(process.cwd(), image_path);
        if (!fs.existsSync(resolvedPath)) {
            return res.status(400).json({ status: false, error: `File gambar tidak ditemukan pada path: ${image_path}` });
        }
        imageBuffer = fs.readFileSync(resolvedPath);
    }

    const results = [];
    console.log(`[WA-GATEWAY] Memproses pengiriman ke ${jids.length} target:\n  - ${jids.join('\n  - ')}`);

    for (const jid of jids) {
        let destJid = jid;

        // If personal number, verify with WhatsApp server
        if (destJid.endsWith('@s.whatsapp.net')) {
            try {
                const checkResults = await sock.onWhatsApp(destJid);
                if (checkResults && checkResults.length > 0 && checkResults[0].exists) {
                    destJid = checkResults[0].jid;
                } else {
                    console.warn(`[WA-GATEWAY] ⚠️ Nomor ${destJid} tidak terdaftar di WhatsApp! Melanjutkan ke target berikutnya...`);
                    results.push({ jid, success: false, error: 'Nomor tidak terdaftar di WhatsApp' });
                    continue;
                }
            } catch (checkErr) {
                // If onWhatsApp check times out or fails, attempt direct send anyway
                console.log(`[WA-GATEWAY] Info onWhatsApp check: ${checkErr.message}. Mengirim langsung...`);
            }
        }

        try {
            let sentInfo;
            if (imageBuffer) {
                console.log(`[WA-GATEWAY] Mengirim gambar (${(imageBuffer.length / 1024).toFixed(1)} KB) ke ${destJid}...`);
                sentInfo = await sock.sendMessage(destJid, {
                    image: imageBuffer,
                    caption: message || ''
                });
            } else {
                console.log(`[WA-GATEWAY] Mengirim teks ke ${destJid}...`);
                sentInfo = await sock.sendMessage(destJid, {
                    text: message || ''
                });
            }
            results.push({ jid: destJid, success: true, id: sentInfo?.key?.id });
            console.log(`[WA-GATEWAY] ✅ Sukses terkirim ke ${destJid}`);
        } catch (err) {
            console.error(`[WA-GATEWAY] ❌ Gagal terkirim ke ${destJid}:`, err.message);
            results.push({ jid: destJid, success: false, error: err.message });
        }

        // Small delay between multiple recipients to ensure smooth delivery
        if (jids.length > 1) {
            await new Promise(r => setTimeout(r, 1000));
        }
    }

    const anySuccess = results.some(r => r.success);
    return res.status(anySuccess ? 200 : 500).json({
        status: anySuccess,
        results
    });
});

// Start Server
app.listen(PORT, () => {
    console.log(`[WA-GATEWAY] Server berjalan di port ${PORT}. Memulai inisialisasi Baileys...`);
    connectToWhatsApp();
});
