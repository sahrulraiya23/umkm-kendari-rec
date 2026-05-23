"""
services/ai_chat.py
Modul integrasi Gemini AI untuk chatbot UMKM Kota Kendari.
Sekarang menggunakan pendekatan Full Gemini dengan Function Calling.
"""

import google.generativeai as genai
from config import GEMINI_API_KEY, GEMINI_MODEL
from models.database import get_db

# Inisialisasi Gemini satu kali (singleton pattern)
_model = None


def cek_stok_produk(nama_produk: str) -> str:
    """
    Mengecek ketersediaan stok produk di UMKM Kendari berdasarkan namanya. 
    Panggil fungsi ini secara otomatis jika pengguna menanyakan ketersediaan, stok, atau sisa produk tertentu.
    """
    try:
        db = get_db()
        rows = db.execute('''
            SELECT p.nama, p.harga, p.stok, p.tersedia, k.nama as kategori_nama
            FROM produk p
            LEFT JOIN kategori k ON p.kategori_id = k.id
            WHERE p.nama LIKE ? OR p.deskripsi LIKE ?
            ORDER BY p.stok DESC
            LIMIT 5
        ''', (f'%{nama_produk}%', f'%{nama_produk}%')).fetchall()
        
        if not rows:
            return f"Produk dengan kata kunci '{nama_produk}' tidak ditemukan di katalog UMKM Kendari."
        
        results = []
        for r in rows:
            stok = int(r['stok'])
            tersedia = "Tersedia" if int(r['tersedia']) == 1 and stok > 0 else "Kosong/Habis"
            results.append(f"- {r['nama']} (Kategori: {r['kategori_nama']}): Rp{r['harga']}, Stok: {stok} ({tersedia})")
        return "Data stok dari database UMKM Kendari:\n" + "\n".join(results)
    except Exception as e:
        return f"Gagal mengambil data stok: {str(e)}"

def cek_jadwal_toko() -> str:
    """
    Mengecek jadwal operasional atau jam buka platform toko UMKM Kendari. 
    Panggil fungsi ini jika pengguna menanyakan jam buka, kapan toko buka/tutup, atau hari operasional.
    """
    try:
        db = get_db()
        rows = db.execute('''
            SELECT hari_nama, buka_jam, tutup_jam, is_open
            FROM operasional_toko
            ORDER BY hari_index ASC
        ''').fetchall()
        if not rows:
            return "Jadwal operasional: Senin - Sabtu: 08:00 - 17:00 WITA. Minggu: Libur."
        
        lines = []
        for row in rows:
            if int(row['is_open']) == 1:
                lines.append(f"{row['hari_nama']}: {row['buka_jam']} - {row['tutup_jam']} WITA")
            else:
                lines.append(f"{row['hari_nama']}: Libur")
        return "Jadwal Operasional Resmi Platform UMKM Kendari:\n" + "\n".join(lines)
    except Exception as e:
        return "Jadwal operasional standar: Senin-Sabtu 08:00-17:00 WITA. Minggu Libur."


def _get_model():
    """Lazy-load model Gemini dengan tools Function Calling."""
    global _model
    if _model is None:
        genai.configure(api_key=GEMINI_API_KEY)
        _model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=_build_system_prompt(),
            tools=[cek_stok_produk, cek_jadwal_toko]
        )
    return _model


def _build_system_prompt() -> str:
    """
    Membangun system prompt yang menjelaskan konteks UMKM Kendari.
    """
    return """
Kamu adalah asisten virtual cerdas untuk platform **UMKM Kota Kendari** — 
sebuah marketplace produk lokal dari Kota Kendari, Sulawesi Tenggara, Indonesia.

## Identitasmu
- Nama: Asisten UMKM Kendari
- Bahasa: Bahasa Indonesia yang ramah, santai, dan mudah dipahami
- Karakter: Helpful, jujur, dan selalu membantu dengan antusias

## Tugasmu
1. Membantu pengguna menemukan produk UMKM lokal yang sesuai kebutuhan mereka.
2. Menjawab pertanyaan tentang ketersediaan produk dan jadwal toko dengan memanggil fungsi yang tersedia (Tools).
3. Memberikan saran dan rekomendasi produk lokal Kendari yang relevan.
4. Menolak menjawab jika pertanyaan di luar topik (misal: politik, agama, atau ngoding).

## Format Jawaban
- Singkat, padat, dan ramah.
- Gunakan emoji secukupnya.
- Berikan informasi stok dan jadwal dengan gaya bahasa yang enak dibaca (jangan seperti robot).
""".strip()


def get_ai_response(user_message: str, extra_context: str = '') -> str:
    """
    Mengirim pesan user ke Gemini dengan mode Chat (mendukung Automatic Function Calling).
    """
    try:
        model = _get_model()
        
        # Mulai sesi chat yang mendukung pemanggilan fungsi otomatis
        chat = model.start_chat(enable_automatic_function_calling=True)

        prompt = user_message
        if extra_context:
            prompt = f"{user_message}\n\n[Informasi tambahan: {extra_context}]"

        response = chat.send_message(prompt)

        if response and response.text:
            return response.text.strip()

        return 'Maaf, saya tidak dapat memproses pertanyaan Anda saat ini. Coba lagi ya! 🙏'

    except Exception as e:
        error_msg = str(e).lower()
        if 'api_key' in error_msg or 'invalid' in error_msg or 'credential' in error_msg:
            return 'Maaf, konfigurasi AI sedang bermasalah. Silakan hubungi admin. 🙏'
        elif 'quota' in error_msg or 'limit' in error_msg or 'resource' in error_msg:
            return 'Maaf, layanan AI sedang sibuk. Coba lagi dalam beberapa saat ya! ⏳'
        elif 'network' in error_msg or 'connection' in error_msg or 'timeout' in error_msg:
            return 'Maaf, koneksi ke layanan AI terputus. Pastikan internet Anda stabil. 🌐'
        else:
            print(f"[AI Error] {type(e).__name__}: {e}")
            return 'Hmm, saya sedang mengalami gangguan teknis. Coba tanyakan hal lain ya! 😅'
