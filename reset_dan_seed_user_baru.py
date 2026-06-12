# -*- coding: utf-8 -*-
"""
Script Reset + Seed User dengan Rating BERVARIASI (versi ditingkatkan)
===========================================
Distribusi user dan rating ditingkatkan agar NCF memiliki cukup data:
  - Segmen 1-4 Rating  : rezky, noval, usrianto, raihan         (3-4 rating)
  - Segmen 5-10 Rating : iqbal, wahyu, rian, apri, hendra, sari (10-15 rating)
  - Segmen >10 Rating  : dany, alfin, aril, andi, bram, citra,
                         fandi, galih, hani, joko                (18-25 rating)

Total: 20 user buyer dengan ~300+ rating untuk training NCF yang lebih baik.
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
# STEP 2: Buat 20 buyer baru dengan jumlah rating bervariasi
# (username, email, nama_lengkap, n_ratings, [kategori_fav])
# ============================================================
new_buyers_cfg = [
    # ── Segmen Cold-Start: 1-4 Rating ────────────────────────
    ('rezky',    'rezky@mail.com',    'Rezky Ramadhan',    4, ['Kuliner', 'Agro']),
    ('noval',    'noval@mail.com',    'Noval Hidayat',     4, ['Fashion', 'Kriya']),
    ('usrianto', 'usrianto@mail.com', 'Usrianto Putra',    3, ['Digital', 'Jasa']),
    ('raihan',   'raihan@mail.com',   'Raihan Akbar',      4, ['Kuliner', 'Retail']),

    # ── Segmen Warm: 15-20 Rating ────────────────────────────
    ('iqbal',    'iqbal@mail.com',    'Iqbal Fauzi',      18, ['Kriya', 'Fashion', 'Kesehatan']),
    ('wahyu',    'wahyu@mail.com',    'Wahyu Pratama',    17, ['Agro', 'Kuliner', 'Retail']),
    ('rian',     'rian@mail.com',     'Rian Saputra',     19, ['Jasa', 'Digital', 'Kriya']),
    ('apri',     'apri@mail.com',     'Apri Yanto',       18, ['Kesehatan', 'Agro', 'Kuliner']),
    ('hendra',   'hendra@mail.com',   'Hendra Wijaya',    20, ['Fashion', 'Retail', 'Agro']),
    ('sari',     'sari@mail.com',     'Sari Dewi',        16, ['Kesehatan', 'Kuliner', 'Kriya']),

    # ── Segmen Hot: 35-45 Rating ─────────────────────────────
    ('dany',     'dany@mail.com',     'Dany Kurniawan',   38, ['Fashion', 'Retail', 'Kriya']),
    ('alfin',    'alfin@mail.com',    'Alfin Maulana',    35, ['Digital', 'Jasa', 'Fashion']),
    ('aril',     'aril@mail.com',     'Aril Hendra',      40, ['Kuliner', 'Kriya', 'Agro']),
    ('andi',     'andi@mail.com',     'Andi Syahputra',   39, ['Retail', 'Kesehatan', 'Fashion']),
    ('bram',     'bram@mail.com',     'Bram Santoso',     36, ['Agro', 'Kuliner', 'Jasa']),
    ('citra',    'citra@mail.com',    'Citra Lestari',    42, ['Kesehatan', 'Kriya', 'Fashion']),
    ('fandi',    'fandi@mail.com',    'Fandi Ahmad',      45, ['Digital', 'Retail', 'Agro']),
    ('galih',    'galih@mail.com',    'Galih Permana',    38, ['Jasa', 'Kuliner', 'Kesehatan']),
    ('hani',     'hani@mail.com',     'Hani Rahayu',      41, ['Fashion', 'Kriya', 'Retail']),
    ('joko',     'joko@mail.com',     'Joko Susilo',      43, ['Agro', 'Digital', 'Kuliner']),
]

# Tambah 40 extra users dengan rating banyak untuk meningkatkan densitas rating
extra_cats = ['Kuliner', 'Agro', 'Fashion', 'Kriya', 'Digital', 'Jasa', 'Kesehatan', 'Retail']
for i in range(1, 41):
    username = f"user_extra_{i}"
    email = f"{username}@mail.com"
    nama = f"Extra Buyer {i}"
    n_prefs = random.randint(2, 4)
    prefs = random.sample(extra_cats, n_prefs)
    if i <= 15:
        n_ratings = random.randint(15, 22)
    else:
        n_ratings = random.randint(30, 45)
    new_buyers_cfg.append((username, email, nama, n_ratings, prefs))

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
    'Sudah beli berkali-kali, selalu puas!', 'Sangat direkomendasikan!',
    'Harga terjangkau, kualitas bagus.', 'Produk otentik, suka banget!',
]

total_ratings = 0

for buyer_id, username, n_ratings, prefs in inserted_users:
    rated_pids = set()

    # Pool favorit: ambil dari kategori favorit dulu (~70%)
    fav_pool = []
    for kat in prefs:
        fav_pool.extend(produk_by_kat.get(kat, []))
    random.shuffle(fav_pool)

    n_fav = min(int(n_ratings * 0.70), len(fav_pool))
    chosen = []
    for pid in fav_pool:
        if pid not in rated_pids and len(chosen) < n_fav:
            chosen.append(pid)
            rated_pids.add(pid)

    # Sisa dari pool acak (30%)
    other_pool = [p for p in all_pids if p not in rated_pids]
    random.shuffle(other_pool)
    n_other = n_ratings - len(chosen)
    for pid in other_pool[:n_other]:
        chosen.append(pid)
        rated_pids.add(pid)

    # Insert rating dengan score realistis
    for pid in chosen:
        kat_pid = pid_to_kat.get(pid, '')
        if kat_pid in prefs:
            # Kategori favorit: score cenderung tinggi (signal kuat untuk NCF)
            score = random.choices([5, 4, 3], weights=[45, 40, 15])[0]
        else:
            # Non-favorit: distribusi lebih merata
            score = random.choices([4, 3, 5, 2, 1], weights=[30, 30, 20, 15, 5])[0]

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
print("=" * 60)
print("DISTRIBUSI RATING PER USER:")
print(f"{'Username':<12} {'Rating':>8}  {'Segmen'}")
print("-" * 60)
for _, username, n_ratings, _ in inserted_users:
    if n_ratings <= 4:
        segmen = "Cold-Start (1-4)"
    elif n_ratings <= 15:
        segmen = "Warm (5-15)"
    else:
        segmen = "Hot (>15)"
    print(f"  {username:<12}: {n_ratings:>2} rating  [{segmen}]")
print("=" * 60)
print(f"\nTotal user  : {len(inserted_users)}")
print(f"Total rating: {total_ratings}")
print(f"\nPassword semua user: buyer123")
