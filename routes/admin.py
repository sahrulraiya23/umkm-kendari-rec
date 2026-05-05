from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, Response
from flask_login import login_required, current_user
from functools import wraps
from models.user import User
from models.produk import Produk
from models.kategori import Kategori
from models.rating import Rating
import csv
import io

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    """Decorator untuk memastikan user adalah admin."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'admin':
            flash('Akses ditolak. Anda bukan admin.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/')
@admin_required
def dashboard():
    """Dashboard admin dengan statistik."""
    stats = {
        'total_users': len(User.get_all()),
        'total_buyers': User.count_by_role('buyer'),
        'total_sellers': User.count_by_role('seller'),
        'total_produk': Produk.count(),
        'total_kategori': Kategori.count(),
        'total_ratings': Rating.count()
    }
    kategori_list = Kategori.get_all()
    return render_template('admin/dashboard.html', stats=stats, kategori_list=kategori_list)


@admin_bp.route('/api/chart-data')
@admin_required
def chart_data():
    """API data chart untuk dashboard admin."""
    from models.database import get_db
    db = get_db()

    # Rating per kategori
    kat_data = db.execute('''
        SELECT k.nama, COUNT(r.id) as total, ROUND(AVG(r.score), 2) as avg_score
        FROM kategori k
        LEFT JOIN produk p ON k.id = p.kategori_id
        LEFT JOIN ratings r ON p.id = r.produk_id
        GROUP BY k.id ORDER BY total DESC
    ''').fetchall()

    # Rating distribusi (1-5)
    dist_data = db.execute('''
        SELECT score, COUNT(*) as total FROM ratings GROUP BY score ORDER BY score
    ''').fetchall()

    # Top produk by rating count
    top_produk = db.execute('''
        SELECT p.nama, COUNT(r.id) as total_rating, ROUND(AVG(r.score),1) as avg_rating
        FROM produk p JOIN ratings r ON p.id = r.produk_id
        GROUP BY p.id ORDER BY total_rating DESC LIMIT 10
    ''').fetchall()

    # User registrations per role
    role_data = db.execute('''
        SELECT role, COUNT(*) as total FROM users GROUP BY role
    ''').fetchall()

    return jsonify({
        'rating_per_kategori': {
            'labels': [r['nama'] for r in kat_data],
            'totals': [r['total'] for r in kat_data],
            'averages': [r['avg_score'] or 0 for r in kat_data],
        },
        'rating_distribusi': {
            'labels': [f'{r["score"]} Bintang' for r in dist_data],
            'totals': [r['total'] for r in dist_data],
        },
        'top_produk': {
            'labels': [r['nama'][:20] for r in top_produk],
            'totals': [r['total_rating'] for r in top_produk],
            'averages': [r['avg_rating'] for r in top_produk],
        },
        'user_roles': {
            'labels': [r['role'].capitalize() for r in role_data],
            'totals': [r['total'] for r in role_data],
        }
    })


@admin_bp.route('/kategori', methods=['GET', 'POST'])
@admin_required
def kelola_kategori():
    """CRUD kategori."""
    if request.method == 'POST':
        action = request.form.get('action')
        nama = request.form.get('nama', '').strip()
        deskripsi = request.form.get('deskripsi', '').strip()
        icon = request.form.get('icon', 'bi-tag').strip()

        if action == 'add':
            if nama:
                Kategori.create(nama, deskripsi, icon)
                flash(f'Kategori "{nama}" berhasil ditambahkan', 'success')
            else:
                flash('Nama kategori wajib diisi', 'danger')

        elif action == 'edit':
            kategori_id = request.form.get('kategori_id', type=int)
            if kategori_id and nama:
                Kategori.update(kategori_id, nama, deskripsi, icon)
                flash(f'Kategori "{nama}" berhasil diupdate', 'success')

        elif action == 'delete':
            kategori_id = request.form.get('kategori_id', type=int)
            if kategori_id:
                Kategori.delete(kategori_id)
                flash('Kategori berhasil dihapus', 'success')

        return redirect(url_for('admin.kelola_kategori'))

    kategori_list = Kategori.get_all()
    return render_template('admin/kategori.html', kategori_list=kategori_list)


@admin_bp.route('/users')
@admin_required
def kelola_users():
    """Daftar semua pengguna."""
    users = User.get_all()
    kategori_list = Kategori.get_all()
    return render_template('admin/users.html', users=users, kategori_list=kategori_list)


@admin_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Hapus user."""
    if user_id == current_user.id:
        flash('Tidak bisa menghapus akun sendiri', 'danger')
    else:
        User.delete(user_id)
        flash('User berhasil dihapus', 'success')
    return redirect(url_for('admin.kelola_users'))


