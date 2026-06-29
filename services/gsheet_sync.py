"""
services/gsheet_sync.py
Service auto-sinkronisasi data produk UMKM → Google Sheets.

Dipanggil otomatis setiap kali produk ditambah, diedit, atau dihapus.
Berjalan di background thread agar tidak memperlambat response Flask.

SETUP (cukup sekali):
1. pip install gspread google-auth (sudah dilakukan)
2. Letakkan credentials.json di root folder proyek
3. Set SPREADSHEET_ID di config.py atau environment variable
4. Share Google Sheet ke email service account
"""

import threading
import sqlite3
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ============================================================
# Ambil config dari environment atau config.py
# ============================================================
SPREADSHEET_ID = os.environ.get('GSHEET_SPREADSHEET_ID', '')
CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'service_account.json')
DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'umkm_kendari.db')

# Sheet per seller: True = buat tab terpisah per UMKM, False = satu sheet semua
SHEET_PER_SELLER = True


def _is_configured() -> bool:
    """Cek apakah konfigurasi Google Sheets sudah lengkap."""
    if not SPREADSHEET_ID:
        logger.warning("[GSheet] GSHEET_SPREADSHEET_ID belum diset. Sync dilewati.")
        return False
    if not os.path.exists(CREDENTIALS_FILE):
        logger.warning(f"[GSheet] credentials.json tidak ditemukan. Sync dilewati.")
        return False
    return True


