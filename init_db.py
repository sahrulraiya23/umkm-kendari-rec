"""
Script untuk inisialisasi database dan menambahkan seed data
produk UMKM Kota Kendari.
"""

import sqlite3
import os
import sys

# Tambahkan project root ke path
sys.path.insert(0, os.path.dirname(__file__))

from config import DATABASE
from models.database import init_db
from werkzeug.security import generate_password_hash


def seed_data():
    """Menambahkan data awal (dummy) ke database."""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")

    # ========== USERS ==========
    users = [
        ('admin', 'admin@umkmkendari.id', generate_password_hash('admin123'), 'admin', 'Administrator', 'Kendari, Sultra', '08110001111'),
        ('toko_sarung', 'sarung@umkm.id', generate_password_hash('seller123'), 'seller', 'Toko Sarung Tenun Kendari', 'Jl. Mayjen Sutoyo, Kendari', '08221112222'),
        ('toko_kain', 'kain@umkm.id', generate_password_hash('seller123'), 'seller', 'Kain Tenun Tolaki', 'Jl. S. Parman, Kendari', '08221113333'),
        ('toko_rempah', 'rempah@umkm.id', generate_password_hash('seller123'), 'seller', 'Rempah Nusantara Kendari', 'Pasar Sentral Kendari', '08221114444'),
        ('toko_kerajinan', 'kerajinan@umkm.id', generate_password_hash('seller123'), 'seller', 'Kerajinan Tangan Sultra', 'Jl. Haluoleo, Kendari', '08221115555'),
        ('toko_kuliner', 'kuliner@umkm.id', generate_password_hash('seller123'), 'seller', 'Kuliner Khas Kendari', 'Jl. A. Yani, Kendari', '08221116666'),
        ('toko_jasa', 'jasa@umkm.id', generate_password_hash('seller123'), 'seller', 'Jasa Kreatif Kendari', 'Jl. MT Haryono, Kendari', '08221117777'),
        ('toko_digital', 'digital@umkm.id', generate_password_hash('seller123'), 'seller', 'Digital Hub Kendari', 'Jl. Piere Tendean, Kendari', '08221118888'),
        ('toko_kesehatan', 'kesehatan@umkm.id', generate_password_hash('seller123'), 'seller', 'Herbal Sehat Kendari', 'Jl. DI Panjaitan, Kendari', '08221119999'),
        ('pembeli1', 'buyer1@mail.com', generate_password_hash('buyer123'), 'buyer', 'Ahmad Saputra', 'Kendari Barat', '08331112222'),
        ('pembeli2', 'buyer2@mail.com', generate_password_hash('buyer123'), 'buyer', 'Siti Nurhaliza', 'Mandonga, Kendari', '08331113333'),
        ('pembeli3', 'buyer3@mail.com', generate_password_hash('buyer123'), 'buyer', 'Budi Santoso', 'Kambu, Kendari', '08331114444'),
        ('pembeli4', 'buyer4@mail.com', generate_password_hash('buyer123'), 'buyer', 'Dewi Lestari', 'Poasia, Kendari', '08331115555'),
        ('pembeli5', 'buyer5@mail.com', generate_password_hash('buyer123'), 'buyer', 'Rizky Pratama', 'Baruga, Kendari', '08331116666'),
    ]

    for u in users:
        try:
            db.execute('INSERT INTO users (username, email, password_hash, role, nama_lengkap, alamat, no_telepon) VALUES (?,?,?,?,?,?,?)', u)
        except sqlite3.IntegrityError:
            pass

    db.commit()

    # ========== KATEGORI ==========
    kategori = [
        ('Kuliner', 'Makanan, minuman, dan produk kuliner khas Kendari & Sulawesi Tenggara', 'bi-cup-hot'),
        ('Fashion', 'Pakaian, kain tenun, aksesoris, dan busana khas daerah', 'bi-bag'),
        ('Kriya', 'Kerajinan tangan, anyaman, ukiran, dan produk kreatif lokal', 'bi-hammer'),
        ('Jasa', 'Layanan jasa seperti fotografi, catering, jahit, dan lainnya', 'bi-briefcase'),
        ('Retail', 'Produk retail, oleh-oleh, souvenir, dan kebutuhan sehari-hari', 'bi-shop'),
        ('Agro', 'Hasil pertanian, perkebunan, perikanan, dan rempah-rempah lokal', 'bi-tree'),
        ('Digital', 'Produk dan layanan digital seperti desain grafis, website, dan aplikasi', 'bi-laptop'),
        ('Kesehatan', 'Produk herbal, jamu, kosmetik alami, dan perawatan kesehatan', 'bi-heart-pulse'),
    ]

    for k in kategori:
        try:
            db.execute('INSERT INTO kategori (nama, deskripsi, icon) VALUES (?,?,?)', k)
        except sqlite3.IntegrityError:
            pass

    db.commit()

    # Ambil ID
    user_rows = db.execute('SELECT id, username FROM users WHERE role = "seller"').fetchall()
    kat_rows = db.execute('SELECT id, nama FROM kategori').fetchall()

    seller_map = {row['username']: row['id'] for row in user_rows}
    kat_map = {row['nama']: row['id'] for row in kat_rows}

    # ========== PRODUK ==========
    produk = [
        # --- Kuliner ---
        ('Kasoami (Sagu Bakar)', 'Makanan khas Kendari berbahan sagu, dipanggang hingga kecoklatan. Tekstur renyah di luar, lembut di dalam.', 25000, 50, 'default.jpg', kat_map['Kuliner'], seller_map['toko_kuliner'], 'Kendari'),
        ('Sinonggi', 'Makanan tradisional Sultra dari tepung sagu yang dimasak dengan air panas hingga mengental. Disajikan dengan ikan kuah kuning.', 30000, 40, 'default.jpg', kat_map['Kuliner'], seller_map['toko_kuliner'], 'Wua-Wua'),
        ('Lapa-Lapa', 'Ketupat khas Kendari yang dibungkus daun kelapa muda, berisi beras yang dimasak dengan santan.', 15000, 100, 'default.jpg', kat_map['Kuliner'], seller_map['toko_kuliner'], 'Mandonga'),
        ('Kopi Kolaka Premium', 'Kopi arabika asli Kolaka, Sulawesi Tenggara. Aroma khas dan rasa yang bold.', 75000, 30, 'default.jpg', kat_map['Kuliner'], seller_map['toko_kuliner'], 'Poasia'),
        ('Sambal Ikan Tore', 'Sambal khas Kendari dengan ikan kering yang diolah tradisional. Pedas dan gurih.', 35000, 60, 'default.jpg', kat_map['Kuliner'], seller_map['toko_kuliner'], 'Puuwatu'),

        # --- Fashion ---
        ('Sarung Tenun Kendari', 'Sarung tenun tradisional khas Kendari dengan motif Tolaki. Dibuat secara handmade.', 350000, 15, 'default.jpg', kat_map['Fashion'], seller_map['toko_sarung'], 'Kendari Barat'),
        ('Kain Tenun Tolaki', 'Kain tenun khas suku Tolaki dengan motif geometris tradisional. Material katun premium.', 450000, 10, 'default.jpg', kat_map['Fashion'], seller_map['toko_kain'], 'Baruga'),
        ('Kain Tenun Muna', 'Kain tenun tradisional suku Muna, Sultra. Motif unik warisan budaya.', 400000, 12, 'default.jpg', kat_map['Fashion'], seller_map['toko_kain'], 'Abeli'),
        ('Baju Adat Tolaki', 'Busana adat suku Tolaki untuk acara pernikahan dan upacara adat.', 850000, 5, 'default.jpg', kat_map['Fashion'], seller_map['toko_kain'], 'Kambu'),
        ('Topi Anyaman Pandan', 'Topi anyaman dari daun pandan khas Sultra. Cocok untuk aksesoris fashion etnik.', 85000, 30, 'default.jpg', kat_map['Fashion'], seller_map['toko_sarung'], 'Nambo'),

        # --- Kriya ---
        ('Anyaman Rotan Kendari', 'Keranjang anyaman rotan khas Kendari. Handmade oleh pengrajin lokal.', 175000, 20, 'default.jpg', kat_map['Kriya'], seller_map['toko_kerajinan'], 'Kendari'),
        ('Gelang Perak Tolaki', 'Gelang perak dengan ukiran motif Tolaki. Perhiasan tradisional Sultra.', 250000, 15, 'default.jpg', kat_map['Kriya'], seller_map['toko_kerajinan'], 'Wua-Wua'),
        ('Miniatur Rumah Adat Tolaki', 'Miniatur rumah adat suku Tolaki dari kayu jati. Souvenir premium.', 200000, 10, 'default.jpg', kat_map['Kriya'], seller_map['toko_kerajinan'], 'Mandonga'),
        ('Tas Anyaman Purun', 'Tas dari anyaman purun (rumput laut kering). Ramah lingkungan dan unik.', 150000, 25, 'default.jpg', kat_map['Kriya'], seller_map['toko_kerajinan'], 'Poasia'),
        ('Ukiran Kayu Kendari', 'Ukiran kayu dekoratif dengan motif khas Sulawesi Tenggara.', 300000, 8, 'default.jpg', kat_map['Kriya'], seller_map['toko_kerajinan'], 'Puuwatu'),

        # --- Jasa ---
        ('Jasa Fotografi Produk UMKM', 'Layanan foto produk profesional untuk pelaku UMKM Kendari. Termasuk editing.', 250000, 99, 'default.jpg', kat_map['Jasa'], seller_map['toko_jasa'], 'Kendari'),
        ('Jasa Catering Masakan Kendari', 'Layanan catering masakan khas Sultra untuk acara dan kantor. Minimal 20 porsi.', 500000, 99, 'default.jpg', kat_map['Jasa'], seller_map['toko_jasa'], 'Mandonga'),
        ('Jasa Jahit & Bordir Sultra', 'Layanan menjahit dan bordir motif khas Sulawesi Tenggara. Custom order.', 200000, 99, 'default.jpg', kat_map['Jasa'], seller_map['toko_jasa'], 'Wua-Wua'),

        # --- Retail ---
        ('Kaos Oleh-oleh Kendari', 'Kaos dengan desain khas Kota Kendari. Bahan cotton combed 30s.', 85000, 50, 'default.jpg', kat_map['Retail'], seller_map['toko_sarung'], 'Kendari'),
        ('Gantungan Kunci Kendari', 'Gantungan kunci miniatur landmark Kendari. Souvenir murah meriah.', 15000, 100, 'default.jpg', kat_map['Retail'], seller_map['toko_kerajinan'], 'Nambo'),
        ('Magnet Kulkas Kendari', 'Magnet kulkas dengan gambar landmark dan budaya Kendari.', 20000, 80, 'default.jpg', kat_map['Retail'], seller_map['toko_kerajinan'], 'Wua-Wua'),
        ('Madu Hutan Konawe', 'Madu murni dari hutan Konawe, Sulawesi Tenggara. Tanpa bahan pengawet.', 120000, 20, 'default.jpg', kat_map['Retail'], seller_map['toko_rempah'], 'Kadia'),

        # --- Agro ---
        ('Lada Hitam Kolaka', 'Lada hitam premium dari Kolaka, Sulawesi Tenggara. Aroma kuat dan rasa pedas khas.', 55000, 40, 'default.jpg', kat_map['Agro'], seller_map['toko_rempah'], 'Kadia'),
        ('Kunyit Bubuk Organik', 'Kunyit bubuk organik dari petani lokal Kendari. Tanpa campuran kimia.', 35000, 50, 'default.jpg', kat_map['Agro'], seller_map['toko_rempah'], 'Kendari Barat'),
        ('Bumbu Rendang Khas Kendari', 'Bumbu rendang racikan khas Kendari. Siap pakai untuk 1kg daging.', 40000, 35, 'default.jpg', kat_map['Agro'], seller_map['toko_rempah'], 'Baruga'),
        ('Garam Laut Kendari', 'Garam laut alami dari pesisir Kendari. Kaya mineral dan tanpa pemutih.', 25000, 60, 'default.jpg', kat_map['Agro'], seller_map['toko_rempah'], 'Abeli'),
        ('Beras Merah Organik Konawe', 'Beras merah organik dari Konawe. Kaya serat dan nutrisi.', 45000, 35, 'default.jpg', kat_map['Agro'], seller_map['toko_rempah'], 'Baruga'),

        # --- Digital ---
        ('Jasa Desain Logo UMKM', 'Layanan desain logo profesional untuk branding UMKM. Revisi hingga puas.', 300000, 99, 'default.jpg', kat_map['Digital'], seller_map['toko_digital'], 'Kendari'),
        ('Paket Website Toko Online', 'Pembuatan website toko online responsive untuk UMKM. Termasuk hosting 1 tahun.', 1500000, 99, 'default.jpg', kat_map['Digital'], seller_map['toko_digital'], 'Mandonga'),
        ('Jasa Digital Marketing UMKM', 'Layanan promosi digital di media sosial untuk produk UMKM Kendari.', 500000, 99, 'default.jpg', kat_map['Digital'], seller_map['toko_digital'], 'Poasia'),

        # --- Kesehatan ---
        ('Jahe Merah Bubuk', 'Jahe merah bubuk organik. Cocok untuk minuman herbal.', 45000, 45, 'default.jpg', kat_map['Kesehatan'], seller_map['toko_kesehatan'], 'Kambu'),
        ('Jahe Merah Bubuk Organik', 'Jahe merah bubuk organik dari Kendari. Cocok untuk minuman herbal penghangat tubuh.', 45000, 45, 'default.jpg', kat_map['Kesehatan'], seller_map['toko_kesehatan'], 'Kambu'),
        ('Minyak Kelapa Murni (VCO)', 'Virgin Coconut Oil dari kelapa segar Sultra. Untuk kesehatan dan perawatan kulit.', 65000, 30, 'default.jpg', kat_map['Kesehatan'], seller_map['toko_kesehatan'], 'Abeli'),
        ('Jamu Tradisional Sultra', 'Ramuan jamu tradisional khas Sulawesi Tenggara. Berbahan herbal alami.', 35000, 40, 'default.jpg', kat_map['Kesehatan'], seller_map['toko_kesehatan'], 'Kendari Barat'),
        ('Lulur Herbal Kendari', 'Lulur tradisional dari bahan herbal lokal Kendari. Menghaluskan dan mencerahkan kulit.', 55000, 25, 'default.jpg', kat_map['Kesehatan'], seller_map['toko_kesehatan'], 'Baruga'),
    ]

    for p in produk:
        try:
            db.execute('INSERT INTO produk (nama, deskripsi, harga, stok, gambar, kategori_id, seller_id, kecamatan) VALUES (?,?,?,?,?,?,?,?)', p)
        except sqlite3.IntegrityError:
            pass

    db.commit()

    # ========== RATINGS ==========
    buyer_rows = db.execute('SELECT id FROM users WHERE role = "buyer"').fetchall()
    produk_rows = db.execute('SELECT id FROM produk').fetchall()

    buyer_ids = [r['id'] for r in buyer_rows]
    produk_ids = [r['id'] for r in produk_rows]

    import random
    random.seed(42)

    ratings = []
    for buyer_id in buyer_ids:
        # Setiap buyer beri rating 5-10 produk random
        n_ratings = random.randint(5, min(10, len(produk_ids)))
        rated_products = random.sample(produk_ids, n_ratings)
        for pid in rated_products:
            score = random.choices([3, 4, 5, 2, 1], weights=[30, 35, 20, 10, 5])[0]
            reviews = [
                'Produk bagus, recommended!',
                'Kualitas oke, sesuai harga.',
                'Sangat memuaskan, akan beli lagi.',
                'Lumayan, cukup baik.',
                'Biasa saja.',
                'Pengiriman cepat, barang sesuai.',
                'Produk asli UMKM Kendari, keren!',
                'Worth it banget!',
                '',
            ]
            review = random.choice(reviews)
            ratings.append((buyer_id, pid, score, review))

    for r in ratings:
        try:
            db.execute('INSERT INTO ratings (user_id, produk_id, score, review) VALUES (?,?,?,?)', r)
        except sqlite3.IntegrityError:
            pass

    db.commit()
    db.close()

    print(f"Seed data berhasil ditambahkan!")
    print(f"  - {len(users)} users (1 admin, 8 sellers, 5 buyers)")
    print(f"  - {len(kategori)} kategori")
    print(f"  - {len(produk)} produk UMKM Kendari")
    print(f"  - {len(ratings)} ratings")
    print(f"\nAkun login:")
    print(f"  Admin  : admin / admin123")
    print(f"  Seller : toko_sarung / seller123")
    print(f"  Buyer  : pembeli1 / buyer123")


if __name__ == '__main__':
    print("Inisialisasi database...")
    init_db()
    print("\nMenambahkan seed data...")
    seed_data()
    print("\nSelesai! Jalankan `python app.py` untuk memulai server.")
