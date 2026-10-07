const path = require('path');
const fs = require('fs');
require('dotenv').config({ path: path.join(__dirname, '../.env') });
require('dotenv').config(); // also check current directory if any

const { createClient } = require('@supabase/supabase-js');

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_KEY;
const SUBSCRIBERS_FILE = path.join(__dirname, 'subscribers.json');

let supabase = null;
if (SUPABASE_URL && SUPABASE_KEY) {
    try {
        supabase = createClient(SUPABASE_URL, SUPABASE_KEY);
        console.log('[DB] Supabase client berhasil diinisialisasi.');
    } catch (err) {
        console.error('[DB] Gagal inisialisasi Supabase client:', err.message);
    }
} else {
    console.warn('[DB] SUPABASE_URL atau SUPABASE_KEY tidak ditemukan. Menggunakan mode fallback JSON.');
}

const DEFAULT_PREFERENCES = ['ihsg', 'gainers', 'losers', 'sektor', 'asing', 'makro', 'ipo', 'watchlist', 'berita'];

// Local JSON fallback helpers
function readLocalSubscribers() {
    try {
        if (!fs.existsSync(SUBSCRIBERS_FILE)) {
            fs.writeFileSync(SUBSCRIBERS_FILE, JSON.stringify([], null, 2));
            return [];
        }
        const data = fs.readFileSync(SUBSCRIBERS_FILE, 'utf8');
        const parsed = JSON.parse(data);
        
        // Migrate old format ['jid1', 'jid2'] to [{jid: 'jid1', preferences: [...], card_style: '1'}]
        if (Array.isArray(parsed) && parsed.length > 0 && typeof parsed[0] === 'string') {
            const migrated = parsed.map(jid => ({ jid, preferences: DEFAULT_PREFERENCES, card_style: '1' }));
            saveLocalSubscribers(migrated);
            return migrated;
        }
        return Array.isArray(parsed) ? parsed : [];
    } catch (err) {
        console.error('[DB] Error membaca subscribers.json lokal:', err.message);
        return [];
    }
}

function saveLocalSubscribers(list) {
    try {
        // Remove duplicates by jid
        const uniqueMap = new Map();
        list.filter(Boolean).forEach(item => {
            if (typeof item === 'string') {
                uniqueMap.set(item, { jid: item, preferences: DEFAULT_PREFERENCES, card_style: '1' });
            } else if (item && item.jid) {
                if (!item.card_style) item.card_style = '1';
                uniqueMap.set(item.jid, item);
            }
        });
        const unique = Array.from(uniqueMap.values());
        fs.writeFileSync(SUBSCRIBERS_FILE, JSON.stringify(unique, null, 2));
        return true;
    } catch (err) {
        console.error('[DB] Error menulis subscribers.json lokal:', err.message);
        return false;
    }
}

function extractPhoneFromJid(jid) {
    if (!jid) return 'unknown';
    const digits = jid.split('@')[0].replace(/[^0-9]/g, '');
    return digits || 'unknown';
}

/**
 * Mendapatkan seluruh subscriber yang aktif beserta preferensinya
 * @returns {Promise<Array>} List of subscriber objects {jid, phone, is_active, preferences}
 */
async function getActiveSubscribers() {
    if (supabase) {
        try {
            const { data, error } = await supabase
                .from('subscribers')
                .select('jid, phone, is_active, preferences')
                .eq('is_active', true);

            if (error) {
                console.error('[DB] Supabase error getActiveSubscribers:', error.message);
                return readLocalSubscribers();
            }

            const subs = data || [];
            // Sinkronkan ke backup lokal
            saveLocalSubscribers(subs);
            return subs;
        } catch (err) {
            console.error('[DB] Exception getActiveSubscribers:', err.message);
            return readLocalSubscribers();
        }
    }
    return readLocalSubscribers();
}

/**
 * Mengecek apakah JID tertentu sedang aktif berlangganan
 */
async function isSubscribed(jid) {
    if (!jid) return false;
    if (supabase) {
        try {
            const { data, error } = await supabase
                .from('subscribers')
                .select('is_active')
                .eq('jid', jid)
                .maybeSingle();

            if (error) {
                console.error('[DB] Supabase error isSubscribed:', error.message);
                const local = readLocalSubscribers().find(s => s.jid === jid);
                return Boolean(local);
            }

            return Boolean(data && data.is_active);
        } catch (err) {
            console.error('[DB] Exception isSubscribed:', err.message);
            const local = readLocalSubscribers().find(s => s.jid === jid);
            return Boolean(local);
        }
    }
    const local = readLocalSubscribers().find(s => s.jid === jid);
    return Boolean(local);
}