def _get_seller_data(seller_id: int) -> dict:
    """Ambil data seller dan semua produknya dari SQLite."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row

    seller = conn.execute(
        "SELECT id, nama_lengkap, no_telepon FROM users WHERE id = ?", (seller_id,)
    ).fetchone()

    if not seller:
        conn.close()
        return {}

    rows = conn.execute('''
        SELECT 
            p.id,
            p.nama          AS nama_produk,
            p.deskripsi,
            p.harga,
            p.stok,
            p.tersedia,
            p.kecamatan,
            k.nama          AS kategori,
            u.no_telepon    AS telepon,
            COALESCE(AVG(r.score), 0) AS avg_rating,
            COUNT(r.id)     AS total_ulasan,
            p.created_at
        FROM produk p
        LEFT JOIN kategori k ON p.kategori_id = k.id
        LEFT JOIN users u    ON p.seller_id = u.id
        LEFT JOIN ratings r  ON p.id = r.produk_id
        WHERE p.seller_id = ?
        GROUP BY p.id
        ORDER BY p.created_at DESC
    ''', (seller_id,)).fetchall()

    conn.close()
    return {
        'seller_nama': seller['nama_lengkap'],
        'seller_id': seller_id,
        'rows': rows
    }


def _get_all_data() -> list:
    """Ambil semua data produk dari semua seller."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute('''
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
            p.created_at
        FROM produk p
        LEFT JOIN kategori k ON p.kategori_id = k.id
        LEFT JOIN users u    ON p.seller_id = u.id
        LEFT JOIN ratings r  ON p.id = r.produk_id
        GROUP BY p.id
        ORDER BY u.nama_lengkap, p.created_at DESC
    ''').fetchall()
    conn.close()
    return rows


def _rows_to_sheet_data(rows, include_umkm_col=False) -> list:
    """Konversi rows SQLite ke format list untuk Google Sheets."""
    if include_umkm_col:
        header = ['ID', 'Nama UMKM', 'Nama Produk', 'Deskripsi', 'Harga',
                  'Stok', 'Tersedia', 'Kategori', 'Kecamatan', 'Telepon',
                  'Rating', 'Total Ulasan', 'Terakhir Update']
    else:
        header = ['ID', 'Nama Produk', 'Deskripsi', 'Harga',
                  'Stok', 'Tersedia', 'Kategori', 'Kecamatan', 'Telepon',
                  'Rating', 'Total Ulasan', 'Terakhir Update']

    data = [header]
    for r in rows:
        tersedia = "✅ Ada" if int(r['tersedia']) == 1 and int(r['stok']) > 0 else "❌ Habis"
        harga_fmt = f"Rp {int(r['harga']):,}".replace(',', '.')
        
        if include_umkm_col:
            row = [
                r['id'], r['nama_umkm'], r['nama_produk'],
                r['deskripsi'] or '-', harga_fmt,
                int(r['stok']), tersedia,
                r['kategori'] or '-', r['kecamatan'] or '-',
                r['telepon'] or '-',
                round(float(r['avg_rating']), 1), int(r['total_ulasan']),
                datetime.now().strftime('%Y-%m-%d %H:%M')
            ]
        else:
            row = [
                r['id'], r['nama_produk'],
                r['deskripsi'] or '-', harga_fmt,
                int(r['stok']), tersedia,
                r['kategori'] or '-', r['kecamatan'] or '-',
                r['telepon'] or '-',
                round(float(r['avg_rating']), 1), int(r['total_ulasan']),
                datetime.now().strftime('%Y-%m-%d %H:%M')
            ]
        data.append(row)
    return data


def _do_sync(seller_id: int = None):
    """
    Fungsi sinkronisasi utama (dijalankan di thread).
    seller_id = None → sync semua produk ke satu sheet
    seller_id = int  → sync produk seller tertentu ke tab khusus
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(SPREADSHEET_ID)

        if seller_id and SHEET_PER_SELLER:
            # Sync tab khusus untuk seller ini
            data_info = _get_seller_data(seller_id)
            if not data_info:
                return

            seller_nama = data_info['seller_nama']
            rows = data_info['rows']
            tab_name = f"UMKM - {seller_nama}"[:100]  # Max 100 karakter
            sheet_data = _rows_to_sheet_data(rows, include_umkm_col=False)
        else:
            # Sync semua ke satu sheet "Semua Produk"
            rows = _get_all_data()
            tab_name = "Semua Produk"
            sheet_data = _rows_to_sheet_data(rows, include_umkm_col=True)

        # Buka atau buat worksheet
        try:
            ws = spreadsheet.worksheet(tab_name)
            ws.clear()
        except gspread.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=tab_name, rows=1000, cols=15)

        # Upload data
        ws.update(sheet_data, value_input_option='USER_ENTERED')

        # Format header
        last_col = chr(ord('A') + len(sheet_data[0]) - 1)
        ws.format(f'A1:{last_col}1', {
            'backgroundColor': {'red': 0.13, 'green': 0.59, 'blue': 0.95},
            'textFormat': {
                'bold': True,
                'foregroundColor': {'red': 1.0, 'green': 1.0, 'blue': 1.0}
            },
            'horizontalAlignment': 'CENTER'
        })

        total = len(sheet_data) - 1
        logger.info(f"[GSheet] ✅ Auto-sync selesai: '{tab_name}' — {total} produk")

    except ImportError:
        logger.error("[GSheet] gspread belum terinstall: pip install gspread google-auth")
    except Exception as e:
        logger.error(f"[GSheet] Sync gagal: {type(e).__name__}: {e}")


def sync_seller(seller_id: int):
    """
    Panggil ini setiap kali produk seller berubah.
    Berjalan di background — tidak memperlambat response Flask.
    """
    if not _is_configured():
        return
    thread = threading.Thread(
        target=_do_sync,
        args=(seller_id,),
        daemon=True,
        name=f"gsheet-sync-seller-{seller_id}"
    )
    thread.start()
    logger.info(f"[GSheet] Background sync dimulai untuk seller_id={seller_id}")


def sync_all():
    """
    Sync semua produk ke Google Sheets.
    Bisa dipanggil manual atau dari scheduler.
    """
    if not _is_configured():
        return
    thread = threading.Thread(
        target=_do_sync,
        args=(None,),
        daemon=True,
        name="gsheet-sync-all"
    )
    thread.start()
    logger.info("[GSheet] Background sync semua produk dimulai")
