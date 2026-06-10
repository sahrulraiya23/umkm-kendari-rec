"""
routes/n8n_api.py
API endpoint khusus untuk integrasi dengan n8n.

Endpoint ini memungkinkan:
1. n8n membaca data produk real-time dari database
2. n8n mengirim pertanyaan chatbot dan mendapat jawaban rule-based
3. n8n melakukan sync data ke Google Sheets otomatis
4. n8n mendapat notifikasi jika ada perubahan data
5. n8n memetakan session WAHA → profil UMKM → konteks chatbot

Alur WAHA → n8n → Flask → chatbot:
  Pesan WA masuk → WAHA kirim session_name → n8n panggil /n8n/umkm-info
  → dapat profil UMKM → n8n panggil /n8n/chat-umkm dengan konteks UMKM tsb
  → chatbot menjawab sesuai UMKM yang sedang aktif

Semua endpoint menggunakan API Key untuk keamanan dasar.
"""

import os
import sqlite3
from datetime import datetime
from functools import wraps
from flask import Blueprint, jsonify, request, current_app
from models.database import get_db

n8n_bp = Blueprint('n8n', __name__, url_prefix='/n8n')

# ============================================================
# CONFIG — Ganti dengan API key rahasia kamu
# Simpan di environment variable: N8N_API_KEY=xxx
# ============================================================
N8N_API_KEY = os.environ.get('N8N_API_KEY', 'umkm-kendari-secret-2024')
# ============================================================


def require_api_key(f):
    """Decorator: Validasi API Key dari header atau query param."""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Cek dari header Authorization: Bearer <key>
        auth_header = request.headers.get('Authorization', '')
        key_from_header = auth_header.replace('Bearer ', '').strip()
        
        # Cek dari query param: ?api_key=xxx
        key_from_query = request.args.get('api_key', '')
        print("AUTH HEADER:", request.headers.get('Authorization'))
        print("EXPECTED:", N8N_API_KEY)
        
        if key_from_header != N8N_API_KEY and key_from_query != N8N_API_KEY:
            return jsonify({
                'success': False,
                'error': 'Unauthorized. Sertakan API Key yang valid.'
            }), 401
        return f(*args, **kwargs)
    return decorated


# ============================================================
# ENDPOINT 1: Health Check
# GET /n8n/ping
# ============================================================
@n8n_bp.route('/ping', methods=['GET'])
def ping():
    """Cek apakah API aktif (tidak perlu API key)."""
    return jsonify({
        'success': True,
        'message': 'UMKM Kendari API aktif! 🟢',
        'timestamp': datetime.now().isoformat(),
        'endpoints': [
            'GET  /n8n/ping              — health check',
            'GET  /n8n/produk            — semua produk',
            'GET  /n8n/produk/cari       — cari produk (?q=keyword)',
            'GET  /n8n/statistik         — ringkasan statistik',
            'POST /n8n/chat              — tanya jawab chatbot rule-based (umum)',
            'GET  /n8n/umkm-info         — profil UMKM by session_name ⭐ BARU',
            'POST /n8n/chat-umkm         — chat rule-based scoped ke UMKM tsb   ⭐ BARU',
            'POST /n8n/sync-trigger      — trigger sinkronisasi manual',
        ]
    })


