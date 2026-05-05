"""
Neural Collaborative Filtering (NCF) untuk Rekomendasi Produk.

Arsitektur: GMF (Generalized Matrix Factorization) + MLP (Multi-Layer Perceptron)
digabung di layer akhir untuk prediksi rating.

Digunakan setelah user memiliki cukup rating (>= NCF_MIN_RATINGS).
"""

import os
import numpy as np
import json

# Suppress TF warningsz
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

NCF_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'saved_model', 'ncf_model.keras')
NCF_MAPPINGS_PATH = os.path.join(os.path.dirname(__file__), 'ncf_mappings.json')


def build_ncf_model(n_users, n_products, embedding_dim=64, mlp_layers=None):
    """
    Membangun arsitektur NCF (GMF + MLP) dengan hyperparameter optimal.

    Args:
        n_users: jumlah user unik
        n_products: jumlah produk unik
        embedding_dim: dimensi embedding (default: 64 untuk representasi lebih baik)
        mlp_layers: list ukuran hidden layers MLP (default: [128, 64, 32])

    Returns:
        model: Keras model
    """
    if mlp_layers is None:
        mlp_layers = [128, 64, 32]
    try:
        import tensorflow as tf
        from tensorflow import keras
        from tensorflow.keras import layers
    except ImportError:
        print("TensorFlow tidak tersedia. NCF tidak dapat digunakan.")
        return None

    # Input layers
    user_input = keras.Input(shape=(1,), name='user_input')
    product_input = keras.Input(shape=(1,), name='product_input')

    # === GMF Branch ===
    gmf_user_embedding = layers.Embedding(n_users, embedding_dim, 
                                         embeddings_regularizer=tf.keras.regularizers.l2(0.0005),
                                         name='gmf_user_emb')(user_input)
    gmf_user_embedding = layers.Flatten()(gmf_user_embedding)

    gmf_product_embedding = layers.Embedding(n_products, embedding_dim, 
                                            embeddings_regularizer=tf.keras.regularizers.l2(0.0005),
                                            name='gmf_product_emb')(product_input)
    gmf_product_embedding = layers.Flatten()(gmf_product_embedding)

    gmf_output = layers.Multiply()([gmf_user_embedding, gmf_product_embedding])

    # === MLP Branch ===
    mlp_user_embedding = layers.Embedding(n_users, embedding_dim, 
                                         embeddings_regularizer=tf.keras.regularizers.l2(0.0005),
                                         name='mlp_user_emb')(user_input)
    mlp_user_embedding = layers.Flatten()(mlp_user_embedding)

    mlp_product_embedding = layers.Embedding(n_products, embedding_dim, 
                                            embeddings_regularizer=tf.keras.regularizers.l2(0.0005),
                                            name='mlp_product_emb')(product_input)
    mlp_product_embedding = layers.Flatten()(mlp_product_embedding)

    mlp_concat = layers.Concatenate()([mlp_user_embedding, mlp_product_embedding])

    for i, units in enumerate(mlp_layers):
        mlp_concat = layers.Dense(units, activation='relu', 
                                 kernel_regularizer=tf.keras.regularizers.l2(0.0005),
                                 name=f'mlp_dense_{i}')(mlp_concat)
        mlp_concat = layers.Dropout(0.1)(mlp_concat)

    # === Gabungkan GMF + MLP ===
    combined = layers.Concatenate()([gmf_output, mlp_concat])
    combined = layers.Dense(32, activation='relu', 
                           kernel_regularizer=tf.keras.regularizers.l2(0.0005),
                           name='combined_dense')(combined)
    output = layers.Dense(1, activation='sigmoid', name='output')(combined)

    model = keras.Model(inputs=[user_input, product_input], outputs=output)
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=0.0005),
        loss='mean_squared_error',
        metrics=['mae']
    )

    return model


