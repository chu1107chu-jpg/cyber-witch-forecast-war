"""
Переобучение модели акций (LightGBM) из командной строки / GitHub Actions.

Вся логика — в src/stock_training.py (тот же код использует фоновое переобучение
внутри приложения, см. src/auto_retrain.py). Артефакты пишутся в data/artifacts/lgbm/ —
оттуда их читает app_local.py.

    python scripts/train_lgbm.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from stock_training import train_all  # noqa: E402

ARTIFACTS = Path(__file__).parent.parent / "data/artifacts/lgbm"

if __name__ == "__main__":
    summary = train_all(ARTIFACTS, run_cv=True)
    for target, m in summary["metrics"].items():
        print(f"{target}: CV AUC={m.get('cv_auc')}, OOS AUC={m['oos_auc']}, OOS acc={m['oos_acc']:.1%}")
