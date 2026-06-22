import csv
import sqlite3
import os
import re
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "umkm_kendari.db")
CSV_PATH = os.path.join(BASE_DIR, "Data umkmmmm - Sheet1 (1).csv")

def get_safe_username(name):
    # Remove non-alphanumeric, replace spaces with underscores
    safe_name = re.sub(r'[^a-zA-Z0-9]', '', name.replace(' ', '_')).lower()
    return f"{safe_name}"

def clean_price(price_str):
    try:
        # Some prices might be just digits, some might have commas or dots
        price_str = price_str.replace('Rp', '').replace('.', '').replace(',', '').strip()
        if '/' in price_str:
            price_str = price_str.split('/')[0].strip()
        return float(price_str)
    except:
        return 0.0

def main():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Get categories
    categories = c.execute("SELECT id, nama FROM kategori").fetchall()
    cat_map = {row['nama'].lower(): row['id'] for row in categories}

    inserted_umkm = 0
    inserted_produk = 0

    with open(CSV_PATH, mode="r", encoding="utf-8-sig") as f:
        # Note: the file might have BOM so utf-8-sig is safer
        reader = csv.DictReader(f, delimiter=',')
        for row in reader:
            nama_umkm = row.get('nama umkm', '').strip()
            no_telpon = row.get('no telpon', '').strip()
            alamat = row.get('alamat', '').strip()
            produk = row.get('produk', '').strip()
            harga_raw = row.get('harga', '').strip()
            kategori = row.get('kategori', '').strip()
            kecamatan = row.get('kecamatan', '').strip()

            if not nama_umkm or not produk:
                continue

            username = get_safe_username(nama_umkm)
            email = f"{username}@umkm.id"

            # Check if UMKM (seller) exists
            seller = c.execute("SELECT id FROM users WHERE role = 'seller' AND (username = ? OR nama_lengkap = ?)", (username, nama_umkm)).fetchone()
            if not seller:
                c.execute(
                    "INSERT INTO users (username, email, password_hash, role, nama_lengkap, alamat, no_telepon) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (username, email, generate_password_hash('seller123'), 'seller', nama_umkm, alamat, no_telpon)
                )
                seller_id = c.lastrowid
                
                # Add operasional
                schedule = [
                    (0, 'Senin', '08:00', '17:00', 1),
                    (1, 'Selasa', '08:00', '17:00', 1),
                    (2, 'Rabu', '08:00', '17:00', 1),
                    (3, 'Kamis', '08:00', '17:00', 1),
                    (4, 'Jumat', '08:00', '17:00', 1),
                    (5, 'Sabtu', '08:00', '17:00', 1),
                    (6, 'Minggu', '08:00', '17:00', 0),
                ]
                seller_schedule = [(seller_id, s[0], s[1], s[2], s[3], s[4]) for s in schedule]
                c.executemany(
                    "INSERT OR IGNORE INTO seller_operasional (seller_id, hari_index, hari_nama, buka_jam, tutup_jam, is_open) VALUES (?, ?, ?, ?, ?, ?)",
                    seller_schedule
                )
                inserted_umkm += 1
            else:
                seller_id = seller['id']

            # Process Category
            kategori_lower = kategori.lower()
            kategori_id = cat_map.get(kategori_lower)
            if not kategori_id:
                if 'kuliner' in kategori_lower or 'uliner' in kategori_lower:
                    kategori_id = cat_map.get('kuliner')
                elif 'ritel' in kategori_lower:
                    kategori_id = cat_map.get('retail')
                else:
                    kategori_id = list(cat_map.values())[0] if cat_map else None

            # Check if product exists
            prod = c.execute("SELECT id FROM produk WHERE nama = ? AND seller_id = ?", (produk, seller_id)).fetchone()
            if not prod:
                harga = clean_price(harga_raw)
                c.execute(
                    "INSERT INTO produk (nama, deskripsi, harga, stok, gambar, kategori_id, seller_id, kecamatan, tersedia) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (produk, f"Produk dari {nama_umkm}", harga, 50, '', kategori_id, seller_id, kecamatan, 1)
                )
                inserted_produk += 1

    conn.commit()
    conn.close()
    print(f"Data import completed. Inserted {inserted_umkm} new UMKM(s) and {inserted_produk} new Product(s).")

if __name__ == '__main__':
    main()
