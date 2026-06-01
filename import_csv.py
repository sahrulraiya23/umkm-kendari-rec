import csv
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "umkm_kendari.db")
CSV_PATH = os.path.join(BASE_DIR, "data_umkm_diratakan_produk_harga.csv")

category_seller_usernames = {
    'Kuliner': 'toko_kuliner',
    'Fashion': 'toko_sarung',
    'Kriya': 'toko_kerajinan',
    'Jasa': 'toko_jasa',
    'Retail': 'toko_sarung',
    'Agro': 'toko_rempah',
    'Digital': 'toko_digital',
    'Kesehatan': 'toko_kesehatan'
}

def clean_price(price_str):
    """
    Cleans price string (e.g. 'Rp 18.000' -> 18000.0, 'Rp 7.000/kg' -> 7000.0)
    """
    price_str = price_str.replace('Rp', '').replace('.', '').strip()
    if '/' in price_str:
        price_str = price_str.split('/')[0].strip()
    try:
        return float(price_str)
    except:
        return 50000.0  # fallback

def import_data():
    if not os.path.exists(DATABASE_PATH):
        print(f"Error: Database {DATABASE_PATH} not found.")
        return

    print("Connecting to database...")
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Get categories mapping: name -> id
    categories = c.execute("SELECT id, nama FROM kategori").fetchall()
    cat_map = {row['nama'].lower(): row['id'] for row in categories}

    # Get sellers mapping: username -> id
    sellers = c.execute("SELECT id, username FROM users WHERE role = 'seller'").fetchall()
    seller_map = {row['username']: row['id'] for row in sellers}

    print(f"Parsing CSV from {CSV_PATH}...")
    inserted_count = 0
    skipped_count = 0

    with open(CSV_PATH, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=';')
        
        # Read header:
        # No;Kecamatan;Kelurahan;Nama UMKM;Kategori;Nama Produk;Harga;Status Harga;Sumber Verifikasi;Status Verifikasi;Alamat pada Data;Catatan;URL Sumber;No Sumber;Baris Sumber CSV
        header = next(reader)
        
        for row in reader:
            if not row or len(row) < 12 or row[0].strip() == '':
                continue
            
            kecamatan_col = row[1].strip()
            kelurahan_col = row[2].strip()
            nama_umkm = row[3].strip()
            kategori_col = row[4].strip()
            nama_produk = row[5].strip()
            harga_col = row[6].strip()
            alamat = row[10].strip()
            catatan = row[11].strip()
            
            # Map Kecamatan
            if kelurahan_col.lower() == 'nambo':
                kecamatan = 'Nambo'
            else:
                kecamatan = kecamatan_col
                
            # Construct product name
            if nama_produk and nama_umkm:
                nama = f"{nama_produk} - {nama_umkm}"
            elif nama_umkm:
                nama = nama_umkm
            else:
                nama = nama_produk

            # Clean price
            harga = clean_price(harga_col)
            
            # Get category id
            kategori_id = cat_map.get(kategori_col.lower())
            if not kategori_id:
                # Default fallback
                kategori_id = list(cat_map.values())[0]
                
            # Get seller id
            seller_username = category_seller_usernames.get(kategori_col, 'toko_sarung')
            seller_id = seller_map.get(seller_username)
            if not seller_id:
                seller_id = list(seller_map.values())[0]

            # Construct description
            desc = catatan if catatan else f"Produk dari {nama_umkm} di {kecamatan}"
            if alamat:
                desc += f" (Alamat: {alamat})"

            # Check if exists
            exists = c.execute("SELECT id FROM produk WHERE nama = ? AND kecamatan = ?", (nama, kecamatan)).fetchone()
            if exists:
                skipped_count += 1
                continue

            # Insert product
            c.execute(
                "INSERT INTO produk (nama, deskripsi, harga, stok, gambar, kategori_id, seller_id, kecamatan, tersedia) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (nama, desc, harga, 50, 'default.jpg', kategori_id, seller_id, kecamatan, 1)
            )
            inserted_count += 1

    # Insert Nambo dummy products to ensure district 11 is fully represented in the system
    nambo_dummies = [
        ("Kasoami Nambo", "Kasoami khas Nambo, lezat dan gurih, dibuat tradisional.", 20000, "Kuliner", "toko_kuliner"),
        ("Batik Nambo", "Batik motif khas daerah Nambo, bahan katun premium.", 180000, "Fashion", "toko_sarung"),
        ("Kerajinan Kerang Nambo", "Hiasan dan kerajinan cantik dari kulit kerang khas Pantai Nambo.", 75000, "Kriya", "toko_kerajinan"),
        ("Jasa Wisata Pantai Nambo", "Pemandu wisata profesional dan sewa gazebo di Pantai Nambo Kendari.", 100000, "Jasa", "toko_jasa"),
        ("Minyak Kelapa Nambo", "Minyak kelapa murni (VCO) buatan home industri Nambo, kaya manfaat.", 50000, "Kesehatan", "toko_kesehatan"),
    ]

    nambo_inserted = 0
    for name, desc, price, cat_name, seller_username in nambo_dummies:
        # Check if exists
        exists = c.execute("SELECT id FROM produk WHERE nama = ? AND kecamatan = ?", (name, "Nambo")).fetchone()
        if exists:
            continue
            
        kategori_id = cat_map.get(cat_name.lower())
        seller_id = seller_map.get(seller_username)
        
        c.execute(
            "INSERT INTO produk (nama, deskripsi, harga, stok, gambar, kategori_id, seller_id, kecamatan, tersedia) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (name, desc, price, 50, 'default.jpg', kategori_id, seller_id, "Nambo", 1)
        )
        nambo_inserted += 1
        inserted_count += 1

    conn.commit()
    conn.close()

    print("Import process completed!")
    print(f"  - Successfully imported products: {inserted_count} (including {nambo_inserted} Nambo dummies)")
    print(f"  - Skipped (already exists): {skipped_count}")

if __name__ == "__main__":
    import_data()
