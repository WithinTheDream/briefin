const { supabase, addSubscriber, getActiveSubscribers } = require('./db');
const fs = require('fs');
const path = require('path');

async function runMigration() {
    console.log('🚀 Memulai migrasi subscribers ke Supabase...');

    if (!supabase) {
        console.error('❌ Gagal: Supabase client belum terkonfigurasi. Periksa file .env.');
        process.exit(1);
    }

    // 1. Tes koneksi ke tabel
    try {
        const { data, error } = await supabase.from('subscribers').select('count', { count: 'exact', head: true });
        if (error) {
            console.error('❌ Gagal mengakses tabel subscribers di Supabase:');
            console.error('Pesan error:', error.message);
            console.error('\n⚠️ Pastikan Anda sudah membuat tabel subscribers di SQL Editor Supabase!');
            process.exit(1);
        }
        console.log('✅ Berhasil terhubung ke tabel `subscribers` di Supabase.');
    } catch (e) {
        console.error('❌ Exception saat test query ke Supabase:', e.message);
        process.exit(1);
    }

    // 2. Baca file subscribers.json lokal
    const jsonPath = path.join(__dirname, 'subscribers.json');
    let localSubscribers = [];
    if (fs.existsSync(jsonPath)) {
        try {
            localSubscribers = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));
        } catch (err) {
            console.warn('⚠️ Gagal membaca subscribers.json:', err.message);
        }
    }

    console.log(`📋 Ditemukan ${localSubscribers.length} nomor di subscribers.json lokal.`);

    // 3. Migrasi ke Supabase
    let successCount = 0;
    for (const jid of localSubscribers) {
        if (!jid) continue;
        console.log(`   -> Memigrasikan: ${jid}`);
        const ok = await addSubscriber(jid);
        if (ok) successCount++;
    }

    console.log(`\n🎉 Migrasi selesai! Berhasil menyimpan ${successCount}/${localSubscribers.length} subscriber ke Supabase.`);

    // 4. Verifikasi data di Supabase
    const active = await getActiveSubscribers();
    console.log(`📊 Total subscriber aktif di Supabase saat ini: ${active.length}`);
    console.log('Daftar JID:', active);
}

runMigration().catch(err => {
    console.error('Unhandled error:', err);
    process.exit(1);
});
