import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

SECRET_KEY = os.environ.get('SECRET_KEY', 'umkm-kendari-secret-key-2026')
DATABASE = os.path.join(BASE_DIR, 'umkm_kendari.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB max upload

NCF_MODEL_PATH = os.path.join(BASE_DIR, 'recommendation', 'saved_model', 'ncf_model.keras')
NCF_MIN_RATINGS = 3  # Minimum rating sebelum menggunakan NCF
KNN_N_NEIGHBORS = 10

# ============ GEMINI AI CONFIG ============
# Dapatkan API Key gratis di: https://aistudio.google.com/apikey
# Lalu set environment variable: set GEMINI_API_KEY=AIza...
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
GEMINI_MODEL = 'gemini-flash-latest'
AI_ENABLED = bool(GEMINI_API_KEY)   # Otomatis aktif jika API key tersedia
