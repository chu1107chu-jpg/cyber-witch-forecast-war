"""PyTorch MLP + упрощённый Transformer для табличных данных."""
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

logger = logging.getLogger(__name__)
ARTIFACT_DIR = Path("data/artifacts/torch")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

torch.manual_seed(42)
np.random.seed(42)


class MLP(nn.Module):
    def __init__(self, in_dim: int, hidden: list[int] = (256, 128, 64),
                 out_dim: int = 1, dropout: float = 0.2):
        super().__init__()
        layers = []
        prev = in_dim
        for h in hidden:
            layers += [nn.Linear(prev, h), nn.ReLU(), nn.Dropout(dropout)]
            prev = h
        layers.append(nn.Linear(prev, out_dim))
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x).squeeze(-1)


class MiniTransformer(nn.Module):
    def __init__(self, in_dim: int, d_model: int = 64, nhead: int = 4,
                 num_layers: int = 2, dim_ff: int = 128, dropout: float = 0.1):
        super().__init__()
        self.proj = nn.Linear(in_dim, d_model)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=dim_ff,
            dropout=dropout, batch_first=True,
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.head = nn.Linear(d_model, 1)

    def forward(self, x):
        # x: (batch, features) → add seq dim
        x = x.unsqueeze(1)
        x = self.proj(x)
        x = self.encoder(x)
        return self.head(x[:, 0]).squeeze(-1)


def _train_model(model: nn.Module, X_tr, y_tr, X_val, y_val,
                 task: str = "regression", epochs: int = 40,
                 batch_size: int = 64, lr: float = 1e-3) -> nn.Module:
    criterion = nn.BCEWithLogitsLoss() if task == "classification" else nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    ds_tr = TensorDataset(torch.tensor(X_tr, dtype=torch.float32),
                          torch.tensor(y_tr, dtype=torch.float32))
    loader = DataLoader(ds_tr, batch_size=batch_size, shuffle=True)
    best_val, best_state = float("inf"), None

    for epoch in range(epochs):
        model.train()
        for xb, yb in loader:
            optimizer.zero_grad()
            loss = criterion(model(xb), yb)
            loss.backward()
            optimizer.step()
        model.eval()
        with torch.no_grad():
            val_loss = criterion(
                model(torch.tensor(X_val, dtype=torch.float32)),
                torch.tensor(y_val, dtype=torch.float32),
            ).item()
        if val_loss < best_val:
            best_val = val_loss
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        if epoch % 10 == 0:
            logger.debug(f"  epoch {epoch}: val_loss={val_loss:.5f}")

    if best_state:
        model.load_state_dict(best_state)
    return model


def train(df: pd.DataFrame, feature_cols: list[str]) -> dict:
    from sklearn.preprocessing import StandardScaler

    X = df[feature_cols].fillna(0).values.astype(np.float32)
    scaler = StandardScaler()
    X = scaler.fit_transform(X)
    split = int(len(X) * 0.8)
    artifacts = {"scaler": scaler, "feature_cols": feature_cols}

    for target, task in [("target_r1", "regression"), ("target_p1_up", "classification")]:
        y = df[target].values.astype(np.float32)
        X_tr, X_val = X[:split], X[split:]
        y_tr, y_val = y[:split], y[split:]

        in_dim = X.shape[1]
        mlp = MLP(in_dim)
        logger.info(f"Training MLP for {target}…")
        mlp = _train_model(mlp, X_tr, y_tr, X_val, y_val, task=task, epochs=40)
        torch.save(mlp.state_dict(), ARTIFACT_DIR / f"mlp_{target}.pt")
        artifacts[f"mlp_{target}_arch"] = {"in_dim": in_dim}

    import pickle
    with open(ARTIFACT_DIR / "scaler.pkl", "wb") as f:
        pickle.dump({"scaler": scaler, "feature_cols": feature_cols}, f)
    logger.info(f"Torch artifacts saved → {ARTIFACT_DIR}")
    return artifacts


def predict(df: pd.DataFrame) -> dict:
    import pickle
    from sklearn.preprocessing import StandardScaler

    meta_path = ARTIFACT_DIR / "scaler.pkl"
    if not meta_path.exists():
        return {}
    with open(meta_path, "rb") as f:
        meta = pickle.load(f)
    feature_cols = meta["feature_cols"]
    scaler = meta["scaler"]

    X = df[feature_cols].fillna(0).values.astype(np.float32)
    X = scaler.transform(X)
    xt = torch.tensor(X)

    preds = {}
    for target in ["target_r1", "target_p1_up"]:
        path = ARTIFACT_DIR / f"mlp_{target}.pt"
        if path.exists():
            in_dim = X.shape[1]
            model = MLP(in_dim)
            model.load_state_dict(torch.load(path, map_location="cpu"))
            model.eval()
            with torch.no_grad():
                out = model(xt).numpy()
            if target == "target_p1_up":
                out = torch.sigmoid(torch.tensor(out)).numpy()
            preds[target] = out
    return preds
