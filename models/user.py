from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from models.database import get_db


class User(UserMixin):
    """Model User untuk Flask-Login."""

    def __init__(self, id, username, email, password_hash, role, nama_lengkap, alamat='', no_telepon='', created_at=None):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.role = role
        self.nama_lengkap = nama_lengkap
        self.alamat = alamat
        self.no_telepon = no_telepon
        self.created_at = created_at

    @staticmethod
    def get_by_id(user_id):
        db = get_db()
        row = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if row:
            return User(**dict(row))
        return None

    @staticmethod
    def get_by_username(username):
        db = get_db()
        row = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        if row:
            return User(**dict(row))
        return None

    @staticmethod
    def get_by_email(email):
        db = get_db()
        row = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if row:
            return User(**dict(row))
        return None

    @staticmethod
    def create(username, email, password, role, nama_lengkap, alamat='', no_telepon=''):
        db = get_db()
        pw_hash = generate_password_hash(password)
        try:
            db.execute(
                'INSERT INTO users (username, email, password_hash, role, nama_lengkap, alamat, no_telepon) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (username, email, pw_hash, role, nama_lengkap, alamat, no_telepon)
            )
            db.commit()
            return True
        except Exception as e:
            print(f"Error creating user: {e}")
            return False

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def get_all():
        db = get_db()
        rows = db.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()
        return [User(**dict(row)) for row in rows]

    @staticmethod
    def count_by_role(role):
        db = get_db()
        row = db.execute('SELECT COUNT(*) as cnt FROM users WHERE role = ?', (role,)).fetchone()
        return row['cnt']

    @staticmethod
    def delete(user_id):
        db = get_db()
        db.execute('DELETE FROM users WHERE id = ?', (user_id,))
        db.commit()