# ============================================================
# ENDPOINT 2: Ambil Semua Produk (untuk n8n baca ke GSheet)
# GET /n8n/produk?api_key=xxx
# GET /n8n/produk?limit=50&offset=0&kategori=Kuliner
# ============================================================
@n8n_bp.route('/produk', methods=['GET'])
@require_api_key
def get_all_produk():
    """
    Kembalikan semua produk dari database.
    n8n bisa memanggil ini secara terjadwal (misal setiap 1 jam)
    dan menulis hasilnya ke Google Sheets otomatis.
    """
    db = get_db()
    
    limit  = request.args.get('limit', 500, type=int)
    offset = request.args.get('offset', 0, type=int)
    kategori = request.args.get('kategori', None)
    hanya_tersedia = request.args.get('tersedia', 'false').lower() == 'true'
    
    query = '''
        SELECT 
            p.id,
            p.nama          AS nama_produk,
            p.deskripsi,
            p.harga,
            p.stok,
            p.tersedia,
            p.kecamatan,
            k.nama          AS kategori,
            u.nama_lengkap  AS nama_umkm,
            u.no_telepon    AS telepon,
            COALESCE(AVG(r.score), 0) AS avg_rating,
            COUNT(r.id)     AS total_ulasan,
            p.created_at,
            p.updated_at
        FROM produk p
        LEFT JOIN kategori k ON p.kategori_id = k.id
        LEFT JOIN users u    ON p.seller_id = u.id
        LEFT JOIN ratings r  ON p.id = r.produk_id
    '''
    
    conditions = []
    params = []
    
    if kategori:
        conditions.append("k.nama LIKE ?")
        params.append(f'%{kategori}%')
    
    if hanya_tersedia:
        conditions.append("p.tersedia = 1 AND p.stok > 0")
    
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    
    query += ' GROUP BY p.id ORDER BY u.nama_lengkap, p.created_at DESC'
    query += f' LIMIT {limit} OFFSET {offset}'
    
    rows = db.execute(query, params).fetchall()
    
    produk_list = []
    for r in rows:
        produk_list.append({
            'id': r['id'],
            'nama_produk': r['nama_produk'],
            'deskripsi': r['deskripsi'] or '',
            'harga': int(r['harga']),
            'harga_format': f"Rp {int(r['harga']):,}".replace(',', '.'),
            'stok': int(r['stok']),
            'tersedia': bool(int(r['tersedia']) == 1 and int(r['stok']) > 0),
            'status_stok': 'Tersedia' if int(r['tersedia']) == 1 and int(r['stok']) > 0 else 'Habis',
            'kecamatan': r['kecamatan'] or '',
            'kategori': r['kategori'] or '',
            'nama_umkm': r['nama_umkm'] or '',
            'telepon': r['telepon'] or '',
            'avg_rating': round(float(r['avg_rating']), 1),
            'total_ulasan': int(r['total_ulasan']),
            'created_at': r['created_at'] or '',
            'updated_at': r['updated_at'] or '',
        })
    
    return jsonify({
        'success': True,
        'total': len(produk_list),
        'limit': limit,
        'offset': offset,
        'updated_at': datetime.now().isoformat(),
        'data': produk_list
    })