@admin_bp.route('/produk')
@admin_required
def kelola_produk():
    """Daftar semua produk (Admin)."""
    from models.database import get_db
    db = get_db()
    
    rows = db.execute('''
        SELECT p.id, p.nama, p.harga, p.stok, p.tersedia, p.gambar,
               k.nama as kategori_nama, u.nama_lengkap as seller_nama
        FROM produk p
        LEFT JOIN kategori k ON p.kategori_id = k.id
        LEFT JOIN users u ON p.seller_id = u.id
        ORDER BY p.created_at DESC
    ''').fetchall()
    
    produk_list = [dict(row) for row in rows]
    kategori_list = Kategori.get_all()
    
    return render_template('admin/produk.html', produk_list=produk_list, kategori_list=kategori_list)


@admin_bp.route('/produk/edit/<int:produk_id>', methods=['GET', 'POST'])
@admin_required
def edit_produk(produk_id):
    """Form edit produk (Admin)."""
    import os
    from werkzeug.utils import secure_filename
    from config import UPLOAD_FOLDER
    
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    produk = Produk.get_by_id(produk_id)
    if not produk:
        flash('Produk tidak ditemukan', 'danger')
        return redirect(url_for('admin.kelola_produk'))

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
            return redirect(url_for('admin.kelola_produk'))

    kategori_list = Kategori.get_all()
    return render_template('admin/produk_form.html', kategori_list=kategori_list, produk=produk)


@admin_bp.route('/produk/hapus/<int:produk_id>', methods=['POST'])
@admin_required
def hapus_produk(produk_id):
    """Hapus produk (Admin)."""
    produk = Produk.get_by_id(produk_id)
    if produk:
        Produk.delete(produk_id)
        flash(f'Produk "{produk.nama}" berhasil dihapus', 'success')
    else:
        flash('Produk tidak ditemukan', 'danger')
    return redirect(url_for('admin.kelola_produk'))


@admin_bp.route('/train-model', methods=['GET', 'POST'])
@admin_required
def train_model():
    """Trigger training model NCF."""
    result = None
    if request.method == 'POST':
        ratings_data = Rating.get_all_for_training()
        from recommendation.ncf import train_ncf_model
        result = train_ncf_model(ratings_data)

        if result['success']:
            flash(result['message'], 'success')
        else:
            flash(result['message'], 'danger')

    kategori_list = Kategori.get_all()
    return render_template('admin/train_model.html', result=result, kategori_list=kategori_list)


@admin_bp.route('/evaluasi')
@admin_required
def evaluasi():
    """Halaman evaluasi model - MAE, RMSE, Precision@K, Recall@K, F1@K."""
    from recommendation.evaluation import evaluate_knn, evaluate_ncf
    from recommendation.knn import get_knn_data_from_db
    from models.database import get_db

    db = get_db()

    # Ambil semua rating untuk evaluasi
    all_ratings = db.execute('''
        SELECT user_id, produk_id, score FROM ratings
    ''').fetchall()
    all_ratings = [dict(r) for r in all_ratings]

    # Evaluasi KNN
    products_data, kategori_ids = get_knn_data_from_db()
    knn_eval = evaluate_knn(products_data, kategori_ids, all_ratings)

    # Evaluasi NCF
    user_ids = list(set(r['user_id'] for r in all_ratings))
    ncf_eval = evaluate_ncf(user_ids, all_ratings)

    kategori_list = Kategori.get_all()
    return render_template('admin/evaluasi.html',
                           knn_eval=knn_eval,
                           ncf_eval=ncf_eval,
                           total_ratings=len(all_ratings),
                           total_users=len(user_ids),
                           kategori_list=kategori_list)


