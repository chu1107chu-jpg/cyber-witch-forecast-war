#!/usr/bin/env python

import argparse
import sys
import time
from pathlib import Path

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
