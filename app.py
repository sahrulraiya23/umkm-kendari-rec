"""
Sistem Rekomendasi Produk UMKM Kota Kendari
Flask Application Entry Point

Algoritma:
- KNN (K-Nearest Neighbor) untuk cold-start
- NCF (Neural Collaborative Filtering) setelah user memberi rating
"""

import os
from flask import Flask
from flask_login import LoginManager
from config import SECRET_KEY, DATABASE, UPLOAD_FOLDER
from models.database import init_db, close_db, get_db
from models.user import User
from datetime import datetime


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = SECRET_KEY
    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB

    # Pastikan folder upload ada
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # Inisialisasi database jika belum ada
    if not os.path.exists(DATABASE):
        init_db()

    # Setup Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Silakan login terlebih dahulu'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        return User.get_by_id(int(user_id))

    # Tutup koneksi DB setelah request
    app.teardown_appcontext(close_db)

    # Register Blueprints
    from routes.auth import auth_bp
    from routes.main import main_bp
    from routes.admin import admin_bp
    from routes.seller import seller_bp
    from routes.api import api_bp
    from routes.n8n_api import n8n_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(seller_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(n8n_bp)  # Endpoint integrasi n8n

    # Custom Jinja2 filter untuk strftime
    @app.template_filter('strftime')
    def strftime_filter(value, format_string):
        """Format datetime object menggunakan strftime."""
        if isinstance(value, str):
            if value.lower() == 'now':
                value = datetime.now()
            else:
                try:
                    value = datetime.fromisoformat(value)
                except:
                    return value
        if isinstance(value, datetime):
            return value.strftime(format_string)
        return value

    # Template context processor
    @app.context_processor
    def inject_globals():
        return {
            'app_name': 'UMKM Kendari',
            'now': datetime.now()
        }

    return app


if __name__ == '__main__':
    app = create_app()
    print("=" * 50)
    print("  Sistem Rekomendasi Produk UMKM Kota Kendari")
    print("  http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)
