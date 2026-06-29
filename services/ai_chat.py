"""
services/ai_chat.py
Chatbot AI untuk UMKM Kendari — sekarang pakai Groq API (bukan rule-based lagi).

Kontrak fungsi get_ai_response() HARUS tetap punya parameter ini karena
routes/n8n_api.py melakukan inspect.signature() untuk cek parameter yang ada:

    get_ai_response(message, system_prompt=None, conversation_id=None, seller_id=None)

Cara kerja:
1. Ambil/buat riwayat chat per conversation_id (disimpan in-memory).
2. Susun messages: [system_prompt] + riwayat lama + pesan baru.
3. Kirim ke Groq (endpoint OpenAI-compatible).
4. Simpan balasan ke riwayat, lalu return teks jawabannya.

ENV yang dibutuhkan (taruh di .env atau export manual):
    GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx     <- wajib, ambil dari https://console.groq.com/keys
    GROQ_MODEL=llama-3.3-70b-versatile        <- opsional, default di bawah
"""

import os
import requests
import logging

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Berapa banyak pasangan (user+assistant) yang diingat per percakapan.
# Lebih besar = lebih "ingat", tapi lebih mahal & lebih lambat per request.
MAX_HISTORY_TURNS = 6

# Riwayat chat in-memory: { conversation_id: [ {role, content}, ... ] }
# CATATAN: ini hilang kalau server di-restart. Kalau mau persist,
# bisa disimpan ke tabel sqlite pakai models.database.get_db().
_conversation_history: dict[str, list[dict]] = {}

DEFAULT_SYSTEM_PROMPT = (
    "Kamu adalah asisten virtual WhatsApp untuk UMKM Kendari. "
    "Jawab pertanyaan pelanggan dengan ramah, singkat, dan jelas dalam Bahasa Indonesia. "
    "Jika tidak tahu jawabannya, katakan dengan jujur, jangan mengarang."
)


def _trim_history(history: list[dict]) -> list[dict]:
    """Potong riwayat supaya tidak membengkak — simpan N pasangan terakhir saja."""
    max_messages = MAX_HISTORY_TURNS * 2
    if len(history) > max_messages:
        return history[-max_messages:]
    return history


def get_ai_response(
    message: str,
    system_prompt: str | None = None,
    conversation_id: str | None = None,
    seller_id: int | None = None,
) -> str:
    """
    Kirim pesan ke Groq dan kembalikan jawaban (string).

    Args:
        message: pesan dari pelanggan.
        system_prompt: instruksi/konteks UMKM (dari n8n_api.get_umkm_info), opsional.
        conversation_id: ID unik percakapan (mis. "n8n:628xxx:628yyy") untuk
                          menjaga history per pelanggan per toko.
        seller_id: ID UMKM, disertakan untuk kompatibilitas signature
                   (belum dipakai langsung, tapi bisa dipakai nanti misal
                   untuk logging atau rate-limit per toko).
    """
    if not GROQ_API_KEY:
        logger.error("GROQ_API_KEY belum di-set di environment variable.")
        return "Maaf, layanan chatbot AI belum dikonfigurasi (API key belum ada)."

    conv_key = conversation_id or "default"
    history = _conversation_history.get(conv_key, [])

    messages = [{"role": "system", "content": system_prompt or DEFAULT_SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})

    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": 0.6,
        "max_tokens": 512,
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=20)
    except requests.exceptions.Timeout:
        logger.warning("Groq API timeout untuk conversation_id=%s", conv_key)
        return "Maaf, balasan AI agak lama. Boleh coba kirim ulang pertanyaannya?"
    except requests.exceptions.RequestException as e:
        logger.error("Groq API request error: %s", e)
        return "Maaf, sedang ada gangguan koneksi ke layanan AI. Coba lagi sebentar ya."

    if resp.status_code != 200:
        logger.error("Groq API error %s: %s", resp.status_code, resp.text[:500])
        # 401 = API key salah/expired, 404 = nama model salah/deprecated,
        # 429 = rate limit kena.
        if resp.status_code == 401:
            return "Maaf, ada masalah autentikasi ke layanan AI (API key)."
        if resp.status_code == 404:
            return "Maaf, model AI yang dipakai sedang tidak tersedia."
        if resp.status_code == 429:
            return "Maaf, layanan AI sedang sibuk. Coba lagi sebentar ya."
        return "Maaf, layanan chatbot AI sedang gangguan. Coba lagi nanti."

    try:
        data = resp.json()
        reply = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, ValueError) as e:
        logger.error("Gagal parse response Groq: %s | raw=%s", e, resp.text[:500])
        return "Maaf, terjadi kesalahan saat memproses jawaban AI."

    # Simpan ke history (in-memory) lalu trim
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": reply})
    _conversation_history[conv_key] = _trim_history(history)

    return reply


def reset_conversation(conversation_id: str) -> None:
    """Hapus riwayat chat untuk satu conversation_id (mis. dipanggil endpoint /n8n/reset)."""
    _conversation_history.pop(conversation_id, None)


if __name__ == "__main__":
    # Test cepat dari terminal: python services/ai_chat.py
    # Pastikan GROQ_API_KEY sudah di-export dulu.
    print(get_ai_response("ada produk kopi ga?", conversation_id="test:manual"))