# -*- coding: utf-8 -*-
"""
Script Reset + Seed User dengan Rating BERVARIASI
===========================================
Agar segmen evaluasi terisi semua:
  - Segmen 1-4 Rating  : rezky, noval, usrianto, raihan  (3 rating)
  - Segmen 5-10 Rating : iqbal, wahyu, rian, apri         (8 rating)
  - Segmen >10 Rating  : dany, alfin, aril, andi           (14 rating)
"""

import sys, os, random, sqlite3
sys.path.insert(0, os.path.dirname(__file__))
from werkzeug.security import generate_password_hash
from config import DATABASE
from collections import defaultdict

random.seed(77)

db = sqlite3.connect(DATABASE)
db.row_factory = sqlite3.Row
db.execute("PRAGMA foreign_keys = ON")

# ============================================================
# STEP 1: Hapus semua ratings dan buyer lama
# ============================================================
db.execute("DELETE FROM ratings")
db.execute("DELETE FROM users WHERE role = 'buyer'")
db.commit()
print("[1] Rating dan buyer lama dihapus.")

# ============================================================
# STEP 2: Buat 12 buyer baru dengan jumlah rating bervariasi
# (username, email, nama_lengkap, n_ratings, [kategori_fav])
# ============================================================
new_buyers_cfg = [
    # Segmen 1-4 Rating (cold-start)
    ('rezky',    'rezky@mail.com',    'Rezky Ramadhan',   3, ['Kuliner', 'Agro']),
    ('noval',    'noval@mail.com',    'Noval Hidayat',    4, ['Fashion', 'Kriya']),
    ('usrianto', 'usrianto@mail.com', 'Usrianto Putra',   3, ['Digital', 'Jasa']),
    ('raihan',   'raihan@mail.com',   'Raihan Akbar',     4, ['Kuliner', 'Retail']),
    # Segmen 5-10 Rating
    ('iqbal',    'iqbal@mail.com',    'Iqbal Fauzi',      8, ['Kriya', 'Fashion', 'Kesehatan']),
    ('wahyu',    'wahyu@mail.com',    'Wahyu Pratama',    7, ['Agro', 'Kuliner', 'Retail']),
    ('rian',     'rian@mail.com',     'Rian Saputra',     9, ['Jasa', 'Digital', 'Kriya']),
    ('apri',     'apri@mail.com',     'Apri Yanto',       8, ['Kesehatan', 'Agro', 'Kuliner']),
    # Segmen >10 Rating
    ('dany',     'dany@mail.com',     'Dany Kurniawan',  14, ['Fashion', 'Retail', 'Kriya']),
    ('alfin',    'alfin@mail.com',    'Alfin Maulana',   13, ['Digital', 'Jasa', 'Fashion']),
    ('aril',     'aril@mail.com',     'Aril Hendra',     14, ['Kuliner', 'Kriya', 'Agro']),
    ('andi',     'andi@mail.com',     'Andi Syahputra',  15, ['Retail', 'Kesehatan', 'Fashion']),
]

pw_hash = generate_password_hash('buyer123')
inserted_users = []
for username, email, nama, n_ratings, prefs in new_buyers_cfg:
    try:
        cur = db.execute(
            'INSERT INTO users (username, email, password_hash, role, nama_lengkap, alamat, no_telepon) VALUES (?,?,?,?,?,?,?)',
            (username, email, pw_hash, 'buyer', nama, 'Kendari', '08000000000')
        )
        inserted_users.append((cur.lastrowid, username, n_ratings, prefs))
    except sqlite3.IntegrityError:
        row = db.execute('SELECT id FROM users WHERE username=?', (username,)).fetchone()
        if row:
            inserted_users.append((row['id'], username, n_ratings, prefs))

db.commit()
print(f"[2] {len(inserted_users)} buyer baru dibuat.")

# ============================================================
# STEP 3: Ambil semua produk tersedia
# ============================================================
produk_rows = db.execute('''
    SELECT p.id, k.nama as kategori_nama
    FROM produk p
    LEFT JOIN kategori k ON p.kategori_id = k.id
    WHERE p.tersedia = 1
''').fetchall()

all_produk = [(r['id'], r['kategori_nama']) for r in produk_rows]
pid_to_kat  = {r['id']: r['kategori_nama'] for r in produk_rows}

produk_by_kat = defaultdict(list)
for pid, kat in all_produk:
    produk_by_kat[kat].append(pid)

all_pids = [p[0] for p in all_produk]

# ============================================================
# STEP 4: Tambah rating per user sesuai konfigurasi
# ============================================================
reviews = [
    'Produk bagus, recommended!', 'Kualitas oke, sesuai harga.',
    'Sangat memuaskan!', 'Mantap, produk lokal berkualitas!',
    'Lumayan, cukup baik.', 'Pengiriman cepat, barang sesuai.',
    'Produk asli UMKM Kendari!', 'Worth it banget!', '',
]

total_ratings = 0

for buyer_id, username, n_ratings, prefs in inserted_users:
    rated_pids = set()

    # Pool favorit: ambil dari kategori favorit dulu
    fav_pool = []
    for kat in prefs:
        fav_pool.extend(produk_by_kat.get(kat, []))
    random.shuffle(fav_pool)

    n_fav = min(int(n_ratings * 0.65), len(fav_pool))   # ~65% dari favorit
    chosen = []
    for pid in fav_pool:
        if pid not in rated_pids and len(chosen) < n_fav:
            chosen.append(pid)
            rated_pids.add(pid)

    # Sisa dari pool acak
    other_pool = [p for p in all_pids if p not in rated_pids]
    random.shuffle(other_pool)
    n_other = n_ratings - len(chosen)
    for pid in other_pool[:n_other]:
        chosen.append(pid)
        rated_pids.add(pid)

    # Insert rating
    for pid in chosen:
        kat_pid = pid_to_kat.get(pid, '')
        if kat_pid in prefs:
            score = random.choices([4, 5, 3], weights=[45, 40, 15])[0]
        else:
            score = random.choices([3, 4, 2, 5, 1], weights=[35, 30, 20, 10, 5])[0]

        try:
            db.execute(
                'INSERT INTO ratings (user_id, produk_id, score, review) VALUES (?,?,?,?)',
                (buyer_id, pid, score, random.choice(reviews))
            )
            total_ratings += 1
        except sqlite3.IntegrityError:
            pass

db.commit()
db.close()

print(f"[3] Total {total_ratings} rating ditambahkan.")
print()
print("=" * 55)
print("DISTRIBUSI RATING PER USER:")
for _, username, n_ratings, _ in inserted_users:
    segmen = "1-4 Rating" if n_ratings <= 4 else ("5-10 Rating" if n_ratings <= 10 else ">10 Rating")
    print(f"  {username:<12} : {n_ratings:>2} rating  [{segmen}]")
print("=" * 55)
print(f"\nPassword semua user: buyer123")
