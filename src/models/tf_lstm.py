"""TensorFlow LSTM/GRU для временных рядов."""
import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)
ARTIFACT_DIR = Path("data/artifacts/tf")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

SEQ_LEN = 20


def _make_sequences(X: np.ndarray, y: np.ndarray, seq_len: int):
    Xs, ys = [], []
    for i in range(seq_len, len(X)):
        Xs.append(X[i - seq_len: i])
        ys.append(y[i])
    return np.array(Xs), np.array(ys)


def build_lstm(input_shape, output_units: int = 1, task: str = "regression"):
    import tensorflow as tf
    from tensorflow.keras import layers, models
    model = models.Sequential([
        layers.Input(shape=input_shape),
        layers.LSTM(64, return_sequences=True),
        layers.Dropout(0.2),
        layers.LSTM(32),
        layers.Dropout(0.2),
        layers.Dense(output_units, activation="sigmoid" if task == "classification" else "linear"),
    ])
    loss = "binary_crossentropy" if task == "classification" else "mse"
    model.compile(optimizer="adam", loss=loss)
    return model


def train(df: pd.DataFrame, feature_cols: list[str]) -> dict:
    import tensorflow as tf
    tf.random.set_seed(42)
    np.random.seed(42)

    artifacts = {}
    for target, task in [("target_r1", "regression"), ("target_p1_up", "classification")]:
        X = df[feature_cols].fillna(0).values
        y = df[target].values
        Xs, ys = _make_sequences(X, y, SEQ_LEN)
        split = int(len(Xs) * 0.8)
        X_tr, X_val = Xs[:split], Xs[split:]
        y_tr, y_val = ys[:split], ys[split:]

        model = build_lstm(
            input_shape=(SEQ_LEN, X.shape[1]),
            output_units=1,
            task=task,
        )
        cb = [
            tf.keras.callbacks.EarlyStopping(patience=5, restore_best_weights=True),
        ]
        logger.info(f"Training TF LSTM for {target}…")
        model.fit(X_tr, y_tr, validation_data=(X_val, y_val),
                  epochs=30, batch_size=64, callbacks=cb, verbose=0)
        save_path = ARTIFACT_DIR / f"lstm_{target}.keras"
        model.save(str(save_path))
        artifacts[target] = str(save_path)
        logger.info(f"  saved {save_path}")
    return artifacts


def predict_lstm(df: pd.DataFrame, feature_cols: list[str]) -> dict:
    import tensorflow as tf
    from sklearn.preprocessing import StandardScaler

    X = df[feature_cols].fillna(0).values
    Xs, _ = _make_sequences(X, np.zeros(len(X)), SEQ_LEN)

    preds = {}
    for target in ["target_r1", "target_p1_up"]:
        path = ARTIFACT_DIR / f"lstm_{target}.keras"
        if path.exists():
            m = tf.keras.models.load_model(str(path))
            preds[target] = m.predict(Xs, verbose=0).flatten()
    return preds
