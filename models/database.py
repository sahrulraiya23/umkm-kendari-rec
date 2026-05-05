import sqlite3
import os
from config import DATABASE


def get_db():
    """Mendapatkan koneksi database SQLite."""
    from flask import g
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    """Menutup koneksi database."""
    from flask import g
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Inisialisasi schema database."""
    db = sqlite3.connect(DATABASE)
    db.execute("PRAGMA foreign_keys = ON")

    db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'buyer' CHECK(role IN ('admin','seller','buyer')),
            nama_lengkap TEXT NOT NULL,
            alamat TEXT DEFAULT '',
            no_telepon TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS kategori (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT UNIQUE NOT NULL,
            deskripsi TEXT DEFAULT '',
            icon TEXT DEFAULT 'bi-tag'
        );

        CREATE TABLE IF NOT EXISTS produk (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL,
            deskripsi TEXT DEFAULT '',
            harga REAL NOT NULL DEFAULT 0,
            stok INTEGER NOT NULL DEFAULT 0,
            gambar TEXT DEFAULT 'default.jpg',
            kategori_id INTEGER,
            seller_id INTEGER NOT NULL,
            kecamatan TEXT DEFAULT 'Kendari',
            tersedia INTEGER NOT NULL DEFAULT 1 CHECK(tersedia IN (0, 1)),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (kategori_id) REFERENCES kategori(id) ON DELETE SET NULL,
            FOREIGN KEY (seller_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            produk_id INTEGER NOT NULL,
            score INTEGER NOT NULL CHECK(score >= 1 AND score <= 5),
            review TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (produk_id) REFERENCES produk(id) ON DELETE CASCADE,
            UNIQUE(user_id, produk_id)
        );

        CREATE TABLE IF NOT EXISTS user_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            kategori_id INTEGER,
            harga_min REAL DEFAULT 0,
            harga_max REAL DEFAULT 999999999,
            rating_min REAL DEFAULT 3.0,
            sort_by TEXT DEFAULT 'rating',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (kategori_id) REFERENCES kategori(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS wishlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            produk_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (produk_id) REFERENCES produk(id) ON DELETE CASCADE,
            UNIQUE(user_id, produk_id)
        );

        CREATE TABLE IF NOT EXISTS operasional_toko (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hari_index INTEGER NOT NULL UNIQUE CHECK(hari_index >= 0 AND hari_index <= 6),
            hari_nama TEXT NOT NULL,
            buka_jam TEXT NOT NULL DEFAULT '08:00',
            tutup_jam TEXT NOT NULL DEFAULT '17:00',
            is_open INTEGER NOT NULL DEFAULT 1 CHECK(is_open IN (0, 1))
        );

        CREATE TABLE IF NOT EXISTS seller_operasional (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER NOT NULL,
            hari_index INTEGER NOT NULL CHECK(hari_index >= 0 AND hari_index <= 6),
            hari_nama TEXT NOT NULL,
            buka_jam TEXT NOT NULL DEFAULT '08:00',
            tutup_jam TEXT NOT NULL DEFAULT '17:00',
            is_open INTEGER NOT NULL DEFAULT 1 CHECK(is_open IN (0, 1)),
            FOREIGN KEY (seller_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(seller_id, hari_index)
        );
    ''')

    # Seed default jadwal operasional jika belum ada
    schedule = [
        (0, 'Senin', '08:00', '17:00', 1),
        (1, 'Selasa', '08:00', '17:00', 1),
        (2, 'Rabu', '08:00', '17:00', 1),
        (3, 'Kamis', '08:00', '17:00', 1),
        (4, 'Jumat', '08:00', '17:00', 1),
        (5, 'Sabtu', '08:00', '17:00', 1),
        (6, 'Minggu', '08:00', '17:00', 0),
    ]
    db.executemany(
        '''
        INSERT OR IGNORE INTO operasional_toko (hari_index, hari_nama, buka_jam, tutup_jam, is_open)
        VALUES (?, ?, ?, ?, ?)
        ''',
        schedule
    )

    # Seed default jadwal operasional per seller (copy dari jadwal umum)
    sellers = db.execute("SELECT id FROM users WHERE role = 'seller'").fetchall()
    for seller in sellers:
        seller_schedule = [(seller[0], s[0], s[1], s[2], s[3], s[4]) for s in schedule]
        db.executemany(
            '''
            INSERT OR IGNORE INTO seller_operasional
            (seller_id, hari_index, hari_nama, buka_jam, tutup_jam, is_open)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            seller_schedule
        )

    db.commit()
    db.close()
    print("Database berhasil diinisialisasi!")