# ============================================================
# ENDPOINT 3: Cari Produk (untuk chatbot n8n)
# GET /n8n/produk/cari?q=kopi&api_key=xxx
# ============================================================
@n8n_bp.route('/produk/cari', methods=['GET'])
@require_api_key
def cari_produk():
    """
    Cari produk dengan memecah pesan menjadi keyword individual dan
    menggabungkan hasil berdasarkan relevansi.
    """
    query_input = request.args.get('q', '').strip()
    if not query_input:
        return jsonify({'success': False, 'error': 'Parameter ?q=keyword diperlukan'}), 400
    
    # Stopwords yang diabaikan (kata umum dari pesan WhatsApp)
    STOPWORDS = {
        'cari', 'ada', 'apakah', 'apa', 'yang', 'dong', 'kak', 'mas', 'mbak',
        'pak', 'bu', 'mau', 'minta', 'ingin', 'pesan', 'beli', 'jual',
        'produk', 'barang', 'stok', 'harga', 'berapa', 'dimana', 'dari',
        'untuk', 'dan', 'atau', 'gak', 'ga', 'nggak', 'nih', 'sih', 'deh',
        'ya', 'oke', 'ok', 'info', 'tanya', 'boleh', 'bisa', 'tolong',
        'halo', 'hai', 'hi', 'hello', 'pagi', 'siang', 'sore', 'malam',
    }
    
    keywords = [
        w for w in query_input.lower().split()
        if w not in STOPWORDS and len(w) > 2
    ]
    if not keywords:
        keywords = [query_input]
    
    db = get_db()
    results_map = {}
    
    for kw in keywords:
        pattern = f'%{kw}%'
        rows = db.execute('''
            SELECT p.id, p.nama, p.harga, p.stok, p.tersedia, p.kecamatan, 
                   k.nama AS kategori, u.nama_lengkap, u.no_telepon, 
                   COALESCE(AVG(r.score), 0) AS avg_rating
            FROM produk p
            LEFT JOIN kategori k ON p.kategori_id = k.id
            LEFT JOIN users u ON p.seller_id = u.id
            LEFT JOIN ratings r ON p.id = r.produk_id
            WHERE p.nama LIKE ? OR p.deskripsi LIKE ?
            GROUP BY p.id
        ''', (pattern, pattern)).fetchall()
        
        for r in rows:
            if r['id'] not in results_map:
                results_map[r['id']] = {'data': r, 'score': 0}
            results_map[r['id']]['score'] += 1
            
    sorted_results = sorted(results_map.values(), key=lambda x: x['score'], reverse=True)[:10]
    
    hasil = []
    for item in sorted_results:
        r = item['data']
        tersedia = bool(int(r['tersedia']) == 1 and int(r['stok']) > 0)
        hasil.append({
            'id': r['id'],
            'nama_produk': r['nama'],
            'harga_format': f"Rp {int(r['harga']):,}".replace(',', '.'),
            'status_stok': '✅ Tersedia' if tersedia else '❌ Habis',
            'stok': int(r['stok']),
            'kecamatan': r['kecamatan'] or '-',
            'kategori': r['kategori'] or '-',
            'nama_umkm': r['nama_lengkap'] or '-',
            'telepon': r['no_telepon'] or '-',
            'rating': round(float(r['avg_rating']), 1),
        })
    
    if hasil:
        teks_ringkasan = f"🔍 Hasil pencarian '{query_input}' ({len(hasil)} produk ditemukan):\n\n"
        for i, p in enumerate(hasil[:5], 1):
            teks_ringkasan += (
                f"{i}. *{p['nama_produk']}* — {p['harga_format']}\n"
                f"   {p['status_stok']} | Stok: {p['stok']}\n"
                f"   📍 {p['kecamatan']} | 🏪 {p['nama_umkm']}\n"
                f"   📞 {p['telepon']}\n\n"
            )
    else:
        teks_ringkasan = f"❌ Produk '{query_input}' tidak ditemukan di katalog UMKM Kendari."
    
    return jsonify({
        'success': True,
        'keyword': query_input,
        'total_ditemukan': len(hasil),
        'teks_chatbot': teks_ringkasan,
        'data': hasil
    })


# ============================================================
# ENDPOINT 4: Statistik Ringkasan
# GET /n8n/statistik?api_key=xxx
# ============================================================
@n8n_bp.route('/statistik', methods=['GET'])
@require_api_key
def get_statistik():
    """
    Ringkasan statistik database.
    Cocok untuk dashboard n8n atau laporan otomatis ke WA.
    """
    db = get_db()
    
    total_produk = db.execute("SELECT COUNT(*) as c FROM produk").fetchone()['c']
    produk_tersedia = db.execute(
        "SELECT COUNT(*) as c FROM produk WHERE tersedia=1 AND stok>0"
    ).fetchone()['c']
    total_umkm = db.execute(
        "SELECT COUNT(DISTINCT id) as c FROM users WHERE role='seller'"
    ).fetchone()['c']
    total_transaksi = db.execute("SELECT COUNT(*) as c FROM pesanan").fetchone()['c'] if _table_exists(db, 'pesanan') else 0
    total_rating = db.execute("SELECT COUNT(*) as c FROM ratings").fetchone()['c'] if _table_exists(db, 'ratings') else 0
    
    # Produk per kategori
    per_kategori = db.execute('''
        SELECT k.nama, COUNT(p.id) as jumlah
        FROM produk p
        LEFT JOIN kategori k ON p.kategori_id = k.id
        GROUP BY k.nama
        ORDER BY jumlah DESC
        LIMIT 10
    ''').fetchall()
    
    return jsonify({
        'success': True,
        'updated_at': datetime.now().isoformat(),
        'ringkasan': {
            'total_produk': total_produk,
            'produk_tersedia': produk_tersedia,
            'produk_habis': total_produk - produk_tersedia,
            'total_umkm': total_umkm,
            'total_transaksi': total_transaksi,
            'total_ulasan': total_rating,
        },
        'per_kategori': [
            {'kategori': r['nama'] or 'Lainnya', 'jumlah': r['jumlah']}
            for r in per_kategori
        ]
    })


