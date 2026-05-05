from models.database import get_db


class Rating:
    """Model Rating/Review produk."""

    def __init__(self, id, user_id, produk_id, score, review='', created_at=None, **kwargs):
        self.id = id
        self.user_id = user_id
        self.produk_id = produk_id
        self.score = score
        self.review = review
        self.created_at = created_at
        self.username = kwargs.get('username', '')
        self.produk_nama = kwargs.get('produk_nama', '')

    @staticmethod
    def get_by_user_and_produk(user_id, produk_id):
        db = get_db()
        row = db.execute('SELECT * FROM ratings WHERE user_id = ? AND produk_id = ?',
                         (user_id, produk_id)).fetchone()
        if row:
            return Rating(**dict(row))
        return None

    @staticmethod
    def get_by_produk(produk_id):
        db = get_db()
        rows = db.execute('''
            SELECT r.*, u.username
            FROM ratings r
            JOIN users u ON r.user_id = u.id
            WHERE r.produk_id = ?
            ORDER BY r.created_at DESC
        ''', (produk_id,)).fetchall()
        return [Rating(**dict(row)) for row in rows]

    @staticmethod
    def get_by_user(user_id):
        db = get_db()
        rows = db.execute('''
            SELECT r.*, p.nama as produk_nama
            FROM ratings r
            JOIN produk p ON r.produk_id = p.id
            WHERE r.user_id = ?
            ORDER BY r.created_at DESC
        ''', (user_id,)).fetchall()
        return [Rating(**dict(row)) for row in rows]

    @staticmethod
    def create_or_update(user_id, produk_id, score, review=''):
        db = get_db()
        existing = db.execute('SELECT id FROM ratings WHERE user_id = ? AND produk_id = ?',
                              (user_id, produk_id)).fetchone()
        if existing:
            db.execute('UPDATE ratings SET score=?, review=?, created_at=CURRENT_TIMESTAMP WHERE id=?',
                       (score, review, existing['id']))
        else:
            db.execute('INSERT INTO ratings (user_id, produk_id, score, review) VALUES (?, ?, ?, ?)',
                       (user_id, produk_id, score, review))
        db.commit()

    @staticmethod
    def count_by_user(user_id):
        db = get_db()
        row = db.execute('SELECT COUNT(*) as cnt FROM ratings WHERE user_id = ?', (user_id,)).fetchone()
        return row['cnt']

    @staticmethod
    def get_all_for_training():
        """Ambil semua data rating untuk training model NCF."""
        db = get_db()
        rows = db.execute('SELECT user_id, produk_id, score FROM ratings').fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def count():
        db = get_db()
        row = db.execute('SELECT COUNT(*) as cnt FROM ratings').fetchone()
        return row['cnt']

    @staticmethod
    def get_user_rated_produk_ids(user_id):
        """Ambil list produk_id yang sudah di-rating user."""
        db = get_db()
        rows = db.execute('SELECT produk_id FROM ratings WHERE user_id = ?', (user_id,)).fetchall()
        return [row['produk_id'] for row in rows]
