"""
sync_csv_ke_gsheet.py
==================================================
Script untuk upload data CSV UMKM Kendari ke Google Sheets
agar bisa dipakai chatbot n8n secara real-time.

CARA PAKAI:
==================================================
LANGKAH 1 — Install library:
  pip install gspread google-auth

LANGKAH 2 — Buat Google Service Account:
  a. Buka: https://console.cloud.google.com/
  b. Buat project baru (atau pilih yang sudah ada)
  c. Aktifkan "Google Sheets API":
     - Klik "APIs & Services" → "Library"
     - Cari "Google Sheets API" → Klik Enable
  d. Buat Service Account:
     - "IAM & Admin" → "Service Accounts" → "Create Service Account"
     - Beri nama: umkm-kendari-bot
     - Klik "Done"
  e. Buat Key (JSON):
     - Klik service account yang dibuat → Tab "Keys"
     - "Add Key" → "Create new key" → Pilih JSON → Download
     - Simpan file JSON sebagai: credentials.json
     - Letakkan di folder yang sama dengan script ini

LANGKAH 3 — Share Google Sheet ke Service Account:
  a. Buka credentials.json → cari "client_email"
  b. Copy email tersebut (contoh: umkm-kendari-bot@project.iam.gserviceaccount.com)
  c. Buka Google Sheet kamu
  d. Klik "Bagikan" (Share) → Paste email service account → Beri akses "Editor"

LANGKAH 4 — Jalankan script:
  python sync_csv_ke_gsheet.py

LANGKAH 5 — Setup n8n untuk auto-sync:
  Di n8n, tambahkan "Schedule Trigger" → jalankan tiap 1 jam
  → HTTP Request ke: http://localhost:5000/n8n/sync-trigger?api_key=umkm-kendari-secret-2024
==================================================
"""

import csv
import os
import sys
import io
from datetime import datetime

# Fix encoding Windows (agar emoji & karakter Unicode bisa tampil)
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ============================================================
# CONFIG — SUDAH DISESUAIKAN DENGAN SHEET KAMU
# ============================================================
CSV_FILE = os.path.join(os.path.dirname(__file__), 'data_umkm_diratakan_produk_harga.csv')
# Cari file service account (cek beberapa nama umum)
_base = os.path.dirname(__file__)
CREDENTIALS_FILE = next(
    (os.path.join(_base, f) for f in
     ['service_account.json', 'credentials.json', 'gsheet_credentials.json']
     if os.path.exists(os.path.join(_base, f))),
    os.path.join(_base, 'service_account.json')  # default jika tidak ada
)

# ID Google Sheet (dari URL)
SPREADSHEET_ID = '1nvjBhXEUdiWXNEAay6u1iQc9DkZCDyLKUPTLSbbUKvA'

# Nama sheet tab
SHEET_NAME = 'Sheet1'  # Ganti jika tab sheet kamu berbeda
# ============================================================


