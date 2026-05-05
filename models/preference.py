from models.database import get_db


class UserPreference:
    """Model preferensi user (onboarding data untuk KNN cold-start)."""

    def __init__(self, id, user_id, kategori_id=None, harga_min=0, harga_max=999999999,
                 rating_min=3.0, sort_by='rating', created_at=None):
        self.id = id
        self.user_id = user_id
        self.kategori_id = kategori_id
        self.harga_min = harga_min
        self.harga_max = harga_max
        self.rating_min = rating_min
        self.sort_by = sort_by
        self.created_at = created_at

    @staticmethod
    def get_by_user(user_id):
        """Ambil semua preferensi user."""
        db = get_db()
        rows = db.execute('SELECT * FROM user_preferences WHERE user_id = ?', (user_id,)).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d.setdefault('rating_min', 3.0)
            d.setdefault('sort_by', 'rating')
            result.append(UserPreference(**d))
        return result

    @staticmethod
    def get_preferred_kategori_ids(user_id):
        """Ambil list kategori_id yang dipilih user."""
        db = get_db()
        rows = db.execute(
            'SELECT DISTINCT kategori_id FROM user_preferences WHERE user_id = ? AND kategori_id IS NOT NULL',
            (user_id,)
        ).fetchall()
        return [row['kategori_id'] for row in rows]

    @staticmethod
    def get_price_range(user_id):
        """Ambil range harga preferensi user."""
        db = get_db()
        row = db.execute(
            'SELECT MIN(harga_min) as harga_min, MAX(harga_max) as harga_max FROM user_preferences WHERE user_id = ?',
            (user_id,)
        ).fetchone()
        if row and row['harga_min'] is not None:
            return row['harga_min'], row['harga_max']
        return 0, 999999999

    @staticmethod
    def get_rating_min(user_id):
        """Ambil rating minimum preferensi user."""
        db = get_db()
        try:
            row = db.execute(
                'SELECT rating_min FROM user_preferences WHERE user_id = ? LIMIT 1',
                (user_id,)
            ).fetchone()
            if row and row['rating_min'] is not None:
                return float(row['rating_min'])
        except Exception:
            pass
        return 3.0

    @staticmethod
    def get_sort_by(user_id):
        """Ambil preferensi urutan rekomendasi user."""
        db = get_db()
        try:
            row = db.execute(
                'SELECT sort_by FROM user_preferences WHERE user_id = ? LIMIT 1',
                (user_id,)
            ).fetchone()
            if row and row['sort_by']:
                return row['sort_by']
        except Exception:
            pass
        return 'rating'

    @staticmethod
    def has_preferences(user_id):
        """Cek apakah user sudah mengisi preferensi."""
        db = get_db()
        row = db.execute('SELECT COUNT(*) as cnt FROM user_preferences WHERE user_id = ?', (user_id,)).fetchone()
        return row['cnt'] > 0

    @staticmethod
    def save_preferences(user_id, kategori_ids, harga_min=0, harga_max=999999999,
                         rating_min=3.0, sort_by='rating'):
        """
        Simpan preferensi user (hapus yang lama, simpan yang baru).

        Args:
            user_id: ID user
            kategori_ids: list of kategori_id yang dipilih
            harga_min: harga minimum preferensi
            harga_max: harga maksimum preferensi
            rating_min: rating minimum produk yang diinginkan (1-5)
            sort_by: urutan rekomendasi ('rating', 'harga_asc', 'harga_desc', 'terbaru')
        """
        db = get_db()
        # Hapus preferensi lama
        db.execute('DELETE FROM user_preferences WHERE user_id = ?', (user_id,))

        cols = 'user_id, kategori_id, harga_min, harga_max, rating_min, sort_by'
        placeholders = '?, ?, ?, ?, ?, ?'

        def _insert(kat_id):
            try:
                db.execute(
                    f'INSERT INTO user_preferences ({cols}) VALUES ({placeholders})',
                    (user_id, kat_id, harga_min, harga_max, rating_min, sort_by)
                )
            except Exception:
                # Kolom baru belum ada (migrasi) — fallback ke kolom lama
                db.execute(
                    'INSERT INTO user_preferences (user_id, kategori_id, harga_min, harga_max) VALUES (?,?,?,?)',
                    (user_id, kat_id, harga_min, harga_max)
                )

        # Simpan preferensi baru — 1 row per kategori
        for kat_id in kategori_ids:
            _insert(kat_id)

        # Jika tidak ada kategori terpilih, simpan 1 row untuk range saja
        if not kategori_ids:
            _insert(None)

        db.commit()

    @staticmethod
    def delete_by_user(user_id):
        db = get_db()
        db.execute('DELETE FROM user_preferences WHERE user_id = ?', (user_id,))
        db.commit()