# ============================================================
# ENDPOINT 5: Chat rule-based (Chatbot n8n)
# POST /n8n/chat
# Body: {"message": "ada produk kopi?", "user_id": "628xxx"}
# ============================================================
@n8n_bp.route('/chat', methods=['POST'])
@require_api_key
def chat_n8n():
    """
    Endpoint chatbot untuk n8n.
    n8n mengirim pesan user lalu Flask menjawab memakai aturan sederhana.
    
    Cocok untuk integrasi:
    - WhatsApp via n8n + Twilio/WA Cloud API
    - Telegram Bot via n8n
    - Chat widget lainnya
    """
    data = request.get_json()
    
    if not data or 'message' not in data:
        return jsonify({
            'success': False,
            'error': "Body JSON harus mengandung field 'message'"
        }), 400
    
    user_message = data.get('message', '').strip()
    user_id = data.get('user_id', 'anonymous')  # ID WA user atau identifier lain
    
    if not user_message:
        return jsonify({
            'success': False,
            'error': 'Pesan tidak boleh kosong'
        }), 400
    
    # Import service chatbot
    try:
        from services.ai_chat import get_ai_response
        jawaban = get_ai_response(
            user_message,
            conversation_id=f"n8n:general:{user_id}"
        )
    except Exception as e:
        jawaban = f"Maaf, layanan chatbot sedang gangguan. Error: {str(e)}"
    
    return jsonify({
        'success': True,
        'user_id': user_id,
        'pertanyaan': user_message,
        'jawaban': jawaban,
        'timestamp': datetime.now().isoformat()
    })


# ============================================================
# ENDPOINT 6: Trigger Sync (n8n panggil ini untuk sync manual)
# POST /n8n/sync-trigger
# ============================================================
@n8n_bp.route('/sync-trigger', methods=['POST'])
@require_api_key
def sync_trigger():
    """
    Trigger sinkronisasi data ke Google Sheets.
    n8n bisa memanggil ini setiap X menit untuk auto-sync.
    Return data JSON agar n8n yang menulis ke Google Sheets.
    """
    db = get_db()
    rows = db.execute('''
        SELECT 
            p.id,
            p.nama          AS nama_produk,
            p.deskripsi,
            p.harga,
            p.stok,
            p.tersedia,
            p.kecamatan,
            k.nama          AS kategori,
            u.nama_lengkap  AS nama_umkm,
            u.no_telepon    AS telepon,
            COALESCE(AVG(r.score), 0) AS avg_rating,
            COUNT(r.id)     AS total_ulasan,
            p.updated_at
        FROM produk p
        LEFT JOIN kategori k ON p.kategori_id = k.id
        LEFT JOIN users u    ON p.seller_id = u.id
        LEFT JOIN ratings r  ON p.id = r.produk_id
        GROUP BY p.id
        ORDER BY u.nama_lengkap, p.nama ASC
    ''').fetchall()
    
    # Format data siap tulis ke Google Sheets
    gsheet_rows = [['ID', 'Nama Produk', 'Deskripsi', 'Harga (Rp)', 'Stok',
                    'Status', 'Kecamatan', 'Kategori', 'Nama UMKM',
                    'Telepon', 'Rating', 'Ulasan', 'Update Terakhir']]
    
    for r in rows:
        tersedia = '✅ Ada' if int(r['tersedia']) == 1 and int(r['stok']) > 0 else '❌ Habis'
        gsheet_rows.append([
            r['id'],
            r['nama_produk'],
            r['deskripsi'] or '-',
            int(r['harga']),
            int(r['stok']),
            tersedia,
            r['kecamatan'] or '-',
            r['kategori'] or '-',
            r['nama_umkm'] or '-',
            r['telepon'] or '-',
            round(float(r['avg_rating']), 1),
            int(r['total_ulasan']),
            r['updated_at'] or '-'
        ])
    
    return jsonify({
        'success': True,
        'sync_time': datetime.now().isoformat(),
        'total_produk': len(rows),
        'sheet_data': gsheet_rows  # Array 2D siap untuk Google Sheets node di n8n
    })