@admin_bp.route('/evaluasi/chart-data')
@admin_required
def evaluasi_chart_data():
    """API data chart evaluasi KNN vs NCF."""
    from recommendation.evaluation import evaluate_knn, evaluate_ncf
    from recommendation.knn import get_knn_data_from_db
    from models.database import get_db

    db = get_db()
    all_ratings = db.execute('SELECT user_id, produk_id, score FROM ratings').fetchall()
    all_ratings = [dict(r) for r in all_ratings]

    products_data, kategori_ids = get_knn_data_from_db()
    knn = evaluate_knn(products_data, kategori_ids, all_ratings)

    user_ids = list(set(r['user_id'] for r in all_ratings))
    ncf = evaluate_ncf(user_ids, all_ratings) or {
        'mae': 0, 'rmse': 0,
        'precision_at_5': 0, 'precision_at_10': 0,
        'recall_at_5': 0, 'recall_at_10': 0,
        'f1_at_5': 0, 'f1_at_10': 0,
        'ndcg_at_10': 0
    }

    return jsonify({
        'knn': {
            'mae':            round(knn.get('mae', 0), 4),
            'rmse':           round(knn.get('rmse', 0), 4),
            'precision_at_5': round(knn.get('precision_at_5', 0) * 100, 2),
            'precision_at_10':round(knn.get('precision_at_10', 0) * 100, 2),
            'recall_at_5':    round(knn.get('recall_at_5', 0) * 100, 2),
            'recall_at_10':   round(knn.get('recall_at_10', 0) * 100, 2),
            'f1_at_5':        round(knn.get('f1_at_5', 0) * 100, 2),
            'f1_at_10':       round(knn.get('f1_at_10', 0) * 100, 2),
            'ndcg_at_10':     round(knn.get('ndcg_at_10', 0) * 100, 2),
        },
        'ncf': {
            'mae':            round(ncf.get('mae', 0), 4),
            'rmse':           round(ncf.get('rmse', 0), 4),
            'precision_at_5': round(ncf.get('precision_at_5', 0) * 100, 2),
            'precision_at_10':round(ncf.get('precision_at_10', 0) * 100, 2),
            'recall_at_5':    round(ncf.get('recall_at_5', 0) * 100, 2),
            'recall_at_10':   round(ncf.get('recall_at_10', 0) * 100, 2),
            'f1_at_5':        round(ncf.get('f1_at_5', 0) * 100, 2),
            'f1_at_10':       round(ncf.get('f1_at_10', 0) * 100, 2),
            'ndcg_at_10':     round(ncf.get('ndcg_at_10', 0) * 100, 2),
        }
    })


@admin_bp.route('/export/ratings')
@admin_required
def export_ratings():
    """Export data rating ke CSV."""
    from models.database import get_db
    db = get_db()

    rows = db.execute('''
        SELECT r.id, u.username, u.nama_lengkap, p.nama as produk_nama,
               k.nama as kategori_nama, r.score, r.review, r.created_at
        FROM ratings r
        JOIN users u ON r.user_id = u.id
        JOIN produk p ON r.produk_id = p.id
        LEFT JOIN kategori k ON p.kategori_id = k.id
        ORDER BY r.created_at DESC
    ''').fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Username', 'Nama Lengkap', 'Produk', 'Kategori', 'Score', 'Review', 'Created At'])

    for row in rows:
        writer.writerow([row['id'], row['username'], row['nama_lengkap'],
                         row['produk_nama'], row['kategori_nama'],
                         row['score'], row['review'], row['created_at']])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=ratings_export.csv'}
    )


@admin_bp.route('/export/users')
@admin_required
def export_users():
    """Export data user ke CSV."""
    from models.database import get_db
    db = get_db()

    rows = db.execute('''
        SELECT id, username, email, role, nama_lengkap, alamat, no_telepon, created_at
        FROM users ORDER BY created_at DESC
    ''').fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Username', 'Email', 'Role', 'Nama Lengkap', 'Alamat', 'No Telepon', 'Created At'])

    for row in rows:
        writer.writerow([row['id'], row['username'], row['email'], row['role'],
                         row['nama_lengkap'], row['alamat'], row['no_telepon'], row['created_at']])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=users_export.csv'}
    )


@admin_bp.route('/export/produk')
@admin_required
def export_produk():
    """Export data produk ke CSV."""
    from models.database import get_db
    db = get_db()

    rows = db.execute('''
        SELECT p.id, p.nama, p.deskripsi, p.harga, p.stok,
               k.nama as kategori_nama, u.nama_lengkap as seller_nama,
               COALESCE(AVG(r.score), 0) as avg_rating, COUNT(r.id) as total_rating,
               p.created_at
        FROM produk p
        LEFT JOIN kategori k ON p.kategori_id = k.id
        LEFT JOIN users u ON p.seller_id = u.id
        LEFT JOIN ratings r ON p.id = r.produk_id
        GROUP BY p.id ORDER BY p.created_at DESC
    ''').fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Nama', 'Deskripsi', 'Harga', 'Stok', 'Kategori', 'Seller', 'Avg Rating', 'Total Rating', 'Created At'])

    for row in rows:
        writer.writerow([row['id'], row['nama'], row['deskripsi'], row['harga'],
                         row['stok'], row['kategori_nama'], row['seller_nama'],
                         row['avg_rating'], row['total_rating'], row['created_at']])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=produk_export.csv'}
    )