/**
 * Mendaftarkan subscriber baru atau mengaktifkan kembali
 */
async function addSubscriber(jid, phone = null) {
    if (!jid) return false;
    const finalPhone = phone || extractPhoneFromJid(jid);
    const defaultPrefs = ['ihsg', 'gainers', 'losers', 'berita'];

    // Update backup lokal
    const local = readLocalSubscribers();
    const existingIndex = local.findIndex(s => s.jid === jid);
    if (existingIndex === -1) {
        local.push({ jid, preferences: defaultPrefs });
    }
    saveLocalSubscribers(local);

    if (supabase) {
        try {
            const payload = {
                jid: jid,
                phone: finalPhone || 'unknown',
                is_active: true,
                preferences: defaultPrefs,
                updated_at: new Date().toISOString()
            };

            const { error } = await supabase
                .from('subscribers')
                .upsert(payload, { onConflict: 'jid' });

            if (error) {
                console.error('[DB] Supabase error addSubscriber:', error.message);
                return false;
            }
            return true;
        } catch (err) {
            console.error('[DB] Exception addSubscriber:', err.message);
            return false;
        }
    }
    return true;
}

/**
 * Menghentikan langganan (is_active = false)
 * @param {string} jid 
 * @returns {Promise<boolean>}
 */
async function removeSubscriber(jid) {
    if (!jid) return false;

    // Update backup lokal
    const local = readLocalSubscribers();
    const updated = local.filter(s => s.jid !== jid);
    saveLocalSubscribers(updated);

    if (supabase) {
        try {
            const { error } = await supabase
                .from('subscribers')
                .update({
                    is_active: false,
                    updated_at: new Date().toISOString()
                })
                .eq('jid', jid);

            if (error) {
                console.error('[DB] Supabase error removeSubscriber:', error.message);
                return false;
            }
            return true;
        } catch (err) {
            console.error('[DB] Exception removeSubscriber:', err.message);
            return false;
        }
    }
    return true;
}

/**
 * Mengupdate preferensi topik user
 * @param {string} jid 
 * @param {string[]} preferences Array topik, misal ['ihsg', 'gainers']
 * @returns {Promise<boolean>}
 */
async function updatePreferences(jid, preferences) {
    if (!jid) return false;

    // Update backup lokal
    const local = readLocalSubscribers();
    const existingIndex = local.findIndex(s => s.jid === jid);
    if (existingIndex !== -1) {
        local[existingIndex].preferences = preferences;
    } else {
        local.push({ jid, preferences });
    }
    saveLocalSubscribers(local);

    if (supabase) {
        try {
            const { error } = await supabase
                .from('subscribers')
                .update({
                    preferences: preferences,
                    updated_at: new Date().toISOString()
                })
                .eq('jid', jid);

            if (error) {
                console.error('[DB] Supabase error updatePreferences:', error.message);
                return false;
            }
            return true;
        } catch (err) {
            console.error('[DB] Exception updatePreferences:', err.message);
            return false;
        }
    }
    return true;
}

/**
 * Mengupdate preferensi gaya kartu visual (1, 2, atau 3)
 */
async function updateCardStyle(jid, cardStyle) {
    if (!jid) return false;
    const style = String(cardStyle).trim();

    // Update backup lokal
    const local = readLocalSubscribers();
    const existingIndex = local.findIndex(s => s.jid === jid);
    if (existingIndex !== -1) {
        local[existingIndex].card_style = style;
    } else {
        local.push({ jid, preferences: DEFAULT_PREFERENCES, card_style: style });
    }
    saveLocalSubscribers(local);

    if (supabase) {
        try {
            await supabase
                .from('subscribers')
                .update({ card_style: style, updated_at: new Date().toISOString() })
                .eq('jid', jid);
        } catch (_) {}
    }
    return true;
}

/**
 * Mengambil subscriber berdasarkan JID
 */
async function getSubscriber(jid) {
    if (!jid) return null;
    const local = readLocalSubscribers();
    return local.find(s => s.jid === jid) || null;
}

module.exports = {
    supabase,
    DEFAULT_PREFERENCES,
    getActiveSubscribers,
    getSubscriber,
    isSubscribed,
    addSubscriber,
    removeSubscriber,
    updatePreferences,
    updateCardStyle,
    readLocalSubscribers,
    saveLocalSubscribers,
    extractPhoneFromJid
};
