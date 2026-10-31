import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from stock_training import train_all  # noqa: E402

ARTIFACTS = Path(__file__).parent.parent / "data/artifacts/lgbm"

if __name__ == "__main__":
    summary = train_all(ARTIFACTS, run_cv=True, champion_dir=ARTIFACTS if (ARTIFACTS / 'models.pkl').exists() else None)
    for target, m in summary["metrics"].items():
        print(f"{target}: CV AUC={m.get('cv_auc')}, OOS AUC={m['oos_auc']}, OOS acc={m['oos_acc']:.1%}")
