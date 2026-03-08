#!/usr/bin/env python
"""CLI runner for ETL / feature / train pipeline steps.

Usage:
    python scripts/run_etl.py --step fetch_quotes
    python scripts/run_etl.py --step fetch_news
    python scripts/run_etl.py --step clean_news
    python scripts/run_etl.py --step build_features
    python scripts/run_etl.py --step big_news
    python scripts/run_etl.py --step train --time-budget 3600
    python scripts/run_etl.py --step evaluate
    python scripts/run_etl.py --step all      # run everything
"""

import argparse
import sys
import time
from pathlib import Path

# Make sure project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def step_fetch_quotes() -> None:
    from src.etl.fetch_quotes import run as run_quotes
    print("[fetch_quotes] starting …")
    run_quotes()
    print("[fetch_quotes] done")


def step_fetch_news() -> None:
    from src.etl.fetch_news import run as run_news
    print("[fetch_news] starting …")
    run_news()
    print("[fetch_news] done")


def step_clean_news() -> None:
    from src.etl.clean_news import run as run_clean
    print("[clean_news] starting …")
    run_clean()
    print("[clean_news] done")


def step_build_features() -> None:
    from src.features.build_features import run as run_features
    print("[build_features] starting …")
    run_features()
    print("[build_features] done")


def step_big_news() -> None:
    from src.features.big_news import run as run_bn
    print("[big_news] starting …")
    run_bn()
    print("[big_news] done")


def step_train(time_budget: int) -> None:
    from src.pipeline.train import run as run_train
    print(f"[train] starting (budget={time_budget}s) …")
    run_train(time_budget=time_budget)
    print("[train] done")


def step_evaluate() -> None:
    from src.pipeline.evaluate import run as run_eval
    print("[evaluate] starting …")
    run_eval()
    print("[evaluate] done")


STEPS_ALL = [
    "fetch_quotes",
    "fetch_news",
    "clean_news",
    "build_features",
    "big_news",
    "train",
    "evaluate",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline step runner")
    parser.add_argument("--step", required=True,
                        choices=STEPS_ALL + ["all"],
                        help="Which step to run")
    parser.add_argument("--time-budget", type=int, default=3600,
                        help="Max training time in seconds (for --step train)")
    args = parser.parse_args()

    steps = STEPS_ALL if args.step == "all" else [args.step]
    t0 = time.time()

    for step in steps:
        if step == "fetch_quotes":
            step_fetch_quotes()
        elif step == "fetch_news":
            step_fetch_news()
        elif step == "clean_news":
            step_clean_news()
        elif step == "build_features":
            step_build_features()
        elif step == "big_news":
            step_big_news()
        elif step == "train":
            step_train(args.time_budget)
        elif step == "evaluate":
            step_evaluate()

    elapsed = time.time() - t0
    print(f"\n[runner] all steps finished in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
