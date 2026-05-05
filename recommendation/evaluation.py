"""
Modul evaluasi model rekomendasi — MAE, RMSE, Precision@K, Recall@K, F1@K, NDCG@K.

Perubahan dari versi sebelumnya:
- NCF MAE/RMSE sekarang menggunakan model.predict() sesungguhnya (bukan hardcoded 3.5)
- Evaluasi KNN sekarang per-user (bukan 1 rekomendasi global)
- Ditambahkan NDCG@K untuk evaluasi ranking quality
"""

import numpy as np
import os
import json


def evaluate_predictions(actual_ratings, predicted_ratings):
    """
    Evaluasi prediksi dengan MAE dan RMSE.

    Args:
        actual_ratings: list of actual scores
        predicted_ratings: list of predicted scores

    Returns:
        dict: {'mae': float, 'rmse': float}
    """
    if not actual_ratings or not predicted_ratings:
        return {'mae': 0, 'rmse': 0}

    actual = np.array(actual_ratings, dtype=float)
    predicted = np.array(predicted_ratings, dtype=float)

    errors = actual - predicted
    mae = np.mean(np.abs(errors))
    rmse = np.sqrt(np.mean(errors ** 2))

    return {
        'mae': round(float(mae), 4),
        'rmse': round(float(rmse), 4)
    }


def precision_at_k(recommended_ids, relevant_ids, k=10):
    """
    Hitung Precision@K.

    Args:
        recommended_ids: list of produk_ids yang direkomendasikan
        relevant_ids: list of produk_ids yang relevan (rated >= 4)
        k: top-K items

    Returns:
        float: precision@k value
    """
    if not recommended_ids or not relevant_ids:
        return 0.0

    top_k = recommended_ids[:k]
    relevant_set = set(relevant_ids)
    hits = len([pid for pid in top_k if pid in relevant_set])

    return round(hits / k, 4) if k > 0 else 0.0


def recall_at_k(recommended_ids, relevant_ids, k=10):
    """Hitung Recall@K."""
    if not recommended_ids or not relevant_ids:
        return 0.0
    top_k = recommended_ids[:k]
    relevant_set = set(relevant_ids)
    hits = len([pid for pid in top_k if pid in relevant_set])
    return round(hits / len(relevant_set), 4) if relevant_set else 0.0


def f1_at_k(p_at_k, r_at_k):
    """Hitung F1@K dari Precision dan Recall."""
    if p_at_k + r_at_k == 0:
        return 0.0
    return round(2 * p_at_k * r_at_k / (p_at_k + r_at_k), 4)


def ndcg_at_k(recommended_ids, relevant_scores, k=10):
    """
    Hitung NDCG@K (Normalized Discounted Cumulative Gain).

    Args:
        recommended_ids: list of recommended produk_ids
        relevant_scores: dict {produk_id: actual_score} untuk semua produk relevan
        k: top-K items

    Returns:
        float: NDCG@k value
    """
    if not recommended_ids or not relevant_scores:
        return 0.0

    top_k = recommended_ids[:k]
    dcg = 0.0
    idcg = 0.0

    # DCG: discounted gain dari rekomendasi
    for i, pid in enumerate(top_k):
        if pid in relevant_scores:
            dcg += relevant_scores[pid] / np.log2(i + 2)  # i+2 karena index mulai dari 1

    # IDCG: ideal DCG (sorted by score descending)
    sorted_scores = sorted(relevant_scores.values(), reverse=True)[:k]
    for i, score in enumerate(sorted_scores):
        idcg += score / np.log2(i + 2)

    return round(dcg / idcg, 4) if idcg > 0 else 0.0


def _get_ncf_predictions(user_id, produk_ids):
    """
    Dapatkan prediksi rating NCF sesungguhnya dari model untuk pasangan
    (user, produk) menggunakan model.predict().

    Args:
        user_id: ID user
        produk_ids: list of produk_id yang ingin diprediksi

    Returns:
        dict: {produk_id: predicted_score (skala 1-5)} atau {} jika gagal
    """
    from config import NCF_MODEL_PATH
    from recommendation.ncf import NCF_MAPPINGS_PATH

    if not os.path.exists(NCF_MODEL_PATH) or not os.path.exists(NCF_MAPPINGS_PATH):
        return {}

    # Load mappings
    with open(NCF_MAPPINGS_PATH, 'r') as f:
        mappings = json.load(f)

    user_key = str(user_id)
    if user_key not in mappings['user_to_idx']:
        return {}

    user_idx = mappings['user_to_idx'][user_key]
    produk_to_idx = mappings['produk_to_idx']

    # Filter produk yang ada di model
    valid_pids = [pid for pid in produk_ids if str(pid) in produk_to_idx]
    if not valid_pids:
        return {}

    # Load model dan prediksi batch
    try:
        # Try keras first (TF 2.11+)
        try:
            from keras.models import load_model
        except ImportError:
            from tensorflow.keras.models import load_model
        
        model = load_model(NCF_MODEL_PATH)
    except Exception as e:
        print(f"⚠️  Cannot load model in _get_ncf_predictions: {e}")
        return {}
    
    try:
        import numpy as np
        user_array = np.array([user_idx] * len(valid_pids))
        produk_array = np.array([produk_to_idx[str(pid)] for pid in valid_pids])

        predictions = model.predict([user_array, produk_array], verbose=0).flatten()

        # Denormalize: sigmoid output [0,1] → rating [0,5]
        result = {}
        for pid, pred in zip(valid_pids, predictions):
            result[pid] = float(pred) * 5.0

        return result
    except Exception as e:
        print(f"⚠️  Error in prediction: {e}")
        return {}


