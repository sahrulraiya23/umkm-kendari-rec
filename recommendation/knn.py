"""
Algoritma K-Nearest Neighbor (KNN) untuk Cold-Start Problem.

Digunakan ketika user baru belum memiliki rating.
Menghitung Cosine Similarity antar produk berdasarkan fitur:
- Kategori (one-hot encoding)
- Harga (normalized)
- Rating rata-rata (normalized)

Jika user sudah mengisi preferensi (onboarding), KNN akan membuat
"virtual user profile" dari preferensi tersebut dan mencocokkan
dengan produk menggunakan Cosine Similarity.

Preferensi yang didukung:
- kategori_ids: list kategori favorit
- harga_min/harga_max: range harga
- rating_min: rating minimum produk (1-5)
- sort_by: urutan hasil ('rating', 'harga_asc', 'harga_desc', 'terbaru')

Alur KNN:
1. Data produk diambil dari DB (hanya yang tersedia/stok > 0)
2. Feature matrix dibangun dari kategori (one-hot), harga, dan avg_rating
3. Untuk cold-start generic → anchor = produk top-rated, cari K tetangga
4. Untuk personalized → virtual user profile, cosine similarity ke semua produk
5. Untuk produk serupa → cosine similarity dari produk tertentu ke semua lainnya
"""

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler


def build_product_features(products_data, kategori_ids):
    """
    Membuat feature matrix untuk semua produk.

    Args:
        products_data: list of dict {'id', 'harga', 'kategori_id', 'avg_rating', 'total_rating'}
        kategori_ids: list of semua kategori id unik

    Returns:
        product_ids: list of product ids
        feature_matrix: numpy array (n_products, n_features)
    """
    if not products_data:
        return [], np.array([])

    product_ids = [p['id'] for p in products_data]
    n_products = len(products_data)
    n_kategori = len(kategori_ids)

    # Feature: one-hot kategori + harga normalized + avg_rating normalized
    n_features = n_kategori + 2  # kategori + harga + avg_rating 
    feature_matrix = np.zeros((n_products, n_features))

    # Kategori one-hot encoding
    kategori_id_to_idx = {kid: idx for idx, kid in enumerate(kategori_ids)}
    for i, p in enumerate(products_data):
        if p['kategori_id'] in kategori_id_to_idx:
            feature_matrix[i, kategori_id_to_idx[p['kategori_id']]] = 1.0

    # Harga normalized
    harga_values = np.array([p['harga'] for p in products_data]).reshape(-1, 1)
    if harga_values.max() > harga_values.min():
        scaler = MinMaxScaler()
        harga_normalized = scaler.fit_transform(harga_values).flatten()
    else:
        harga_normalized = np.zeros(n_products)
    feature_matrix[:, n_kategori] = harga_normalized

    # Avg rating normalized (0-5 → 0-1)
    avg_ratings = np.array([p.get('avg_rating', 0) for p in products_data])
    feature_matrix[:, n_kategori + 1] = avg_ratings / 5.0

    # Catatan: sklearn cosine_similarity() sudah menangani normalisasi L2
    # secara internal, sehingga tidak perlu normalisasi manual di sini.

    return product_ids, feature_matrix


def build_user_profile_vector(preferred_kategori_ids, harga_min, harga_max,
                               kategori_ids, all_harga_values, rating_min=3.0):
    """
    Membuat virtual user profile vector dari preferensi onboarding.
    Vector ini memiliki dimensi yang sama dengan product feature vector,
    sehingga bisa dihitung Cosine Similarity-nya.

    Args:
        preferred_kategori_ids: list kategori_id yang dipilih user
        harga_min: harga minimum preferensi
        harga_max: harga maksimum preferensi
        kategori_ids: semua kategori ids (untuk indexing)
        all_harga_values: semua harga produk (untuk normalisasi)
        rating_min: rating minimum produk yang diinginkan (1-5)

    Returns:
        user_vector: numpy array (1, n_features)
    """
    n_kategori = len(kategori_ids)
    n_features = n_kategori + 2
    user_vector = np.zeros(n_features)

    # One-hot kategori yang dipilih user (normalize jika multiple)
    kategori_id_to_idx = {kid: idx for idx, kid in enumerate(kategori_ids)}
    if preferred_kategori_ids:
        weight = 1.0 / len(preferred_kategori_ids)  # Equal weight for each preferred category
        for kat_id in preferred_kategori_ids:
            if kat_id in kategori_id_to_idx:
                user_vector[kategori_id_to_idx[kat_id]] = weight

    # Harga: normalize titik tengah range user
    if all_harga_values.max() > all_harga_values.min():
        # Hitung midpoint budget user
        effective_max = min(harga_max, all_harga_values.max())
        midpoint = (harga_min + effective_max) / 2.0
        # Normalize ke skala yang sama
        normalized = (midpoint - all_harga_values.min()) / (all_harga_values.max() - all_harga_values.min())
        user_vector[n_kategori] = max(0, min(1, normalized))
    else:
        user_vector[n_kategori] = 0.5

    # Rating min: normalize ke 0-1 (user ingin produk dengan rating >= rating_min)
    user_vector[n_kategori + 1] = max(0.0, min(1.0, rating_min / 5.0))

    # Catatan: tidak perlu L2 normalize — cosine_similarity() menangani ini.

    return user_vector.reshape(1, -1)


