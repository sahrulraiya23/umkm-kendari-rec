"""
routes/n8n_api.py
API endpoint khusus untuk integrasi dengan n8n.

Endpoint ini memungkinkan:
1. n8n membaca data produk real-time dari database
2. n8n mengirim pertanyaan chatbot dan mendapat jawaban AI
3. n8n melakukan sync data ke Google Sheets otomatis
4. n8n mendapat notifikasi jika ada perubahan data

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
            'GET  /n8n/ping           — health check',
            'GET  /n8n/produk         — semua produk',
            'GET  /n8n/produk/cari    — cari produk (?q=keyword)',
            'GET  /n8n/statistik      — ringkasan statistik',
            'POST /n8n/chat           — tanya jawab chatbot AI',
            'POST /n8n/sync-trigger   — trigger sinkronisasi manual',
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
    Cari produk berdasarkan keyword.
    Digunakan oleh chatbot n8n ketika user menanyakan produk tertentu.
    """
    keyword = request.args.get('q', '').strip()
    
    if not keyword:
        return jsonify({
            'success': False,
            'error': 'Parameter ?q=keyword diperlukan'
        }), 400
    
    db = get_db()
    rows = db.execute('''
        SELECT 
            p.id,
            p.nama          AS nama_produk,
            p.harga,
            p.stok,
            p.tersedia,
            p.kecamatan,
            k.nama          AS kategori,
            u.nama_lengkap  AS nama_umkm,
            u.no_telepon    AS telepon,
            COALESCE(AVG(r.score), 0) AS avg_rating
        FROM produk p
        LEFT JOIN kategori k ON p.kategori_id = k.id
        LEFT JOIN users u    ON p.seller_id = u.id
        LEFT JOIN ratings r  ON p.id = r.produk_id
        WHERE (p.nama LIKE ? OR p.deskripsi LIKE ? OR k.nama LIKE ?)
        GROUP BY p.id
        ORDER BY p.tersedia DESC, avg_rating DESC
        LIMIT 10
    ''', (f'%{keyword}%', f'%{keyword}%', f'%{keyword}%')).fetchall()
    
    hasil = []
    for r in rows:
        tersedia = bool(int(r['tersedia']) == 1 and int(r['stok']) > 0)
        hasil.append({
            'id': r['id'],
            'nama_produk': r['nama_produk'],
            'harga_format': f"Rp {int(r['harga']):,}".replace(',', '.'),
            'status_stok': '✅ Tersedia' if tersedia else '❌ Habis',
            'stok': int(r['stok']),
            'kecamatan': r['kecamatan'] or '-',
            'kategori': r['kategori'] or '-',
            'nama_umkm': r['nama_umkm'] or '-',
            'telepon': r['telepon'] or '-',
            'rating': round(float(r['avg_rating']), 1),
        })
    
    # Format teks ringkasan untuk langsung dipakai chatbot
    if hasil:
        teks_ringkasan = f"🔍 Hasil pencarian '{keyword}' ({len(hasil)} produk ditemukan):\n\n"
        for i, p in enumerate(hasil[:5], 1):
            teks_ringkasan += (
                f"{i}. *{p['nama_produk']}* — {p['harga_format']}\n"
                f"   {p['status_stok']} | Stok: {p['stok']}\n"
                f"   📍 {p['kecamatan']} | 🏪 {p['nama_umkm']}\n"
                f"   📞 {p['telepon']}\n\n"
            )
    else:
        teks_ringkasan = f"❌ Produk '{keyword}' tidak ditemukan di katalog UMKM Kendari."
    
    return jsonify({
        'success': True,
        'keyword': keyword,
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
# ENDPOINT 5: Chat dengan AI (Chatbot n8n → Gemini)
# POST /n8n/chat
# Body: {"message": "ada produk kopi?", "user_id": "628xxx"}
# ============================================================
@n8n_bp.route('/chat', methods=['POST'])
@require_api_key
def chat_n8n():
    """
    Endpoint chatbot untuk n8n.
    n8n mengirim pesan user → Flask meneruskan ke Gemini AI → jawaban dikembalikan.
    
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
    
    # Import service AI
    try:
        from services.ai_chat import get_ai_response
        jawaban = get_ai_response(user_message)
    except Exception as e:
        jawaban = f"Maaf, layanan AI sedang gangguan. Error: {str(e)}"
    
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
# Helper
# ============================================================
def _table_exists(db, table_name: str) -> bool:
    result = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
    ).fetchone()
    return result is not None
