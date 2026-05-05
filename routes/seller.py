import os
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from functools import wraps
from werkzeug.utils import secure_filename
from models.produk import Produk
from models.kategori import Kategori
from config import UPLOAD_FOLDER

seller_bp = Blueprint('seller', __name__, url_prefix='/seller')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def seller_required(f):
    """Decorator untuk memastikan user adalah seller."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'seller':
            flash('Akses ditolak. Anda bukan seller.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


@seller_bp.route('/')
@seller_required
def dashboard():
    """Dashboard seller dengan analytics profesional."""
    from models.database import get_db
    from models.rating import Rating
    from models.user import User
    from models.wishlist import Wishlist
    import datetime

    db = get_db()
    seller_id = current_user.id

    # === BASIC STATS ===
    produk_list = Produk.get_by_seller(seller_id)
    total_produk = len(produk_list)

    # Rating stats
    rating_stats = db.execute('''
        SELECT COUNT(r.id) as total_ratings,
               COALESCE(AVG(r.score), 0) as avg_rating,
               COUNT(CASE WHEN r.score >= 4 THEN 1 END) as positive_ratings
        FROM ratings r
        JOIN produk p ON r.produk_id = p.id
        WHERE p.seller_id = ?
    ''', (seller_id,)).fetchone()

    # === REVENUE & SALES STATS ===
    # Asumsi ada tabel orders/transactions (untuk sekarang pakai estimasi)
    sales_stats = db.execute('''
        SELECT COUNT(DISTINCT r.user_id) as unique_customers,
               COUNT(r.id) as total_interactions,
               COALESCE(AVG(r.score), 0) as avg_rating
        FROM ratings r
        JOIN produk p ON r.produk_id = p.id
        WHERE p.seller_id = ?
    ''', (seller_id,)).fetchone()

    # === PRODUCT PERFORMANCE ===
    top_products = db.execute('''
        SELECT p.id, p.nama, p.harga, p.stok, p.gambar,
               COUNT(r.id) as total_ratings,
               COALESCE(AVG(r.score), 0) as avg_rating
        FROM produk p
        LEFT JOIN ratings r ON p.id = r.produk_id
        WHERE p.seller_id = ?
        GROUP BY p.id
        ORDER BY COUNT(r.id) DESC, avg_rating DESC
        LIMIT 5
    ''', (seller_id,)).fetchall()

    # === RECENT ACTIVITIES ===
    recent_ratings = db.execute('''
        SELECT r.score, r.review, r.created_at,
               p.nama as produk_nama,
               u.nama_lengkap as customer_nama
        FROM ratings r
        JOIN produk p ON r.produk_id = p.id
        JOIN users u ON r.user_id = u.id
        WHERE p.seller_id = ?
        ORDER BY r.created_at DESC
        LIMIT 5
    ''', (seller_id,)).fetchall()

    # === MONTHLY TRENDS (last 6 months) ===
    monthly_data = []
    for i in range(5, -1, -1):
        date = datetime.datetime.now() - datetime.timedelta(days=30*i)
        month_start = date.replace(day=1)
        month_end = (month_start + datetime.timedelta(days=32)).replace(day=1) - datetime.timedelta(days=1)

        month_stats = db.execute('''
            SELECT COUNT(r.id) as ratings_count,
                   COALESCE(AVG(r.score), 0) as avg_rating
            FROM ratings r
            JOIN produk p ON r.produk_id = p.id
            WHERE p.seller_id = ? AND r.created_at BETWEEN ? AND ?
        ''', (seller_id, month_start.strftime('%Y-%m-%d'), month_end.strftime('%Y-%m-%d'))).fetchone()

        monthly_data.append({
            'month': month_start.strftime('%b %Y'),
            'ratings': month_stats['ratings_count'],
            'avg_rating': round(month_stats['avg_rating'], 1)
        })

    # === STOCK ALERTS ===
    low_stock_products = [p for p in produk_list if p.stok <= 5 and p.stok > 0]
    out_of_stock_products = [p for p in produk_list if p.stok == 0]

    # === COMPILE STATS ===
    stats = {
        'total_produk': total_produk,
        'total_ratings': rating_stats['total_ratings'],
        'avg_rating': round(rating_stats['avg_rating'], 1) if rating_stats['avg_rating'] else 0,
        'positive_ratings': rating_stats['positive_ratings'],
        'unique_customers': sales_stats['unique_customers'],
        'total_interactions': sales_stats['total_interactions'],
        'low_stock_count': len(low_stock_products),
        'out_of_stock_count': len(out_of_stock_products)
    }

    kategori_list = Kategori.get_all()

    return render_template('seller/dashboard.html',
                           produk_list=produk_list,
                           stats=stats,
                           top_products=top_products,
                           recent_ratings=recent_ratings,
                           monthly_data=monthly_data,
                           low_stock_products=low_stock_products,
                           out_of_stock_products=out_of_stock_products,
                           kategori_list=kategori_list)


@seller_bp.route('/produk/tambah', methods=['GET', 'POST'])
@seller_required
def tambah_produk():
    """Form tambah produk baru."""
    if request.method == 'POST':
        nama = request.form.get('nama', '').strip()
        deskripsi = request.form.get('deskripsi', '').strip()
        harga = request.form.get('harga', type=float, default=0)
        stok = request.form.get('stok', type=int, default=0)
        kategori_id = request.form.get('kategori_id', type=int)
        tersedia = 1 if request.form.get('tersedia') == 'on' else 0

        # Handle upload gambar
        gambar = 'default.jpg'
        if 'gambar' in request.files:
            file = request.files['gambar']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Tambahkan timestamp untuk menghindari duplikat
                import time
                filename = f"{int(time.time())}_{filename}"
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                gambar = filename

        if not nama:
            flash('Nama produk wajib diisi', 'danger')
        elif harga <= 0:
            flash('Harga harus lebih dari 0', 'danger')
        else:
            produk_id = Produk.create(nama, deskripsi, harga, stok, gambar, kategori_id, current_user.id, tersedia)
            if produk_id:
                flash(f'Produk "{nama}" berhasil ditambahkan!', 'success')
                return redirect(url_for('seller.dashboard'))
            else:
                flash('Gagal menambahkan produk', 'danger')

    kategori_list = Kategori.get_all()
    return render_template('seller/produk_form.html', kategori_list=kategori_list, produk=None)


@seller_bp.route('/produk/edit/<int:produk_id>', methods=['GET', 'POST'])
@seller_required
def edit_produk(produk_id):
    """Form edit produk."""
    produk = Produk.get_by_id(produk_id)
    if not produk or produk.seller_id != current_user.id:
        flash('Produk tidak ditemukan atau bukan milik Anda', 'danger')
        return redirect(url_for('seller.dashboard'))

    if request.method == 'POST':
        nama = request.form.get('nama', '').strip()
        deskripsi = request.form.get('deskripsi', '').strip()
        harga = request.form.get('harga', type=float, default=0)
        stok = request.form.get('stok', type=int, default=0)
        kategori_id = request.form.get('kategori_id', type=int)
        tersedia = 1 if request.form.get('tersedia') == 'on' else 0

        gambar = produk.gambar
        if 'gambar' in request.files:
            file = request.files['gambar']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                import time
                filename = f"{int(time.time())}_{filename}"
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                gambar = filename

        if not nama:
            flash('Nama produk wajib diisi', 'danger')
        elif harga <= 0:
            flash('Harga harus lebih dari 0', 'danger')
        else:
            Produk.update(produk_id, nama, deskripsi, harga, stok, gambar, kategori_id, tersedia)
            flash(f'Produk "{nama}" berhasil diupdate!', 'success')
            return redirect(url_for('seller.dashboard'))

    kategori_list = Kategori.get_all()
    return render_template('seller/produk_form.html', kategori_list=kategori_list, produk=produk)


@seller_bp.route('/produk/hapus/<int:produk_id>', methods=['POST'])
@seller_required
def hapus_produk(produk_id):
    """Hapus produk."""
    produk = Produk.get_by_id(produk_id)
    if not produk or produk.seller_id != current_user.id:
        flash('Produk tidak ditemukan atau bukan milik Anda', 'danger')
    else:
        Produk.delete(produk_id)
        flash(f'Produk "{produk.nama}" berhasil dihapus', 'success')
    return redirect(url_for('seller.dashboard'))
