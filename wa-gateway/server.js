// Intercept noisy internal libsignal session dumps before anything else
const originalConsoleInfo = console.info;
console.info = function (...args) {
    if (typeof args[0] === 'string' && (
        args[0].startsWith('Closing session:') ||
        args[0].startsWith('Removing old closed session:') ||
        args[0].startsWith('Decrypted message with closed session')
    )) {
        return;
    }
    originalConsoleInfo.apply(console, args);
};

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
const {
    getActiveSubscribers,
    getSubscriber,
    isSubscribed,
    addSubscriber,
    removeSubscriber,
    updatePreferences,
    updateCardStyle,
    DEFAULT_PREFERENCES
} = require('./db');
const { exec } = require('child_process');

const app = express();
const PORT = process.env.PORT || 3000;
const AUTH_DIR = path.join(__dirname, 'auth_session');

app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true, limit: '50mb' }));

let sock = null;
let connectionStatus = 'initializing'; // 'initializing', 'qr_ready', 'connected', 'disconnected'

/**
 * Normalizes any WhatsApp identifier into a valid Baileys JID format.
 * Supports:
 * - Group JID (@g.us)
 * - User phone number JID (@s.whatsapp.net)
 * - WhatsApp Linked Identity JID (@lid)
 * - Raw phone numbers (e.g. 0812..., 62812..., +62812...)
 */
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

    // User LID: WhatsApp Linked Identity (e.g. 154459992793290@lid)
    if (clean.endsWith('@lid')) {
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

/**
 * Parses and deduplicates target inputs (string, list, comma-separated, phone numbers, or JIDs).
 * Guarantees no duplicated targets in the returned array.
 */
function parseTargets(input) {
    if (!input) return [];
    if (Array.isArray(input)) {
        const flattened = [];
        for (const item of input) {
            const parsed = parseTargets(item);
            for (const p of parsed) {
                if (!flattened.includes(p)) {
                    flattened.push(p);
                }
            }
        }
        return Array.from(new Set(flattened));
    }

    const str = input.toString().trim();
    const results = [];

    // 1. Extract JIDs (e.g. ...@g.us, ...@s.whatsapp.net, ...@lid)
    const jidMatches = str.match(/[\w\-]+@(g\.us|s\.whatsapp\.net|lid)/g) || [];
    for (const jid of jidMatches) {
        const formatted = formatJid(jid);
        if (formatted && !results.includes(formatted)) {
            results.push(formatted);
        }
    }

    // 2. Remove extracted JIDs from the string so we can safely extract phone numbers
    let remaining = str;
    for (const jid of jidMatches) {
        remaining = remaining.replace(jid, ' ');
    }

    // 3. Extract phone numbers (handles 08..., 628..., +628...)
    const phoneMatches = remaining.match(/(?:\+?62|0)[0-9]{8,14}/g) || [];
    for (const phone of phoneMatches) {
        const formatted = formatJid(phone);
        if (formatted && !results.includes(formatted)) {
            results.push(formatted);
        }
    }

    // 4. Fallback: split by delimiters
    if (results.length === 0) {
        const items = str.split(/[,;\s\n]+/).map(t => t.trim()).filter(Boolean);
        for (const it of items) {
            const f = formatJid(it);
            if (f && !results.includes(f)) {
                results.push(f);
            }
        }
    }

    return Array.from(new Set(results));
}

async function connectToWhatsApp() {
    if (sock) {
        try {
            sock.ev.removeAllListeners();
        } catch (_) {}
    }

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

function extractMessageText(msg) {
    if (!msg || !msg.message) return '';
    let m = msg.message;
    // Unwrap nested message wrappers (ephemeral, viewOnce, etc.)
    while (m && (m.ephemeralMessage?.message || m.viewOnceMessage?.message || m.viewOnceMessageV2?.message || m.documentWithCaptionMessage?.message)) {
        m = m.ephemeralMessage?.message || m.viewOnceMessage?.message || m.viewOnceMessageV2?.message || m.documentWithCaptionMessage?.message;
    }
    if (!m) return '';
    return (
        m.conversation ||
        m.extendedTextMessage?.text ||
        m.imageMessage?.caption ||
        m.videoMessage?.caption ||
        ''
    ).trim();
}

    // Listen for incoming messages for subscriber registration (!daftar, !batal, !info, !topik / !topic)
    sock.ev.on('messages.upsert', async ({ messages, type }) => {
        if (type !== 'notify' && type !== 'append') return;
        for (const msg of messages) {
            if (!msg.message) continue;
            const senderJid = msg.key.remoteJid;
            if (!senderJid || senderJid.endsWith('@broadcast') || senderJid.endsWith('@newsletter')) continue;

            const text = extractMessageText(msg).toLowerCase();
            if (!text) continue;

            // If message is fromMe, only process if it starts with ! or / (enables self-chat testing)
            if (msg.key.fromMe && !text.startsWith('!') && !text.startsWith('/')) continue;

            console.log(`[WA-GATEWAY] 📩 Pesan masuk [${senderJid}] (fromMe: ${Boolean(msg.key.fromMe)}): "${text}"`);

            const formattedSender = formatJid(senderJid);
            if (!formattedSender) continue;

            // Detect phone number if available from sender, remoteJidAlt, or participant
            let detectedPhone = null;
            if (senderJid && senderJid.endsWith('@s.whatsapp.net')) {
                detectedPhone = senderJid.split('@')[0].replace(/[^0-9]/g, '');
            } else if (msg.key.remoteJidAlt && msg.key.remoteJidAlt.endsWith('@s.whatsapp.net')) {
                detectedPhone = msg.key.remoteJidAlt.split('@')[0].replace(/[^0-9]/g, '');
            } else if (msg.key.participant && msg.key.participant.endsWith('@s.whatsapp.net')) {
                detectedPhone = msg.key.participant.split('@')[0].replace(/[^0-9]/g, '');
            }

            const registered = await isSubscribed(formattedSender);

            try {
                if (['!daftar', 'daftar', '/daftar', '/start', '!regist', 'regist', '!subscribe', 'subscribe'].includes(text)) {
                    if (!registered) {
                        await addSubscriber(formattedSender, detectedPhone);
                        console.log(`[WA-GATEWAY] ➕ Subscriber baru terdaftar: ${formattedSender}`);
                    }
                    console.log(`[WA-GATEWAY] 📤 Mengirim konfirmasi pendaftaran ke ${senderJid}...`);
                    await sock.sendMessage(senderJid, {
                        text: `📈 *Selamat datang di Briefin!*\n\nNomor kamu berhasil terdaftar. Kamu akan otomatis menerima analisis harian pasar saham IDX (IHSG, top movers, market cap) & kartu infografis setiap pagi hari bursa (Senin–Jumat pukul 06:30 WIB).\n\n• Ketik *!topik* untuk atur preferensi topik\n• Ketik *!info* untuk cek status langganan\n• Ketik *!batal* untuk berhenti berlangganan`
                    });
                    console.log(`[WA-GATEWAY] ✅ Balasan !daftar terkirim ke ${senderJid}`);
                } else if (['!batal', 'batal', '/stop', '!stop', '!unsub', 'unsub', '!unsubscribe'].includes(text)) {
                    if (registered) {
                        await removeSubscriber(formattedSender);
                        console.log(`[WA-GATEWAY] ➖ Subscriber berhenti: ${formattedSender}`);
                    }
                    console.log(`[WA-GATEWAY] 📤 Mengirim konfirmasi berhenti ke ${senderJid}...`);
                    await sock.sendMessage(senderJid, {
                        text: `👋 *Berhenti Berlangganan*\n\nKamu telah berhenti berlangganan Briefin. Kamu tidak akan menerima brief harian lagi.\n\nKetik *!daftar* kapan saja jika ingin bergabung kembali!`
                    });
                    console.log(`[WA-GATEWAY] ✅ Balasan !batal terkirim ke ${senderJid}`);
                } else if (['!info', 'info', '!help', 'help', 'menu', '!menu'].includes(text)) {
                    const statusText = registered ? '✅ Terdaftar (Aktif)' : '❌ Belum Terdaftar';
                    const subData = await getSubscriber(formattedSender);
                    const curPrefs = subData?.preferences?.length ? subData.preferences.join(', ') : 'Semua (Default)';
                    const curCard = subData?.card_style || '1';

                    console.log(`[WA-GATEWAY] 📤 Mengirim info ke ${senderJid}...`);
                    await sock.sendMessage(senderJid, {
                        text: `📊 *Briefin • Market Assistant*\n\nStatus: *${statusText}*\nTopik Aktif: *${curPrefs}*\nGaya Kartu: *Versi ${curCard}*\n\n*Perintah yang tersedia:*\n• *!briefin* - ⚡ Kirim market brief hari ini sekarang juga\n• *!topik* - Atur preferensi 9 topik pasar\n• *!kartu* - Pilih desain visual infografis (1, 2, atau 3)\n• *!daftar* - Berlangganan otomatis pagi hari (06:30 WIB)\n• *!info* - Cek status akun kamu\n• *!batal* - Berhenti berlangganan`
                    });
                    console.log(`[WA-GATEWAY] ✅ Balasan !info terkirim ke ${senderJid}`);
                } else if (['!briefin', '/briefin', 'briefin'].includes(text)) {
                    if (!registered) {
                        await addSubscriber(formattedSender, detectedPhone);
                        console.log(`[WA-GATEWAY] ➕ Auto-register subscriber baru via !briefin: ${formattedSender}`);
                    }
                    console.log(`[WA-GATEWAY] 🚀 Trigger manual !briefin diminta oleh ${senderJid}`);
                    await sock.sendMessage(senderJid, {
                        text: `⏳ *Sedang menyiapkan Briefin harian untukmu...*\n_Mohon tunggu sebentar, data sedang diracik..._`
                    });

                    const subData = await getSubscriber(formattedSender);
                    const cardStyle = subData?.card_style || '1';
                    const mainPyPath = path.resolve(__dirname, '../src/main.py');
                    const projectRoot = path.resolve(__dirname, '..');

                    const pyCmd = `python "${mainPyPath}" --target "${formattedSender}" --card "${cardStyle}"`;
                    console.log(`[WA-GATEWAY] Menjalankan: ${pyCmd}`);

                    exec(pyCmd, { cwd: projectRoot }, (err, stdout, stderr) => {
                        if (err) {
                            console.error(`[WA-GATEWAY] ❌ Gagal trigger briefin untuk ${formattedSender}:`, stderr || err.message);
                            sock.sendMessage(senderJid, { text: `⚠️ Gagal menghasilkan brief. Silakan coba lagi beberapa saat lagi.` }).catch(() => {});
                        } else {
                            console.log(`[WA-GATEWAY] ✅ Briefin sukses dikirim ke ${formattedSender}`);
                        }
                    });
                } else if (['!kartu', '/kartu', '!card', '/card', 'kartu', 'card'].includes(text)) {
                    console.log(`[WA-GATEWAY] 📤 Mengirim menu kartu ke ${senderJid}...`);
                    await sock.sendMessage(senderJid, {
                        text: `🖼️ *Pilihan Desain Infografis Briefin:*\n\n` +
                              `*1. Versi 1 (Standard)*: IHSG Composite Pulse + Top 5 Gainers & Losers (Angka IHSG Putih Bersih)\n` +
                              `*2. Versi 2 (Sector & Macro)*: IDX Sector Heatmap + Global Macro (Minyak, Emas, CPO) & Technical Watchlist\n` +
                              `*3. Versi 3 (Executive All-in-One)*: Dashboard Lengkap (IHSG, Gainers/Losers, Sektor, & Watchlist)\n\n` +
                              `Ketik *!kartu 1*, *!kartu 2*, atau *!kartu 3* untuk memilih gaya favoritmu!`
                    });
                    console.log(`[WA-GATEWAY] ✅ Balasan menu kartu terkirim ke ${senderJid}`);
                } else if (
                    text.startsWith('!kartu ') || text.startsWith('/kartu ') ||
                    text.startsWith('!card ') || text.startsWith('/card ') ||
                    text.startsWith('kartu ') || text.startsWith('card ')
                ) {
                    const arg = text.replace(/^(!|\/)?(kartu|card)\s+/, '').trim();
                    if (!['1', '2', '3'].includes(arg)) {
                        await sock.sendMessage(senderJid, { text: `❌ Pilihan kartu tidak valid. Pilih angka 1, 2, atau 3. Contoh: *!kartu 3*` });
                    } else {
                        await updateCardStyle(formattedSender, arg);
                        const names = { '1': 'Versi 1 (Standard Movers)', '2': 'Versi 2 (Sector & Macro Radar)', '3': 'Versi 3 (Executive All-in-One)' };
                        console.log(`[WA-GATEWAY] 📤 Update gaya kartu [${arg}] untuk ${senderJid}`);
                        await sock.sendMessage(senderJid, {
                            text: `✅ Gaya kartu berhasil diubah ke: *${names[arg]}*!\nKetik *!briefin* untuk melihat hasilnya sekarang.`
                        });
                    }
                } else if (['!topik', '/topik', '!topic', '/topic', 'topik', 'topic'].includes(text)) {
                    console.log(`[WA-GATEWAY] 📤 Mengirim menu topik ke ${senderJid}...`);
                    await sock.sendMessage(senderJid, {
                        text: `📝 *Pengaturan 9 Topik Briefin:*\n\n` +
                              `Balas angka topik yang ingin kamu terima (bisa lebih dari satu, pisahkan dengan koma):\n` +
                              `1. *IHSG* (Pergerakan & Sentimen Indeks)\n` +
                              `2. *Top Gainers* (Saham Pendorong Pasar)\n` +
                              `3. *Top Losers* (Saham Terkoreksi)\n` +
                              `4. *Performa Sektor* (Sektor Penggerak Reli IDX)\n` +
                              `5. *Arus Dana Asing* (Net Foreign Flow)\n` +
                              `6. *Komoditas & Makro* (Minyak, Emas, CPO, USD/IDR)\n` +
                              `7. *IPO & Aksi Korporasi* (RUPS, Dividen, e-IPO)\n` +
                              `8. *Watchlist Saham* (2-3 Rekomendasi Teknikal)\n` +
                              `9. *Tips & Strategi* (Money Management)\n\n` +
                              `Contoh ketik: *!topik 1,4,8* untuk memilih IHSG, Sektor, dan Watchlist.\n` +
                              `Ketik *!topik all* untuk memilih semua topik.`
                    });
                    console.log(`[WA-GATEWAY] ✅ Balasan menu topik terkirim ke ${senderJid}`);
                } else if (
                    text.startsWith('!topik ') || text.startsWith('/topik ') ||
                    text.startsWith('!topic ') || text.startsWith('/topic ') ||
                    text.startsWith('topik ') || text.startsWith('topic ')
                ) {
                    const arg = text.replace(/^(!|\/)?(topik|topic)\s+/, '').trim();
                    if (!registered) {
                        await addSubscriber(formattedSender, detectedPhone);
                        console.log(`[WA-GATEWAY] ➕ Auto-register subscriber baru via set topik: ${formattedSender}`);
                    }

                    if (arg === 'all' || arg === 'semua') {
                        await updatePreferences(formattedSender, DEFAULT_PREFERENCES);
                        console.log(`[WA-GATEWAY] 📤 Mengirim konfirmasi topik 'all' ke ${senderJid}...`);
                        await sock.sendMessage(senderJid, { text: `✅ Preferensi disimpan! Kamu akan menerima seluruh 9 topik pasar.\nKetik *!briefin* untuk melihat hasilnya sekarang.` });
                    } else {
                        const map = {
                            '1': 'ihsg',
                            '2': 'gainers',
                            '3': 'losers',
                            '4': 'sektor',
                            '5': 'asing',
                            '6': 'makro',
                            '7': 'ipo',
                            '8': 'watchlist',
                            '9': 'berita'
                        };
                        const choices = arg.split(/[,;\s]+/).map(x => x.trim()).filter(x => map[x]);
                        if (choices.length === 0) {
                            await sock.sendMessage(senderJid, { text: `❌ Format salah. Contoh: *!topik 1,4,8* atau *!topik all*` });
                        } else {
                            const newPrefs = Array.from(new Set(choices.map(c => map[c])));
                            await updatePreferences(formattedSender, newPrefs);
                            console.log(`[WA-GATEWAY] 📤 Mengirim konfirmasi topik [${newPrefs.join(', ')}] ke ${senderJid}...`);
                            await sock.sendMessage(senderJid, {
                                text: `✅ Preferensi topik berhasil disimpan: *${newPrefs.join(', ')}*!\nKetik *!briefin* untuk melihat hasilnya sekarang.`
                            });
                        }
                    }
                    console.log(`[WA-GATEWAY] ✅ Balasan set topik terkirim ke ${senderJid}`);
                }
            } catch (replyErr) {
                console.error(`[WA-GATEWAY] ❌ Gagal membalas pesan ke ${senderJid}:`, replyErr);
            }
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

// Get all registered subscribers from Supabase (with local json fallback)
app.get('/subscribers', async (req, res) => {
    const subscribers = await getActiveSubscribers();
    res.json({
        status: true,
        count: subscribers.length,
        subscribers
    });
});

// Manage subscribers (add or remove manually via API)
app.post('/subscribers', async (req, res) => {
    const { action, target } = req.body;
    if (!target) {
        return res.status(400).json({ status: false, error: 'Parameter "target" diperlukan.' });
    }
    const jids = parseTargets(target);
    if (jids.length === 0) {
        return res.status(400).json({ status: false, error: 'Format target tidak valid.' });
    }

    if (action === 'remove') {
        for (const jid of jids) {
            await removeSubscriber(jid);
        }
    } else {
        for (const jid of jids) {
            await addSubscriber(jid);
        }
    }

    const subscribers = await getActiveSubscribers();
    res.json({
        status: true,
        action: action === 'remove' ? 'removed' : 'added',
        count: subscribers.length,
        subscribers
    });
});

// Send message endpoint (supports group JID, LID, and phone numbers with deduplication)
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
    console.log(`[WA-GATEWAY] Memproses pengiriman ke ${jids.length} target unik:\n  - ${jids.join('\n  - ')}`);

    for (const jid of jids) {
        let destJid = jid;

        // If personal phone number, verify with WhatsApp server.
        // NOTE: JIDs ending in @lid or @g.us must NOT be checked with sock.onWhatsApp()
        // because onWhatsApp only checks regular MSISDN phone numbers.
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
