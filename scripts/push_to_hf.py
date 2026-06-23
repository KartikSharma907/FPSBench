#!/usr/bin/env python3
"""Publish FPS-Bench to HuggingFace: public dataset + private answers + results repo.

This is run interactively by a maintainer after authenticating
(`huggingface-cli login`, or set ``HF_TOKEN``). No token is ever read from or
written to the repository.

It creates/updates three repos under ``--hf-user``:

* ``<user>/fpsbench``                      (public dataset) — questions-only
  ``fpsbench_v1.jsonl`` + ``.csv`` + schema + stats + the dataset card as README.
* ``<user>/fpsbench-answers``             (PRIVATE dataset) — ``fpsbench_v1.full.jsonl``
  (the held-out answer key the leaderboard scores against).
* ``<user>/fpsbench-leaderboard-results`` (public dataset) — empty store the
  leaderboard Space appends submissions to.

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
ANSWERS_FILE = ("fpsbench_v1.full.jsonl", ANN / "fpsbench_v1.full.jsonl")


def _assert_no_answer_leak() -> None:
    """Hard guard: the public file must not contain the answer key."""
    text = (ANN / "fpsbench_v1.jsonl").read_text(encoding="utf-8")
    if '"answer"' in text:
        sys.exit("ABORT: annotations/fpsbench_v1.jsonl contains an answer key; "
                 "it must be questions-only. Re-run scripts/ingest_release.py.")


def _check_files(files) -> None:
    missing = [str(p) for _, p in files if not p.exists()]
    if missing:
        sys.exit("ABORT: missing required file(s):\n  " + "\n  ".join(missing) +
                 "\nRun scripts/ingest_release.py first.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Publish FPS-Bench to HuggingFace.")
    ap.add_argument("--hf-user", required=True, help="your HuggingFace username/org")
    ap.add_argument("--public-repo", default=None, help="default <user>/fpsbench")
    ap.add_argument("--answers-repo", default=None, help="default <user>/fpsbench-answers")
    ap.add_argument("--results-repo", default=None, help="default <user>/fpsbench-leaderboard-results")
    ap.add_argument("--execute", action="store_true", help="actually push (default: dry run)")
    args = ap.parse_args()

    public_repo = args.public_repo or f"{args.hf_user}/fpsbench"
    answers_repo = args.answers_repo or f"{args.hf_user}/fpsbench-answers"
    results_repo = args.results_repo or f"{args.hf_user}/fpsbench-leaderboard-results"

    _assert_no_answer_leak()
    _check_files(PUBLIC_FILES + [ANSWERS_FILE])

    plan = [
        (public_repo, "dataset", "public", [name for name, _ in PUBLIC_FILES]),
        (answers_repo, "dataset", "PRIVATE", [ANSWERS_FILE[0]]),
        (results_repo, "dataset", "public", ["(empty results store)"]),
    ]
    print("Plan:")
    for repo, kind, vis, names in plan:
        print(f"  {kind} {repo}  [{vis}]")
        for n in names:
            print(f"      - {n}")

    if not args.execute:
        print("\nDry run. Re-run with --execute to push (after `huggingface-cli login`).")
        return

    from huggingface_hub import HfApi

    api = HfApi()

    # Public dataset.
    api.create_repo(public_repo, repo_type="dataset", exist_ok=True, private=False)
    for name, path in PUBLIC_FILES:
        api.upload_file(path_or_fileobj=str(path), path_in_repo=name,
                        repo_id=public_repo, repo_type="dataset")
        print(f"  uploaded {name} -> {public_repo}")

    # Private answers (gated by privacy).
    api.create_repo(answers_repo, repo_type="dataset", exist_ok=True, private=True)
    api.upload_file(path_or_fileobj=str(ANSWERS_FILE[1]), path_in_repo=ANSWERS_FILE[0],
                    repo_id=answers_repo, repo_type="dataset")
    print(f"  uploaded {ANSWERS_FILE[0]} -> {answers_repo} (PRIVATE)")

    # Results store (created empty; the Space writes results.jsonl here).
    api.create_repo(results_repo, repo_type="dataset", exist_ok=True, private=False)
    print(f"  ensured results repo {results_repo}")

    print("\nDone. Next: set the leaderboard Space secrets "
          f"FPSBENCH_ANSWERS_REPO={answers_repo}, FPSBENCH_RESULTS_REPO={results_repo}, HF_TOKEN.")


if __name__ == "__main__":
    main()