def baca_csv():
    """Baca data dari file CSV UMKM."""
    if not os.path.exists(CSV_FILE):
        print(f"❌ File CSV tidak ditemukan: {CSV_FILE}")
        sys.exit(1)
    
    rows = []
    with open(CSV_FILE, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            # Skip baris kosong
            if not any(row.values()):
                continue
            rows.append(row)
    
    print(f"✅ {len(rows)} data UMKM berhasil dibaca dari CSV")
    return rows


def format_untuk_gsheet(rows):
    """Format data CSV untuk Google Sheets."""
    
    # Header baru yang lebih rapi untuk n8n chatbot
    header = [
        'No',
        'Kecamatan',
        'Kelurahan', 
        'Nama UMKM',
        'Kategori',
        'Nama Produk',
        'Harga',
        'Status Harga',
        'Status Verifikasi',
        'Alamat',
        'Catatan',
        'URL Sumber',
        'Update Terakhir'
    ]
    
    data_rows = [header]
    
    for i, row in enumerate(rows, 1):
        data_rows.append([
            row.get('No', str(i)),
            row.get('Kecamatan', ''),
            row.get('Kelurahan', ''),
            row.get('Nama UMKM', ''),
            row.get('Kategori', ''),
            row.get('Nama Produk', ''),
            row.get('Harga', ''),
            row.get('Status Harga', ''),
            row.get('Status Verifikasi', ''),
            row.get('Alamat pada Data', ''),
            row.get('Catatan', ''),
            row.get('URL Sumber', ''),
            datetime.now().strftime('%Y-%m-%d %H:%M')
        ])
    
    return data_rows


def upload_ke_gsheet(data_rows):
    """Upload data ke Google Sheets."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        print("\n❌ Library belum terinstall!")
        print("   Jalankan: pip install gspread google-auth")
        sys.exit(1)

    if not os.path.exists(CREDENTIALS_FILE):
        print(f"\n❌ File Service Account JSON tidak ditemukan!")
        print(f"   Dicari di: {os.path.dirname(__file__)}")
        print(f"   Nama yang dicari: service_account.json / credentials.json")
        print("""
   ⚠️  PENTING: credential.json yang kamu punya adalah OAuth2 (untuk n8n).
               Yang dibutuhkan di sini adalah SERVICE ACCOUNT JSON.

   CARA MEMBUAT service_account.json:
   1. Buka: https://console.cloud.google.com/iam-admin/serviceaccounts?project=n8n-chatbot-498311
   2. Klik "+ Create Service Account"
   3. Nama: umkm-sheet-sync → Klik Done
   4. Klik service account → Tab Keys → Add Key → Create new key → JSON
   5. Rename file download menjadi: service_account.json
   6. Letakkan di folder: """ + os.path.dirname(__file__))
        sys.exit(1)
    
    # Cek apakah file yang ada adalah OAuth2 (salah jenis)
    import json as _json
    with open(CREDENTIALS_FILE) as _f:
        _cred_data = _json.load(_f)
    if 'web' in _cred_data or 'installed' in _cred_data:
        print(f"\n❌ File {os.path.basename(CREDENTIALS_FILE)} adalah OAuth2 credential — bukan Service Account!")
        print("   OAuth2 dipakai untuk n8n, tapi script ini butuh Service Account JSON.")
        print("   Buat Service Account baru di project n8n-chatbot-498311 seperti panduan di atas.")
        sys.exit(1)

    print("\n🔗 Menghubungkan ke Google Sheets...")
    
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    try:
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
        client = gspread.authorize(creds)
    except Exception as e:
        print(f"❌ Gagal autentikasi: {e}")
        sys.exit(1)

    # Buka spreadsheet
    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        print(f"✅ Terhubung ke Google Sheet: {spreadsheet.title}")
    except Exception as e:
        print(f"❌ Gagal membuka Google Sheet: {e}")
        print("""
   Kemungkinan masalah:
   1. Sheet belum di-share ke email service account
   2. SPREADSHEET_ID salah
   
   Cara share:
   - Buka Google Sheet → Klik "Bagikan"
   - Tambahkan email dari credentials.json (field "client_email")
   - Beri akses "Editor"
        """)
        sys.exit(1)

    # Cari atau buat worksheet
    try:
        worksheet = spreadsheet.worksheet(SHEET_NAME)
        print(f"✅ Sheet '{SHEET_NAME}' ditemukan")
        worksheet.clear()
        print("   Data lama dihapus")
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows=500, cols=15)
        print(f"✅ Sheet baru '{SHEET_NAME}' dibuat")

    # Upload data
    print(f"\n📤 Mengupload {len(data_rows) - 1} data UMKM...")
    
    try:
        worksheet.update(data_rows, value_input_option='USER_ENTERED')
    except Exception as e:
        print(f"❌ Gagal upload: {e}")
        sys.exit(1)

    # Format header (bold, background biru)
    try:
        worksheet.format('A1:M1', {
            'backgroundColor': {'red': 0.13, 'green': 0.45, 'blue': 0.78},
            'textFormat': {
                'bold': True,
                'foregroundColor': {'red': 1, 'green': 1, 'blue': 1},
                'fontSize': 11
            },
            'horizontalAlignment': 'CENTER',
            'verticalAlignment': 'MIDDLE'
        })
        
        # Freeze baris header
        spreadsheet.batch_update({
            'requests': [{
                'updateSheetProperties': {
                    'properties': {
                        'sheetId': worksheet.id,
                        'gridProperties': {'frozenRowCount': 1}
                    },
                    'fields': 'gridProperties.frozenRowCount'
                }
            }]
        })
        print("✅ Header diformat (biru, bold, frozen)")
    except Exception as e:
        print(f"⚠️  Format gagal (data tetap terupload): {e}")

    waktu = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    total = len(data_rows) - 1
    
    print(f"""
╔══════════════════════════════════════════════╗
║          ✅ SINKRONISASI BERHASIL!           ║
╠══════════════════════════════════════════════╣
║  📊 Total data    : {total} UMKM{' ' * (23 - len(str(total)))}║
║  📋 Sheet         : {SHEET_NAME[:20]}{' ' * (23 - len(SHEET_NAME[:20]))}║
║  🕐 Waktu         : {waktu[:19]}{' ' * (23 - 19)}║
╚══════════════════════════════════════════════╝

🔗 Buka Sheet:
   https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit

📌 LANGKAH SELANJUTNYA — Setup n8n:
   1. Di n8n, tambahkan node "Google Sheets"
   2. Pilih spreadsheet ID: {SPREADSHEET_ID}
   3. Sheet name: {SHEET_NAME}
   4. Operasi: "Read Rows" untuk dibaca chatbot
   5. Tambahkan Schedule Trigger untuk auto-sync tiap 1 jam
    """)


def main():
    print("=" * 50)
    print("  Sync Data UMKM Kendari → Google Sheets")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # Baca CSV
    print("\n📂 Membaca file CSV...")
    rows = baca_csv()
    
    if not rows:
        print("⚠️  Tidak ada data di CSV!")
        sys.exit(0)
    
    # Format data
    data_rows = format_untuk_gsheet(rows)
    
    # Preview 3 baris pertama
    print("\n📋 Preview data (3 baris pertama):")
    for r in data_rows[:4]:
        print(f"   {r[:5]}")  # Tampilkan 5 kolom pertama
    
    # Upload
    upload_ke_gsheet(data_rows)


if __name__ == '__main__':
    main()