def _apply_sort(recommended_ids, products_data, sort_by):
    """
    Urutkan daftar produk berdasarkan preferensi sort_by.

    Args:
        recommended_ids: list of product ids (urutan sudah berdasarkan similarity)
        products_data: list of dict produk
        sort_by: 'rating' | 'harga_asc' | 'harga_desc' | 'terbaru'

    Returns:
        sorted list of product ids
    """
    if sort_by == 'rating':
        # Urut berdasarkan avg_rating desc, lalu total_rating desc
        prod_map = {p['id']: p for p in products_data}
        return sorted(
            recommended_ids,
            key=lambda pid: (
                prod_map.get(pid, {}).get('avg_rating', 0),
                prod_map.get(pid, {}).get('total_rating', 0)
            ),
            reverse=True
        )
    elif sort_by == 'harga_asc':
        prod_map = {p['id']: p for p in products_data}
        return sorted(recommended_ids, key=lambda pid: prod_map.get(pid, {}).get('harga', 0))
    elif sort_by == 'harga_desc':
        prod_map = {p['id']: p for p in products_data}
        return sorted(recommended_ids, key=lambda pid: prod_map.get(pid, {}).get('harga', 0), reverse=True)
    elif sort_by == 'terbaru':
        # Urut berdasarkan id desc (id lebih besar = lebih baru)
        return sorted(recommended_ids, reverse=True)
    # Default: kembalikan urutan similarity
    return recommended_ids


def knn_recommend_personalized(products_data, kategori_ids, preferred_kategori_ids,
                                harga_min=0, harga_max=999999999,
                                rating_min=3.0, sort_by='rating',
                                n_recommendations=8, k_neighbors=10):
    """
    KNN Personalized Recommendation berdasarkan preferensi user.

    Langkah:
    1. Buat feature matrix semua produk
    2. Buat virtual user profile dari preferensi (kategori, harga, rating_min)
    3. Hitung Cosine Similarity antara user profile dan semua produk
    4. Filter produk berdasarkan range harga dan rating_min
    5. Urutkan sesuai sort_by
    6. Return top-N produk paling mirip

    Args:
        products_data: list of dict dari database
        kategori_ids: list of kategori_ids
        preferred_kategori_ids: kategori yang dipilih user saat onboarding
        harga_min: minimum harga preferensi
        harga_max: maximum harga preferensi
        rating_min: rating minimum produk yang diinginkan (1-5)
        sort_by: urutan rekomendasi ('rating', 'harga_asc', 'harga_desc', 'terbaru')
        n_recommendations: jumlah rekomendasi
        k_neighbors: jumlah tetangga KNN

    Returns:
        list of produk_ids yang direkomendasikan
    """
    if not products_data or len(products_data) < 2:
        return [p['id'] for p in products_data] if products_data else []

    product_ids, feature_matrix = build_product_features(products_data, kategori_ids)

    if feature_matrix.size == 0:
        return []

    # Buat user profile vector
    all_harga = np.array([p['harga'] for p in products_data])
    user_vector = build_user_profile_vector(
        preferred_kategori_ids, harga_min, harga_max,
        kategori_ids, all_harga, rating_min
    )

    # Hitung Cosine Similarity antara user profile vs semua produk
    similarities = cosine_similarity(user_vector, feature_matrix).flatten()

    # Penalti produk di luar range harga
    for i, p in enumerate(products_data):
        if p['harga'] < harga_min or p['harga'] > harga_max:
            similarities[i] *= 0.3

    # Penalti produk dengan rating di bawah rating_min
    for i, p in enumerate(products_data):
        avg_r = p.get('avg_rating', 0)
        if avg_r > 0 and avg_r < rating_min:
            similarities[i] *= 0.5

    # Sort by similarity descending
    sorted_indices = np.argsort(similarities)[::-1]

    recommended = []
    for idx in sorted_indices:
        recommended.append(product_ids[idx])
        if len(recommended) >= n_recommendations:
            break

    # Terapkan preferensi urutan
    recommended = _apply_sort(recommended, products_data, sort_by)

    return recommended[:n_recommendations]