@admin_bp.route('/operasional', methods=['GET', 'POST'])
@admin_required
def kelola_operasional():
    """Kelola jadwal operasional toko untuk chatbot."""
    from models.database import get_db
    db = get_db()

    if request.method == 'POST':
        try:
            for day_idx in range(7):
                is_open = 1 if request.form.get(f'is_open_{day_idx}') == '1' else 0
                buka_jam = request.form.get(f'buka_jam_{day_idx}', '08:00').strip() or '08:00'
                tutup_jam = request.form.get(f'tutup_jam_{day_idx}', '17:00').strip() or '17:00'
                db.execute(
                    '''
                    UPDATE operasional_toko
                    SET buka_jam = ?, tutup_jam = ?, is_open = ?
                    WHERE hari_index = ?
                    ''',
                    (buka_jam, tutup_jam, is_open, day_idx)
                )
            db.commit()
            flash('Jadwal operasional berhasil diperbarui.', 'success')
        except Exception as e:
            db.rollback()
            flash(f'Gagal menyimpan jadwal operasional: {e}', 'danger')
        return redirect(url_for('admin.kelola_operasional'))

    rows = db.execute(
        '''
        SELECT hari_index, hari_nama, buka_jam, tutup_jam, is_open
        FROM operasional_toko
        ORDER BY hari_index ASC
        '''
    ).fetchall()
    schedule = [dict(row) for row in rows]

    kategori_list = Kategori.get_all()
    return render_template(
        'admin/operasional.html',
        schedule=schedule,
        kategori_list=kategori_list
    )


@admin_bp.route('/operasional/seller', methods=['GET', 'POST'])
@admin_required
def kelola_operasional_seller():
    """Kelola jadwal operasional per toko/seller."""
    from models.database import get_db
    db = get_db()

    sellers = db.execute(
        "SELECT id, username, nama_lengkap FROM users WHERE role = 'seller' ORDER BY nama_lengkap ASC"
    ).fetchall()

    if not sellers:
        flash('Belum ada akun seller.', 'warning')
        return redirect(url_for('admin.dashboard'))

    selected_seller_id = request.args.get('seller_id', type=int) or sellers[0]['id']

    if request.method == 'POST':
        selected_seller_id = request.form.get('seller_id', type=int) or selected_seller_id
        try:
            for day_idx in range(7):
                is_open = 1 if request.form.get(f'is_open_{day_idx}') == '1' else 0
                buka_jam = request.form.get(f'buka_jam_{day_idx}', '08:00').strip() or '08:00'
                tutup_jam = request.form.get(f'tutup_jam_{day_idx}', '17:00').strip() or '17:00'
                db.execute(
                    '''
                    UPDATE seller_operasional
                    SET buka_jam = ?, tutup_jam = ?, is_open = ?
                    WHERE seller_id = ? AND hari_index = ?
                    ''',
                    (buka_jam, tutup_jam, is_open, selected_seller_id, day_idx)
                )
            db.commit()
            flash('Jadwal operasional toko berhasil diperbarui.', 'success')
        except Exception as e:
            db.rollback()
            flash(f'Gagal menyimpan jadwal toko: {e}', 'danger')
        return redirect(url_for('admin.kelola_operasional_seller', seller_id=selected_seller_id))

    rows = db.execute(
        '''
        SELECT hari_index, hari_nama, buka_jam, tutup_jam, is_open
        FROM seller_operasional
        WHERE seller_id = ?
        ORDER BY hari_index ASC
        ''',
        (selected_seller_id,)
    ).fetchall()
    schedule = [dict(row) for row in rows]

    selected_seller = next((dict(s) for s in sellers if s['id'] == selected_seller_id), dict(sellers[0]))
    kategori_list = Kategori.get_all()
    return render_template(
        'admin/operasional_seller.html',
        sellers=[dict(s) for s in sellers],
        selected_seller=selected_seller,
        schedule=schedule,
        kategori_list=kategori_list
    )
