#!/usr/bin/env python
"""Upload trained model artifacts from data/artifacts/ to Cloudflare R2."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.storage.r2 import upload_file
from src.utils.logging import get_logger

log = get_logger("upload_artifacts")
ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "data" / "artifacts"


def main() -> None:
    if not ARTIFACTS_DIR.exists():
        log.warning("Artifacts directory not found: %s", ARTIFACTS_DIR)
        return

    files = list(ARTIFACTS_DIR.rglob("*"))
    uploaded = 0
    for fpath in files:
        if fpath.is_dir():
            continue
        key = "artifacts/" + fpath.relative_to(ARTIFACTS_DIR).as_posix()
        try:
            upload_file(str(fpath), key)
            log.info("Uploaded %s → %s", fpath.name, key)
            uploaded += 1
        except Exception as exc:
            log.error("Failed to upload %s: %s", fpath, exc)

    log.info("Done. Uploaded %d file(s).", uploaded)


if __name__ == "__main__":
    main()