# ============================================================
# ENDPOINT 7: Info UMKM by Session Name (WAHA → n8n → Flask)
# GET /n8n/umkm-info?session_name=628xxx&api_key=xxx
#
# WAHA menyertakan session_name (nomor WA penjual) ke n8n.
# n8n memanggil endpoint ini untuk dapat profil UMKM + produk.
# Hasilnya digunakan sebagai konteks sistem chatbot.
# ============================================================
@n8n_bp.route('/umkm-info', methods=['GET'])
@require_api_key
def get_umkm_info():
    """
    Ambil profil UMKM + daftar produk berdasarkan session_name WAHA.

    session_name di WAHA = nomor WhatsApp penjual (e.g. '628123456789').
    Nomor ini dicocokkan dengan kolom no_telepon di tabel users (seller).

    Contoh panggilan dari n8n:
        GET /n8n/umkm-info?session_name=628123456789&api_key=umkm-kendari-secret-2024

    Return JSON:
    {
      "success": true,
      "session_name": "628123456789",
      "umkm": {
        "id": 3,
        "nama_lengkap": "Toko Kopi Dara",
        "no_telepon": "628123456789",
        "alamat": "Jl. Beringin No.5, Kendari",
        "email": "kopi@example.com",
        "jumlah_produk": 8,
        "produk": [...]
      },
      "system_prompt": "Kamu adalah asisten virtual untuk UMKM ..."
    }
    """
    session_name = request.args.get('session_name', '').strip()
    if not session_name:
        return jsonify({
            'success': False,
            'error': 'Parameter ?session_name=<nomor_wa> diperlukan'
        }), 400

    db = get_db()

    # Normalkan: hapus leading '+' jika ada, atau '0' di awal → '62'
    # WAHA biasanya pakai format '628xxx@c.us' atau '628xxx'
    clean_session = session_name.split('@')[0].lstrip('+')
    local_session = '0' + clean_session[2:] if clean_session.startswith('62') else clean_session
    intl_session = '62' + clean_session[1:] if clean_session.startswith('0') else clean_session

    # Cari seller berdasarkan no_telepon
    seller = db.execute('''
        SELECT id, nama_lengkap, email, no_telepon, alamat, created_at
        FROM users
        WHERE role = 'seller'
          AND (
            no_telepon = ?
            OR no_telepon = ?
            OR REPLACE(REPLACE(no_telepon, '+', ''), '-', '') = ?
            OR REPLACE(REPLACE(no_telepon, '+', ''), '-', '') = ?
          )
        LIMIT 1
    ''', (clean_session, '+' + intl_session, intl_session, local_session)).fetchone()

    if not seller:
        return jsonify({
            'success': False,
            'session_name': session_name,
            'error': f'UMKM dengan nomor {clean_session} tidak ditemukan di database.',
            'hint': 'Pastikan no_telepon seller di database sesuai dengan session_name WAHA.'
        }), 404

    seller_id = seller['id']

    # Ambil produk-produk milik seller ini
    produk_rows = db.execute('''
        SELECT
            p.id,
            p.nama,
            p.deskripsi,
            p.harga,
            p.stok,
            p.tersedia,
            p.kecamatan,
            k.nama AS kategori,
            COALESCE(AVG(r.score), 0) AS avg_rating,
            COUNT(r.id) AS total_ulasan
        FROM produk p
        LEFT JOIN kategori k ON p.kategori_id = k.id
        LEFT JOIN ratings r ON p.id = r.produk_id
        WHERE p.seller_id = ?
        GROUP BY p.id
        ORDER BY p.tersedia DESC, p.nama ASC
    ''', (seller_id,)).fetchall()

    produk_list = []
    produk_teks_list = []  # Untuk system prompt chatbot
    for p in produk_rows:
        tersedia = bool(int(p['tersedia']) == 1 and int(p['stok']) > 0)
        item = {
            'id': p['id'],
            'nama': p['nama'],
            'deskripsi': p['deskripsi'] or '',
            'harga': int(p['harga']),
            'harga_format': f"Rp {int(p['harga']):,}".replace(',', '.'),
            'stok': int(p['stok']),
            'tersedia': tersedia,
            'status': 'Tersedia' if tersedia else 'Habis',
            'kecamatan': p['kecamatan'] or 'Kendari',
            'kategori': p['kategori'] or 'Umum',
            'rating': round(float(p['avg_rating']), 1),
            'total_ulasan': int(p['total_ulasan']),
        }
        produk_list.append(item)
        # Baris ringkas untuk system prompt
        produk_teks_list.append(
            f"- {p['nama']} | "
            f"Rp {int(p['harga']):,} | "
            f"{'Tersedia' if tersedia else 'Habis'} (stok {p['stok']}) | "
            f"Kat: {p['kategori'] or 'Umum'}"
        )

    produk_teks = '\n'.join(produk_teks_list) if produk_teks_list else 'Belum ada produk terdaftar.'

    # Buat system prompt siap pakai untuk chatbot di n8n
    system_prompt = (
        f"Kamu adalah asisten virtual WhatsApp untuk UMKM *{seller['nama_lengkap']}* "
        f"yang berlokasi di {seller['alamat'] or 'Kota Kendari'}. "
        f"Nomor WA toko: {seller['no_telepon']}.\n\n"
        f"Daftar produk yang tersedia saat ini:\n{produk_teks}\n\n"
        f"Tugasmu:\n"
        f"1. Jawab pertanyaan pelanggan tentang produk, harga, stok, dan lokasi."
        f" Gunakan data produk di atas.\n"
        f"2. Jika stok habis, sampaikan dengan sopan dan tawarkan produk lain.\n"
        f"3. Jika ada pertanyaan di luar produk toko ini, jawab secara umum tapi "
        f"tetap arahkan kembali ke produk toko.\n"
        f"4. Gunakan bahasa Indonesia yang ramah dan singkat (cocok untuk WhatsApp).\n"
        f"5. Jangan membuat harga atau stok yang tidak ada dalam daftar di atas."
    )

    return jsonify({
        'success': True,
        'session_name': session_name,
        'umkm': {
            'id': seller_id,
            'nama_lengkap': seller['nama_lengkap'],
            'email': seller['email'] or '',
            'no_telepon': seller['no_telepon'] or '',
            'alamat': seller['alamat'] or '',
            'jumlah_produk': len(produk_list),
            'produk': produk_list,
        },
        'system_prompt': system_prompt,
        'updated_at': datetime.now().isoformat()
    })