def evaluate_knn(products_data, kategori_ids, test_ratings):
    """
    Evaluasi KNN per-user dengan pendekatan content-based.

    Untuk setiap user yang memiliki rating:
    - Gunakan kategori produk yang di-rating tinggi sebagai preferensi
    - Jalankan KNN personalized
    - Hitung Precision/Recall terhadap item relevan user tersebut
    - MAE/RMSE: avg_rating produk sebagai prediksi vs rating aktual

    Args:
        products_data: list of dict produk
        kategori_ids: list of kategori ids
        test_ratings: list of dict {'user_id', 'produk_id', 'score'}

    Returns:
        dict: metrik evaluasi
    """
    from recommendation.knn import knn_recommend, knn_recommend_personalized

    if len(test_ratings) < 2:
        return {
            'mae': 0, 'rmse': 0,
            'precision_at_5': 0, 'precision_at_10': 0,
            'recall_at_5': 0, 'recall_at_10': 0,
            'f1_at_5': 0, 'f1_at_10': 0,
            'ndcg_at_10': 0,
            'total_test': 0, 'evaluated_users': 0
        }

    # Kelompokkan rating per user
    user_map = {}
    for r in test_ratings:
        uid = r['user_id']
        if uid not in user_map:
            user_map[uid] = []
        user_map[uid].append(r)

    precision_5_list = []
    precision_10_list = []
    recall_5_list = []
    recall_10_list = []
    ndcg_10_list = []
    all_actual = []
    all_predicted = []

    prod_map = {p['id']: p for p in products_data}

    for uid, user_ratings in user_map.items():
        if len(user_ratings) < 2:
            continue

        # Item relevan user ini (score >= 4)
        relevant_ids = [r['produk_id'] for r in user_ratings if r['score'] >= 4]
        if not relevant_ids:
            continue

        # Buat preferensi virtual dari rating tinggi user → kategori favorit
        preferred_kat_ids = list(set(
            prod_map[r['produk_id']]['kategori_id']
            for r in user_ratings
            if r['score'] >= 4 and r['produk_id'] in prod_map
        ))

        # Jalankan KNN personalized berdasarkan preferensi user ini
        if preferred_kat_ids:
            recommended = knn_recommend_personalized(
                products_data, kategori_ids,
                preferred_kat_ids,
                n_recommendations=10
            )
        else:
            recommended = knn_recommend(products_data, kategori_ids, n_recommendations=10)

        if not recommended:
            continue

        # Precision/Recall per user
        p5 = precision_at_k(recommended, relevant_ids, k=5)
        p10 = precision_at_k(recommended, relevant_ids, k=10)
        r5 = recall_at_k(recommended, relevant_ids, k=5)
        r10 = recall_at_k(recommended, relevant_ids, k=10)
        precision_5_list.append(p5)
        precision_10_list.append(p10)
        recall_5_list.append(r5)
        recall_10_list.append(r10)

        # NDCG@10
        relevant_scores = {r['produk_id']: r['score'] for r in user_ratings if r['score'] >= 4}
        ndcg = ndcg_at_k(recommended, relevant_scores, k=10)
        ndcg_10_list.append(ndcg)

        # MAE/RMSE: avg_rating produk rekomendasi sebagai prediksi vs rating aktual user
        rated_map = {r['produk_id']: r['score'] for r in user_ratings}
        for pid in recommended:
            if pid in rated_map and pid in prod_map:
                all_actual.append(rated_map[pid])
                all_predicted.append(prod_map[pid].get('avg_rating', 3.0))

    pred_result = evaluate_predictions(all_actual, all_predicted) if all_actual else {'mae': 0, 'rmse': 0}

    p5_avg = round(float(np.mean(precision_5_list)), 4) if precision_5_list else 0
    p10_avg = round(float(np.mean(precision_10_list)), 4) if precision_10_list else 0
    r5_avg = round(float(np.mean(recall_5_list)), 4) if recall_5_list else 0
    r10_avg = round(float(np.mean(recall_10_list)), 4) if recall_10_list else 0
    ndcg_avg = round(float(np.mean(ndcg_10_list)), 4) if ndcg_10_list else 0

    return {
        'mae': pred_result['mae'],
        'rmse': pred_result['rmse'],
        'precision_at_5': p5_avg,
        'precision_at_10': p10_avg,
        'recall_at_5': r5_avg,
        'recall_at_10': r10_avg,
        'f1_at_5': f1_at_k(p5_avg, r5_avg),
        'f1_at_10': f1_at_k(p10_avg, r10_avg),
        'ndcg_at_10': ndcg_avg,
        'total_test': len(test_ratings),
        'evaluated_users': len(precision_5_list)
    }


