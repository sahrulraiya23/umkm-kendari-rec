"""
sync_to_gsheet.py
Script untuk sinkronisasi data produk UMKM dari database SQLite
ke Google Sheets — agar chatbot WA n8n bisa membaca data real-time.

CARA PAKAI:
1. Install dependency:
   pip install gspread google-auth

2. Buat Google Service Account:
   - Buka: https://console.cloud.google.com/
   - Buat project baru → Enable "Google Sheets API"
   - IAM & Admin → Service Accounts → Create Service Account
   - Buat Key (JSON) → Download → simpan sebagai: credentials.json
   - Buka Google Sheet kamu → Share ke email service account

3. Set nama sheet dan ID di bagian CONFIG di bawah

4. Jalankan:
   python sync_to_gsheet.py
   
   Atau untuk UMKM tertentu (misal Suntoast):
   python sync_to_gsheet.py --umkm "Suntoast"
   
   Untuk semua UMKM:
   python sync_to_gsheet.py --all
"""

import sqlite3
import os
import sys
import argparse
from datetime import datetime

# ============================================================
# CONFIG — Sesuaikan dengan Google Sheet kamu
# ============================================================
DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'umkm_kendari.db')
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), 'credentials.json')

# ID Google Sheet kamu (dari URL: https://docs.google.com/spreadsheets/d/ID_INI/edit)
SPREADSHEET_ID = 'GANTI_DENGAN_ID_GOOGLE_SHEET_KAMU'

# Nama sheet/tab (default: Sheet1)
SHEET_NAME = 'Data UMKM'
# ============================================================


def get_db_connection():
    """Koneksi ke SQLite database lokal."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_produk_dari_db(nama_umkm: str = None):
    """
    Ambil data produk dari database.
    Jika nama_umkm diisi, filter berdasarkan nama seller/UMKM.
    """
    conn = get_db_connection()
    
    if nama_umkm:
        # Filter berdasarkan nama UMKM/seller (pencarian fleksibel)
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
            WHERE u.nama_lengkap LIKE ?
            GROUP BY p.id
            ORDER BY p.created_at DESC
        ''', (f'%{nama_umkm}%',)).fetchall()
    else:
        # Ambil semua produk
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


def sync_ke_gsheet(rows, nama_umkm=None):
    """Upload data ke Google Sheets menggunakan gspread."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        print("❌ Library belum terinstall! Jalankan:")
        print("   pip install gspread google-auth")
        sys.exit(1)

    if not os.path.exists(CREDENTIALS_FILE):
        print(f"❌ File credentials.json tidak ditemukan di: {CREDENTIALS_FILE}")
        print("   Download dari Google Cloud Console → Service Account → Keys")
        sys.exit(1)

    if SPREADSHEET_ID == 'GANTI_DENGAN_ID_GOOGLE_SHEET_KAMU':
        print("❌ Belum set SPREADSHEET_ID di script ini!")
        print("   Buka Google Sheet → salin ID dari URL → tempel di bagian CONFIG")
        sys.exit(1)

    print("🔗 Menghubungkan ke Google Sheets...")
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    client = gspread.authorize(creds)

    # Buka spreadsheet
    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
    except Exception as e:
        print(f"❌ Gagal membuka Google Sheet: {e}")
        print("   Pastikan Sheet sudah di-share ke email service account!")
        sys.exit(1)

    # Tentukan nama tab sheet
    tab_name = f"UMKM - {nama_umkm}" if nama_umkm else SHEET_NAME
    
    try:
        worksheet = spreadsheet.worksheet(tab_name)
        worksheet.clear()
        print(f"✅ Sheet '{tab_name}' ditemukan, data lama dihapus.")
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=tab_name, rows=500, cols=15)
        print(f"✅ Sheet baru '{tab_name}' dibuat.")

    # Header kolom
    header = [
        'ID', 'Nama Produk', 'Deskripsi', 'Harga (Rp)',
        'Stok', 'Tersedia', 'Kecamatan', 'Kategori',
        'Nama UMKM', 'Telepon', 'Rating Rata-rata',
        'Total Ulasan', 'Tanggal Ditambah'
    ]

    # Konversi data ke list of list
    data_rows = [header]
    for r in rows:
        tersedia = "✅ Ada" if int(r['tersedia']) == 1 and int(r['stok']) > 0 else "❌ Habis"
        data_rows.append([
            r['id'],
            r['nama_produk'],
            r['deskripsi'] or '-',
            f"Rp {int(r['harga']):,}".replace(',', '.'),
            int(r['stok']),
            tersedia,
            r['kecamatan'] or '-',
            r['kategori'] or '-',
            r['nama_umkm'] or '-',
            r['telepon'] or '-',
            round(float(r['avg_rating']), 1),
            int(r['total_ulasan']),
            r['created_at'] or '-'
        ])

    # Upload semua sekaligus (lebih cepat)
    worksheet.update(data_rows, value_input_option='USER_ENTERED')

    # Format header (bold & background biru)
    worksheet.format('A1:M1', {
        'backgroundColor': {'red': 0.2, 'green': 0.5, 'blue': 0.8},
        'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
        'horizontalAlignment': 'CENTER'
    })

    total = len(data_rows) - 1  # dikurangi header
    waktu = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n✅ Sinkronisasi selesai!")
    print(f"   📊 {total} produk berhasil dikirim ke Google Sheets")
    print(f"   📋 Sheet: '{tab_name}'")
    print(f"   🕐 Waktu: {waktu}")
    print(f"\n🔗 Buka: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit")


def main():
    parser = argparse.ArgumentParser(
        description='Sinkronisasi data UMKM Kendari → Google Sheets'
    )
    parser.add_argument('--umkm', type=str, help='Filter nama UMKM tertentu (contoh: Suntoast)')
    parser.add_argument('--all', action='store_true', help='Sync semua UMKM')
    args = parser.parse_args()

    if not args.umkm and not args.all:
        print("Gunakan salah satu:")
        print("  python sync_to_gsheet.py --umkm \"NamaUMKM\"")
        print("  python sync_to_gsheet.py --all")
        sys.exit(0)

    nama_umkm = args.umkm if args.umkm else None
    
    print(f"📦 Mengambil data dari database...")
    if nama_umkm:
        print(f"   Filter UMKM: '{nama_umkm}'")
    else:
        print(f"   Mode: Semua UMKM")
    
    rows = fetch_produk_dari_db(nama_umkm)
    
    if not rows:
        print(f"⚠️  Tidak ada data ditemukan untuk UMKM: '{nama_umkm}'")
        print("   Coba cek nama UMKM yang tersedia:")
        conn = get_db_connection()
        sellers = conn.execute("SELECT DISTINCT nama_lengkap FROM users WHERE role='seller'").fetchall()
        conn.close()
        for s in sellers:
            print(f"   - {s['nama_lengkap']}")
        sys.exit(0)
    
    print(f"   ✅ {len(rows)} produk ditemukan")
    sync_ke_gsheet(rows, nama_umkm)


if __name__ == '__main__':
    main()