def knn_recommend(products_data, kategori_ids, n_recommendations=8, k_neighbors=10):
    """
    KNN Cold-Start Recommendation (tanpa preferensi user).

    Langkah:
    1. Buat feature matrix semua produk
    2. Hitung cosine similarity antar produk
    3. Ambil produk dengan rating terbaik sebagai anchor
    4. Cari K tetangga terdekat dari anchor
    5. Return top-N produk

    Args:
        products_data: list of dict dari database
        kategori_ids: list of kategori ids
        n_recommendations: jumlah rekomendasi
        k_neighbors: jumlah tetangga KNN

    Returns:
        list of produk_ids yang direkomendasikan
    """
    if not products_data or len(products_data) < 2:
        return [p['id'] for p in products_data] if products_data else []

    product_ids, feature_matrix = build_product_features(products_data, kategori_ids)

    if feature_matrix.size == 0:
        return []

    # Hitung Cosine Similarity matrix
    similarity_matrix = cosine_similarity(feature_matrix)

    # Cari anchor: produk dengan Bayesian confidence score tertinggi
    scores = []
    for p in products_data:
        avg_r = p.get('avg_rating', 0)
        total_r = p.get('total_rating', 0)
        # Bayesian confidence: balance rating dengan jumlah rating
        min_ratings = 2  # Minimum ratings untuk confidence
        global_avg = 3.5  # Global average rating
        confidence = total_r / (total_r + min_ratings)
        score = confidence * avg_r + (1 - confidence) * global_avg
        scores.append(score)

    scores = np.array(scores)

    # Jika tidak ada produk dengan rating, gunakan semua produk secara acak
    if scores.max() == 0:
        # Deterministik: urutkan berdasarkan produk terbaru (created_at desc)
        sorted_by_recency = sorted(
            range(len(products_data)),
            key=lambda i: products_data[i].get('created_at', ''),
            reverse=True
        )
        return [product_ids[i] for i in sorted_by_recency[:n_recommendations]]

    # Ambil top anchor products
    n_anchors = min(3, len(product_ids))
    anchor_indices = np.argsort(scores)[-n_anchors:][::-1]

    # Kumpulkan semua tetangga dari anchor
    recommended_set = set()
    for anchor_idx in anchor_indices:
        similarities = similarity_matrix[anchor_idx]
        # Sort by similarity descending, skip self
        neighbor_indices = np.argsort(similarities)[::-1]

        k = min(k_neighbors, len(neighbor_indices))
        for idx in neighbor_indices[:k]:
            if idx != anchor_idx:
                recommended_set.add(product_ids[idx])

            if len(recommended_set) >= n_recommendations:
                break

        if len(recommended_set) >= n_recommendations:
            break

    # Tambahkan anchor juga jika belum cukup
    for anchor_idx in anchor_indices:
        recommended_set.add(product_ids[anchor_idx])
        if len(recommended_set) >= n_recommendations:
            break

    return list(recommended_set)[:n_recommendations]


def knn_recommend_similar(target_produk_id, products_data, kategori_ids,
                          n_recommendations=4):
    """
    Cari produk yang mirip dengan produk tertentu menggunakan Cosine Similarity.
    Digunakan di halaman detail produk untuk menampilkan "Produk Serupa".

    Langkah:
    1. Buat feature matrix semua produk
    2. Cari index produk target
    3. Hitung Cosine Similarity antara produk target vs semua produk
    4. Return top-N produk yang paling mirip (selain dirinya sendiri)

    Args:
        target_produk_id: ID produk yang sedang dilihat
        products_data: list of dict dari database
        kategori_ids: list of kategori ids
        n_recommendations: jumlah produk serupa

    Returns:
        list of produk_ids yang mirip
    """
    if not products_data or len(products_data) < 2:
        return []

    product_ids, feature_matrix = build_product_features(products_data, kategori_ids)

    if feature_matrix.size == 0:
        return []

    # Cari index produk target
    try:
        target_idx = product_ids.index(target_produk_id)
    except ValueError:
        # Produk target tidak ditemukan di data, fallback ke generic
        return knn_recommend(products_data, kategori_ids, n_recommendations)

    # Hitung similarity antara target vs semua produk
    target_vector = feature_matrix[target_idx].reshape(1, -1)
    similarities = cosine_similarity(target_vector, feature_matrix).flatten()

    # Sort by similarity descending, skip self
    sorted_indices = np.argsort(similarities)[::-1]

    recommended = []
    for idx in sorted_indices:
        if product_ids[idx] != target_produk_id:
            recommended.append(product_ids[idx])
        if len(recommended) >= n_recommendations:
            break

    return recommended


def get_knn_data_from_db(include_unavailable=False):
    """
    Ambil data produk dari database untuk KNN.
    
    Args:
        include_unavailable: jika True, ambil semua produk termasuk yang tidak tersedia.
                            Default False (hanya produk yang tersedia dan stok > 0).
    
    Returns:
        products_data: list of dict produk
        kategori_ids: list of kategori ids
    """
    from models.database import get_db
    db = get_db()

    query = '''
        SELECT p.id, p.harga, p.kategori_id, p.created_at,
               COALESCE(AVG(r.score), 0) as avg_rating,
               COUNT(r.id) as total_rating
        FROM produk p
        LEFT JOIN ratings r ON p.id = r.produk_id
    '''
    if not include_unavailable:
        query += ' WHERE p.tersedia = 1 AND p.stok > 0'
    
    query += ' GROUP BY p.id'

    products = db.execute(query).fetchall()
    products_data = [dict(p) for p in products]

    kategori_rows = db.execute('SELECT id FROM kategori ORDER BY id').fetchall()
    kategori_ids = [row['id'] for row in kategori_rows]

    return products_data, kategori_ids