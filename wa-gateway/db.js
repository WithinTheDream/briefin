const path = require('path');
const fs = require('fs');
require('dotenv').config({ path: path.join(__dirname, '../.env') });
require('dotenv').config(); // also check current dir if any

const { createClient } = require('@supabase/supabase-js');

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_KEY;
const SUBSCRIBERS_FILE = path.join(__dirname, 'subscribers.json');

let supabase = null;
if (SUPABASE_URL && SUPABASE_KEY) {
    try {
        supabase = createClient(SUPABASE_URL, SUPABASE_KEY);
        console.log('[DB] Supabase client initialized.');
    } catch (err) {
        console.error('[DB] Gagal inisialisasi Supabase client:', err.message);
    }
} else {
    console.warn('[DB] SUPABASE_URL atau SUPABASE_KEY tidak ditemukan. Menggunakan mode fallback JSON.');
}

// Local JSON fallback helpers
function readLocalSubscribers() {
    try {
        if (!fs.existsSync(SUBSCRIBERS_FILE)) {
            fs.writeFileSync(SUBSCRIBERS_FILE, JSON.stringify([], null, 2));
            return [];
        }
        const data = fs.readFileSync(SUBSCRIBERS_FILE, 'utf8');
        const parsed = JSON.parse(data);
        return Array.isArray(parsed) ? parsed : [];
    } catch (err) {
        console.error('[DB] Error membaca subscribers.json lokal:', err.message);
        return [];
    }
}

function saveLocalSubscribers(list) {
    try {
        const unique = Array.from(new Set(list.filter(Boolean)));
        fs.writeFileSync(SUBSCRIBERS_FILE, JSON.stringify(unique, null, 2));
        return true;
    } catch (err) {
        console.error('[DB] Error menulis subscribers.json lokal:', err.message);
        return false;
    }
}

function extractPhoneFromJid(jid) {
    if (!jid) return '';
    const clean = jid.split('@')[0].replace(/[^0-9]/g, '');
    return clean;
}

/**
 * Mendapatkan seluruh JID subscriber yang aktif (is_active = true)
 * @returns {Promise<string[]>} List of JIDs
 */
async function getActiveSubscribers() {
    if (supabase) {
        try {
            const { data, error } = await supabase
                .from('subscribers')
                .select('jid, phone, is_active')
                .eq('is_active', true);

            if (error) {
                console.error('[DB] Supabase error getActiveSubscribers:', error.message);
                return readLocalSubscribers();
            }

            const jids = (data || []).map(row => row.jid).filter(Boolean);
            // Sinkronkan ke backup lokal
            saveLocalSubscribers(jids);
            return jids;
        } catch (err) {
            console.error('[DB] Exception getActiveSubscribers:', err.message);
            return readLocalSubscribers();
        }
    }
    return readLocalSubscribers();
}

/**
 * Mengecek apakah JID tertentu sedang aktif berlangganan
 * @param {string} jid 
 * @returns {Promise<boolean>}
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
                return readLocalSubscribers().includes(jid);
            }

            return Boolean(data && data.is_active);
        } catch (err) {
            console.error('[DB] Exception isSubscribed:', err.message);
            return readLocalSubscribers().includes(jid);
        }
    }
    return readLocalSubscribers().includes(jid);
}

/**
 * Mendaftarkan subscriber baru atau mengaktifkan kembali yang sudah non-aktif
 * @param {string} jid 
 * @param {string} phone
 * @returns {Promise<boolean>}
 */
async function addSubscriber(jid, phone = null) {
    if (!jid) return false;
    const finalPhone = phone || extractPhoneFromJid(jid);

    // Update backup lokal
    const local = readLocalSubscribers();
    if (!local.includes(jid)) {
        local.push(jid);
        saveLocalSubscribers(local);
    }

    if (supabase) {
        try {
            const { error } = await supabase
                .from('subscribers')
                .upsert(
                    {
                        jid: jid,
                        phone: finalPhone,
                        is_active: true,
                        updated_at: new Date().toISOString()
                    },
                    { onConflict: 'jid' }
                );

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
    const updated = local.filter(s => s !== jid);
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

module.exports = {
    supabase,
    getActiveSubscribers,
    isSubscribed,
    addSubscriber,
    removeSubscriber,
    readLocalSubscribers,
    saveLocalSubscribers
};
