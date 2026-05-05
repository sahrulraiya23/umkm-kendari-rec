from flask import Blueprint, jsonify
from flask_login import current_user
from recommendation.engine import get_recommendations
from models.produk import Produk

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/recommendations')
def api_recommendations():
    """API endpoint untuk mendapatkan rekomendasi."""
    user_id = current_user.id if current_user.is_authenticated else None
    result = get_recommendations(user_id, n=8)

    products = Produk.get_by_ids(result['products'])
    products_data = [{
        'id': p.id,
        'nama': p.nama,
        'harga': p.harga,
        'gambar': p.gambar,
        'kategori': p.kategori_nama,
        'avg_rating': round(p.avg_rating, 1),
        'total_rating': p.total_rating
    } for p in products]

    return jsonify({
        'success': True,
        'method': result['method'],
        'reason': result['reason'],
        'products': products_data
    })
