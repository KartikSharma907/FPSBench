#!/usr/bin/env python3
"""Publish FPS-Bench to HuggingFace: the public dataset (+ a results store).

Run interactively by a maintainer after authenticating (`huggingface-cli login`
or set ``HF_TOKEN``). No token is ever read from or written to the repository.

It creates/updates two dataset repos under ``--hf-user``:

* ``<user>/fpsbench``                      (public) — ``fpsbench_v1.jsonl`` (with
  answers) + ``.csv`` + schema + stats + the dataset card as README.
* ``<user>/fpsbench-leaderboard-results`` (public) — the store the leaderboard
  Space appends submissions to.

By default this only *prints* what it would do. Pass ``--execute`` to push.

Usage:
    huggingface-cli login
    python scripts/push_to_hf.py --hf-user YOUR_HF_USERNAME            # dry run
    python scripts/push_to_hf.py --hf-user YOUR_HF_USERNAME --execute  # push
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ANN = REPO_ROOT / "annotations"

PUBLIC_FILES = [
    ("fpsbench_v1.jsonl", ANN / "fpsbench_v1.jsonl"),
    ("fpsbench_v1.csv", ANN / "fpsbench_v1.csv"),
    ("fpsbench_v1.schema.json", ANN / "fpsbench_v1.schema.json"),
    ("fpsbench_v1_stats.json", ANN / "fpsbench_v1_stats.json"),
    ("README.md", REPO_ROOT / "release" / "dataset_card.md"),
]


def _check_files(files) -> None:
    missing = [str(p) for _, p in files if not p.exists()]
    if missing:
        sys.exit("ABORT: missing required file(s):\n  " + "\n  ".join(missing) +
                 "\nRun scripts/ingest_release.py first.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Publish FPS-Bench to HuggingFace.")
    ap.add_argument("--hf-user", required=True, help="your HuggingFace username/org")
    ap.add_argument("--public-repo", default=None, help="default <user>/fpsbench")
    ap.add_argument("--results-repo", default=None, help="default <user>/fpsbench-leaderboard-results")
    ap.add_argument("--execute", action="store_true", help="actually push (default: dry run)")
    args = ap.parse_args()

    public_repo = args.public_repo or f"{args.hf_user}/fpsbench"
    results_repo = args.results_repo or f"{args.hf_user}/fpsbench-leaderboard-results"

    _check_files(PUBLIC_FILES)

    print("Plan:")
    print(f"  dataset {public_repo}  [public]")
    for name, _ in PUBLIC_FILES:
        print(f"      - {name}")
    print(f"  dataset {results_repo}  [public]")
    print(f"      - (empty results store)")

    if not args.execute:
        print("\nDry run. Re-run with --execute to push (after `huggingface-cli login`).")
        return

    from huggingface_hub import HfApi

    api = HfApi()

    # Public dataset (includes the answer key).
    api.create_repo(public_repo, repo_type="dataset", exist_ok=True, private=False)
    for name, path in PUBLIC_FILES:
        api.upload_file(path_or_fileobj=str(path), path_in_repo=name,
                        repo_id=public_repo, repo_type="dataset")
        print(f"  uploaded {name} -> {public_repo}")

    # Results store (created empty; the Space writes results.jsonl here).
    api.create_repo(results_repo, repo_type="dataset", exist_ok=True, private=False)
    print(f"  ensured results repo {results_repo}")

    print(f"\nDone. The leaderboard Space scores against the public dataset "
          f"{public_repo}; set FPSBENCH_RESULTS_REPO={results_repo} as a Space secret.")


if __name__ == "__main__":
    main()