def evaluate_ncf(user_ids, all_ratings):
    """
    Evaluasi NCF per-user menggunakan prediksi model sesungguhnya.

    Untuk setiap user:
    - Ambil item yang sudah di-rating
    - Dapatkan rekomendasi NCF (exclude rated items)
    - Hitung Precision/Recall terhadap item relevan
    - MAE/RMSE: gunakan model.predict() vs rating aktual (BUKAN hardcoded)

    Args:
        user_ids: list of user_id
        all_ratings: list of dict {'user_id', 'produk_id', 'score'}

    Returns:
        dict: metrik evaluasi atau None jika model belum ada
    """
    from recommendation.ncf import ncf_recommend
    from config import NCF_MODEL_PATH

    if not os.path.exists(NCF_MODEL_PATH):
        return None

    actual_scores = []
    predicted_scores = []
    precision_5_list = []
    precision_10_list = []
    recall_5_list = []
    recall_10_list = []
    ndcg_10_list = []

    for uid in user_ids:
        user_ratings = [r for r in all_ratings if r['user_id'] == uid]
        if len(user_ratings) < 3:
            continue

        rated_ids = [r['produk_id'] for r in user_ratings]
        all_produk_ids = list(set(r['produk_id'] for r in all_ratings))

        recommended = ncf_recommend(uid, all_produk_ids, rated_ids, n_recommendations=10)
        if not recommended:
            continue

        relevant = [r['produk_id'] for r in user_ratings if r['score'] >= 4]

        # Precision/Recall
        p5 = precision_at_k(recommended, relevant, k=5)
        p10 = precision_at_k(recommended, relevant, k=10)
        r5 = recall_at_k(recommended, relevant, k=5)
        r10 = recall_at_k(recommended, relevant, k=10)
        precision_5_list.append(p5)
        precision_10_list.append(p10)
        recall_5_list.append(r5)
        recall_10_list.append(r10)

        # NDCG@10
        relevant_scores = {r['produk_id']: r['score'] for r in user_ratings if r['score'] >= 4}
        ndcg = ndcg_at_k(recommended, relevant_scores, k=10)
        ndcg_10_list.append(ndcg)

        # MAE/RMSE: gunakan model.predict() sesungguhnya
        rated_map = {r['produk_id']: r['score'] for r in user_ratings}
        ncf_predictions = _get_ncf_predictions(uid, list(rated_map.keys()))
        for pid, actual_score in rated_map.items():
            if pid in ncf_predictions:
                actual_scores.append(actual_score)
                predicted_scores.append(ncf_predictions[pid])

    pred_result = evaluate_predictions(actual_scores, predicted_scores) if actual_scores else {'mae': 0, 'rmse': 0}

    p5_avg = round(float(np.mean(precision_5_list)), 4) if precision_5_list else 0
    p10_avg = round(float(np.mean(precision_10_list)), 4) if precision_10_list else 0
    r5_avg = round(float(np.mean(recall_5_list)), 4) if recall_5_list else 0
    r10_avg = round(float(np.mean(recall_10_list)), 4) if recall_10_list else 0
    ndcg_avg = round(float(np.mean(ndcg_10_list)), 4) if ndcg_10_list else 0

    return {
        'mae': pred_result['mae'],
        'rmse': pred_result['rmse'],
        'precision_at_5': p5_avg,
        'precision_at_10': p10_avg,
        'recall_at_5': r5_avg,
        'recall_at_10': r10_avg,
        'f1_at_5': f1_at_k(p5_avg, r5_avg),
        'f1_at_10': f1_at_k(p10_avg, r10_avg),
        'ndcg_at_10': ndcg_avg,
        'total_users': len(user_ids),
        'evaluated_users': len(precision_5_list)
    }