def train_ncf_model(ratings_data, epochs=50):
    """
    Training model NCF dengan data rating dari database.

    Args:
        ratings_data: list of dict {'user_id', 'produk_id', 'score'}

    Returns:
        dict: hasil training {'success', 'message', 'history'}
    """
    from config import NCF_MIN_RATINGS
    if not ratings_data or len(ratings_data) < NCF_MIN_RATINGS:
        return {
            'success': False,
            'message': f'Data rating tidak cukup (minimal {NCF_MIN_RATINGS}, saat ini {len(ratings_data)})'
        }

    try:
        import tensorflow as tf
    except ImportError:
        return {'success': False, 'message': 'TensorFlow tidak tersedia'}

    # Mapping user_id dan produk_id ke index kontinu (0, 1, 2, ...)
    user_ids = sorted(list(set(r['user_id'] for r in ratings_data)))
    produk_ids = sorted(list(set(r['produk_id'] for r in ratings_data)))

    user_to_idx = {uid: idx for idx, uid in enumerate(user_ids)}
    produk_to_idx = {pid: idx for idx, pid in enumerate(produk_ids)}

    n_users = len(user_ids)
    n_products = len(produk_ids)

    # Siapkan data training
    user_array = np.array([user_to_idx[r['user_id']] for r in ratings_data])
    produk_array = np.array([produk_to_idx[r['produk_id']] for r in ratings_data])
    # Normalize score ke 0-1
    scores = np.array([r['score'] for r in ratings_data], dtype=np.float32) / 5.0

    # Build & train model
    model = build_ncf_model(n_users, n_products)
    if model is None:
        return {'success': False, 'message': 'Gagal membuat model'}

    # Early stopping untuk mencegah overfitting
    callbacks = []
    use_validation = len(ratings_data) >= 10
    if use_validation:
        try:
            from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
            callbacks.append(EarlyStopping(
                monitor='val_loss', patience=10, restore_best_weights=True
            ))
            # Learning rate scheduler: kurangi LR jika val_loss tidak meningkat
            callbacks.append(ReduceLROnPlateau(
                monitor='val_loss', factor=0.5, patience=5, min_lr=0.00001, verbose=0
            ))
        except ImportError:
            pass

    history = model.fit(
        [user_array, produk_array],
        scores,
        epochs=epochs,
        batch_size=16,
        validation_split=0.15 if use_validation else 0.0,
        callbacks=callbacks,
        verbose=0
    )

    # Simpan model & mappings
    os.makedirs(os.path.dirname(NCF_MODEL_PATH), exist_ok=True)
    model.save(NCF_MODEL_PATH)

    mappings = {
        'user_to_idx': {str(k): v for k, v in user_to_idx.items()},
        'produk_to_idx': {str(k): v for k, v in produk_to_idx.items()},
        'idx_to_user': {str(v): k for k, v in user_to_idx.items()},
        'idx_to_produk': {str(v): k for k, v in produk_to_idx.items()},
        'n_users': n_users,
        'n_products': n_products
    }
    with open(NCF_MAPPINGS_PATH, 'w') as f:
        json.dump(mappings, f)

    final_loss = history.history['loss'][-1]
    final_mae = history.history['mae'][-1]
    actual_epochs = len(history.history['loss'])

    # Invalidate cached model agar prediksi menggunakan model terbaru
    global _cached_model
    _cached_model = None

    return {
        'success': True,
        'message': f'Training berhasil! Loss: {final_loss:.4f}, MAE: {final_mae:.4f} ({actual_epochs} epochs)',
        'n_users': n_users,
        'n_products': n_products,
        'n_ratings': len(ratings_data),
        'epochs': actual_epochs
    }


# ── Model Caching ──────────────────────────────────────────────────────────────
# Cache model di memory agar tidak perlu load dari disk setiap request.
# Model di-reload otomatis jika file berubah (setelah retrain).
_cached_model = None
_cached_model_mtime = 0


def _get_cached_model():
    """
    Load model NCF dari cache memory. Jika file model berubah (setelah
    retrain), model dimuat ulang secara otomatis.
    """
    global _cached_model, _cached_model_mtime

    if not os.path.exists(NCF_MODEL_PATH):
        return None

    try:
        import tensorflow as tf
    except ImportError:
        return None

    mtime = os.path.getmtime(NCF_MODEL_PATH)
    if _cached_model is None or mtime > _cached_model_mtime:
        _cached_model = tf.keras.models.load_model(NCF_MODEL_PATH)
        _cached_model_mtime = mtime

    return _cached_model


def ncf_recommend(user_id, all_produk_ids, rated_produk_ids, n_recommendations=8):
    """
    Prediksi rating menggunakan model NCF, lalu rekomendasikan produk dengan prediksi tertinggi.

    Args:
        user_id: ID user
        all_produk_ids: semua produk_id di database
        rated_produk_ids: produk_id yang sudah di-rating user
        n_recommendations: jumlah rekomendasi

    Returns:
        list of produk_ids yang direkomendasikan
    """
    if not os.path.exists(NCF_MODEL_PATH) or not os.path.exists(NCF_MAPPINGS_PATH):
        return []

    # Load mappings
    with open(NCF_MAPPINGS_PATH, 'r') as f:
        mappings = json.load(f)

    user_to_idx = mappings['user_to_idx']
    produk_to_idx = mappings['produk_to_idx']

    # Cek apakah user ada di training data
    user_key = str(user_id)
    if user_key not in user_to_idx:
        # User baru: trigger retrain di background (dengan cooldown)
        from .engine import _trigger_bg_retrain
        _trigger_bg_retrain()
        return []  # Fallback ke KNN sementara

    user_idx = user_to_idx[user_key]

    # Load model dari cache (hindari load dari disk setiap request)
    model = _get_cached_model()
    if model is None:
        return []

    # Prediksi untuk semua produk yang belum di-rating
    unrated_produk_ids = [pid for pid in all_produk_ids if pid not in rated_produk_ids]
    valid_unrated = [pid for pid in unrated_produk_ids if str(pid) in produk_to_idx]

    if not valid_unrated:
        return []

    user_array = np.array([user_idx] * len(valid_unrated))
    produk_array = np.array([produk_to_idx[str(pid)] for pid in valid_unrated])

    predictions = model.predict([user_array, produk_array], verbose=0).flatten()

    # Sort by predicted rating descending
    sorted_indices = np.argsort(predictions)[::-1]
    recommended_ids = [valid_unrated[i] for i in sorted_indices[:n_recommendations]]

    return recommended_ids