# ============================================================
# ENDPOINT 8: Chat rule-based scoped ke UMKM (alur lengkap WAHA)
# POST /n8n/chat-umkm
# Body: {
#   "message": "ada produk kopi?",
#   "session_name": "628123456789",
#   "user_wa": "628999888777"       ← nomor pelanggan (opsional)
# }
# ============================================================
@n8n_bp.route('/chat-umkm', methods=['POST'])
@require_api_key
def chat_umkm():
    """
    Endpoint chatbot rule-based yang konteksnya disesuaikan dengan UMKM tertentu.

    Alur di n8n:
      1. WAHA Trigger → dapat message + session_name
      2. HTTP Request ke /n8n/umkm-info?session_name=xxx → dapat system_prompt
      3. HTTP Request ke /n8n/chat-umkm dengan body di bawah ini
      4. Jawaban chatbot dikembalikan ke WAHA untuk dikirim ke pelanggan

    Atau: jika ingin satu langkah, kirim semua ke endpoint ini.
    Flask akan otomatis fetch umkm-info internal lalu jawab.
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Body JSON diperlukan'}), 400

    message      = data.get('message', '').strip()
    session_name = data.get('session_name', '').strip()
    user_wa      = data.get('user_wa', 'anonymous')
    # Opsional: system_prompt yang sudah di-fetch sebelumnya oleh n8n
    system_prompt_override = data.get('system_prompt', '').strip()

    if not message:
        return jsonify({'success': False, 'error': "Field 'message' tidak boleh kosong"}), 400
    if not session_name:
        return jsonify({'success': False, 'error': "Field 'session_name' wajib diisi (nomor WA UMKM)"}), 400

    db = get_db()

    # ── Ambil konteks UMKM (sama seperti /umkm-info) ────────────────────────
    clean_session = session_name.split('@')[0].lstrip('+')
    local_session = '0' + clean_session[2:] if clean_session.startswith('62') else clean_session
    intl_session = '62' + clean_session[1:] if clean_session.startswith('0') else clean_session

    seller = db.execute('''
        SELECT id, nama_lengkap, no_telepon, alamat
        FROM users
        WHERE role = 'seller'
          AND (
            no_telepon = ?
            OR no_telepon = ?
            OR REPLACE(REPLACE(no_telepon, '+', ''), '-', '') = ?
            OR REPLACE(REPLACE(no_telepon, '+', ''), '-', '') = ?
          )
        LIMIT 1
    ''', (clean_session, '+' + intl_session, intl_session, local_session)).fetchone()

    if not seller:
        return jsonify({
            'success': False,
            'error': f'UMKM dengan session {session_name} tidak ditemukan.',
            'jawaban': 'Maaf, toko ini belum terdaftar di sistem kami.'
        }), 404

    # Gunakan system_prompt dari request jika ada (lebih efisien, n8n fetch duluan)
    if system_prompt_override:
        system_prompt = system_prompt_override
    else:
        # Bangun system_prompt dari database
        produk_rows = db.execute('''
            SELECT p.nama, p.harga, p.stok, p.tersedia, k.nama AS kategori
            FROM produk p
            LEFT JOIN kategori k ON p.kategori_id = k.id
            WHERE p.seller_id = ?
            ORDER BY p.tersedia DESC, p.nama ASC
        ''', (seller['id'],)).fetchall()

        baris = []
        for p in produk_rows:
            tersedia = bool(int(p['tersedia']) == 1 and int(p['stok']) > 0)
            baris.append(
                f"- {p['nama']} | Rp {int(p['harga']):,} | "
                f"{'Tersedia' if tersedia else 'Habis'} (stok {p['stok']}) | "
                f"Kat: {p['kategori'] or 'Umum'}"
            )

        produk_teks = '\n'.join(baris) if baris else 'Belum ada produk terdaftar.'
        system_prompt = (
            f"Kamu adalah asisten virtual WhatsApp untuk UMKM *{seller['nama_lengkap']}* "
            f"di {seller['alamat'] or 'Kota Kendari'}. "
            f"Nomor WA toko: {seller['no_telepon']}.\n\n"
            f"Produk saat ini:\n{produk_teks}\n\n"
            f"Jawab pertanyaan pelanggan tentang produk, harga, dan stok. "
            f"Gunakan bahasa Indonesia ramah dan singkat (untuk WhatsApp)."
        )

    # ── Panggil chatbot rule-based ───────────────────────────────────────────
    try:
        from services.ai_chat import get_ai_response
        # Kirim system_prompt sebagai konteks jika fungsi mendukung parameter tsb
        import inspect
        sig = inspect.signature(get_ai_response)
        conversation_id = f"n8n:{session_name}:{user_wa}"
        if 'seller_id' in sig.parameters:
            jawaban = get_ai_response(
                message,
                system_prompt=system_prompt,
                conversation_id=conversation_id,
                seller_id=seller['id']
            )
        elif 'system_prompt' in sig.parameters:
            jawaban = get_ai_response(message, system_prompt=system_prompt)
        else:
            # Fallback: gabungkan system prompt ke dalam pesan
            gabungan = f"{system_prompt}\n\n---\nPertanyaan pelanggan: {message}"
            jawaban  = get_ai_response(gabungan)
    except Exception as e:
        jawaban = f"Maaf, layanan chatbot sedang gangguan. Silakan coba lagi.\n(Error: {e})"

    return jsonify({
        'success': True,
        'session_name': session_name,
        'user_wa': user_wa,
        'umkm': seller['nama_lengkap'],
        'pertanyaan': message,
        'jawaban': jawaban,
        'timestamp': datetime.now().isoformat()
    })


# ============================================================
# Helper
# ============================================================
def _table_exists(db, table_name: str) -> bool:
    result = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
    ).fetchone()
    return result is not None
