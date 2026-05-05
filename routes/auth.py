from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from models.user import User
from models.kategori import Kategori
from models.preference import UserPreference

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', 'buyer')
        nama_lengkap = request.form.get('nama_lengkap', '').strip()
        alamat = request.form.get('alamat', '').strip()
        no_telepon = request.form.get('no_telepon', '').strip()

        # Validasi
        errors = []
        if not username or len(username) < 3:
            errors.append('Username minimal 3 karakter')
        if not email or '@' not in email:
            errors.append('Email tidak valid')
        if not password or len(password) < 6:
            errors.append('Password minimal 6 karakter')
        if password != confirm_password:
            errors.append('Konfirmasi password tidak cocok')
        if not nama_lengkap:
            errors.append('Nama lengkap wajib diisi')
        if role not in ('buyer', 'seller'):
            errors.append('Role tidak valid')

        if User.get_by_username(username):
            errors.append('Username sudah digunakan')
        if User.get_by_email(email):
            errors.append('Email sudah digunakan')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('auth/register.html',
                                   username=username, email=email,
                                   nama_lengkap=nama_lengkap, alamat=alamat,
                                   no_telepon=no_telepon, role=role)

        success = User.create(username, email, password, role, nama_lengkap, alamat, no_telepon)
        if success:
            # Auto-login setelah register, lalu arahkan ke onboarding
            user = User.get_by_username(username)
            if user:
                login_user(user)
                if user.role == 'buyer':
                    flash('Registrasi berhasil! Bantu kami kenali preferensi Anda.', 'success')
                    return redirect(url_for('auth.onboarding'))
                else:
                    flash('Registrasi berhasil! Selamat datang.', 'success')
                    return redirect(url_for('seller.dashboard'))
            else:
                flash('Registrasi berhasil! Silakan login.', 'success')
                return redirect(url_for('auth.login'))
        else:
            flash('Terjadi kesalahan saat registrasi', 'danger')

    return render_template('auth/register.html')


@auth_bp.route('/onboarding', methods=['GET', 'POST'])
@login_required
def onboarding():
    """Halaman onboarding — user pilih kategori favorit & range harga (seperti Gojek)."""
    if request.method == 'POST':
        # Ambil kategori yang dipilih
        kategori_ids = request.form.getlist('kategori_ids', type=int)
        harga_min = request.form.get('harga_min', 0, type=float)
        harga_max = request.form.get('harga_max', 999999999, type=float)
        rating_min = request.form.get('rating_min', 3.0, type=float)
        sort_by = request.form.get('sort_by', 'rating')

        if harga_min < 0:
            harga_min = 0
        if harga_max <= 0:
            harga_max = 999999999
        if harga_max < harga_min:
            harga_max = harga_min + 100000
        if rating_min < 1:
            rating_min = 1.0
        if rating_min > 5:
            rating_min = 5.0
        if sort_by not in ('rating', 'harga_asc', 'harga_desc', 'terbaru'):
            sort_by = 'rating'

        UserPreference.save_preferences(current_user.id, kategori_ids, harga_min, harga_max,
                                        rating_min=rating_min, sort_by=sort_by)
        flash('Preferensi berhasil disimpan! Rekomendasi akan disesuaikan untuk Anda.', 'success')
        return redirect(url_for('main.index'))

    kategori_list = Kategori.get_all()

    # Load existing preferences jika ada
    existing_kat_ids = UserPreference.get_preferred_kategori_ids(current_user.id)
    existing_harga_min, existing_harga_max = UserPreference.get_price_range(current_user.id)
    existing_rating_min = UserPreference.get_rating_min(current_user.id)
    existing_sort_by = UserPreference.get_sort_by(current_user.id)

    return render_template('auth/onboarding.html',
                           kategori_list=kategori_list,
                           existing_kat_ids=existing_kat_ids,
                           existing_harga_min=existing_harga_min,
                           existing_harga_max=existing_harga_max,
                           existing_rating_min=existing_rating_min,
                           existing_sort_by=existing_sort_by)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.get_by_username(username)
        if user and user.verify_password(password):
            login_user(user)
            flash(f'Selamat datang, {user.nama_lengkap}!', 'success')

            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)

            # Cek apakah buyer belum isi preferensi → arahkan ke onboarding
            if user.role == 'buyer' and not UserPreference.has_preferences(user.id):
                return redirect(url_for('auth.onboarding'))

            # Redirect berdasarkan role
            if user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif user.role == 'seller':
                return redirect(url_for('seller.dashboard'))
            else:
                return redirect(url_for('main.index'))
        else:
            flash('Username atau password salah', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Anda telah logout', 'info')
    return redirect(url_for('main.index'))
