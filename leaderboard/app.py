#!/usr/bin/env python3
"""FPS-Bench leaderboard -- a held-out-answer Gradio Space.

Users upload a predictions JSONL produced by ``scripts/evaluate.py`` (one object
per line, ``{"id": "fpsbench_000000", "prediction": "A"}`` or with
``raw_response``). The Space scores it server-side against the **private** answer
key and appends the result to a persisted leaderboard. The public dataset is
questions-only, so answers are never exposed here.

Configuration (Space *Secrets* / *Variables*; sensible local fallbacks):

* ``HF_TOKEN``            -- token with read access to the private answers repo
                            and write access to the results repo.
* ``FPSBENCH_ANSWERS_REPO`` -- private dataset id holding ``fpsbench_v1.full.jsonl``
                            (e.g. ``<your-hf-user>/fpsbench-answers``).
* ``FPSBENCH_RESULTS_REPO`` -- dataset id to persist submissions
                            (e.g. ``<your-hf-user>/fpsbench-leaderboard-results``).

For local development, drop ``annotations/fpsbench_v1.full.jsonl`` next to the
repo root (it is git-ignored) and results persist to ``leaderboard/results.jsonl``.

The scoring logic is the same code path as the CLI: ``scripts.score_predictions``.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Make the repo importable whether the Space installs the package or runs from a
# checkout (the GitHub repo's `leaderboard/` synced into the Space).
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.score_predictions import score_predictions  # noqa: E402

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
HF_TOKEN = os.environ.get("HF_TOKEN")
ANSWERS_REPO = os.environ.get("FPSBENCH_ANSWERS_REPO")  # e.g. "<user>/fpsbench-answers"
RESULTS_REPO = os.environ.get("FPSBENCH_RESULTS_REPO")  # e.g. "<user>/fpsbench-leaderboard-results"
ANSWERS_FILENAME = "fpsbench_v1.full.jsonl"
RESULTS_FILENAME = "results.jsonl"

LOCAL_ANSWERS = REPO_ROOT / "annotations" / ANSWERS_FILENAME
LOCAL_RESULTS = Path(__file__).resolve().parent / RESULTS_FILENAME
SEED_FILE = Path(__file__).resolve().parent / "seed_leaderboard.json"

EXPECTED_NUM_EXAMPLES = 1000

# Leaderboard columns surfaced in the UI table.
DISPLAY_COLUMNS = [
    "Model", "Type", "Overall Acc (%)", "95% CI", "minFPS 4", "minFPS 10+",
    "No-answer (%)", "# scored", "Submitted",
]


# --------------------------------------------------------------------------- #
# Data loading (answers + persisted results), with local fallbacks
# --------------------------------------------------------------------------- #
def _read_jsonl(path: Path) -> List[Dict]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def load_annotations() -> List[Dict]:
    """Load the private full annotations (with answers). Local file wins; else HF."""
    if LOCAL_ANSWERS.exists():
        return _read_jsonl(LOCAL_ANSWERS)
    if ANSWERS_REPO:
        from huggingface_hub import hf_hub_download

        path = hf_hub_download(
            repo_id=ANSWERS_REPO, filename=ANSWERS_FILENAME,
            repo_type="dataset", token=HF_TOKEN,
        )
        return _read_jsonl(Path(path))
    raise RuntimeError(
        "No answer key available: set FPSBENCH_ANSWERS_REPO (+ HF_TOKEN) or place "
        f"{ANSWERS_FILENAME} under annotations/."
    )


def load_seed_rows() -> List[Dict]:
    if SEED_FILE.exists():
        return json.loads(SEED_FILE.read_text(encoding="utf-8"))
    return []


def load_submissions() -> List[Dict]:
    """Persisted user submissions (seed rows are added separately)."""
    if RESULTS_REPO:
        try:
            from huggingface_hub import hf_hub_download

            path = hf_hub_download(
                repo_id=RESULTS_REPO, filename=RESULTS_FILENAME,
                repo_type="dataset", token=HF_TOKEN,
            )
            return _read_jsonl(Path(path))
        except Exception:
            return []
    if LOCAL_RESULTS.exists():
        return _read_jsonl(LOCAL_RESULTS)
    return []


def persist_submission(row: Dict) -> None:
    """Append one submission to the results store (HF dataset or local file)."""
    rows = load_submissions()
    rows.append(row)
    body = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    if RESULTS_REPO and HF_TOKEN:
        from huggingface_hub import HfApi

        HfApi().upload_file(
            path_or_fileobj=body.encode("utf-8"),
            path_in_repo=RESULTS_FILENAME,
            repo_id=RESULTS_REPO,
            repo_type="dataset",
            token=HF_TOKEN,
            commit_message=f"Add submission: {row.get('Model', '?')}",
        )
    else:
        LOCAL_RESULTS.write_text(body, encoding="utf-8")


# --------------------------------------------------------------------------- #
# Scoring + validation (pure functions, unit-testable without gradio)
# --------------------------------------------------------------------------- #
def validate_predictions(preds: List[Dict], valid_ids: set) -> Optional[str]:
    """Return an error string if the submission is malformed, else ``None``."""
    if not preds:
        return "Submission is empty."
    seen = set()
    for i, p in enumerate(preds):
        if "id" not in p:
            return f"Row {i} is missing an 'id'."
        if p["id"] not in valid_ids:
            return f"Row {i}: unknown id {p['id']!r} (not part of FPS-Bench)."
        if p["id"] in seen:
            return f"Duplicate prediction for id {p['id']!r}."
        seen.add(p["id"])
        if p.get("prediction") is None and not str(p.get("raw_response", "")).strip():
            return f"Row {i} ({p['id']}): needs a 'prediction' or non-empty 'raw_response'."
    missing = len(valid_ids) - len(seen)
    if missing > 0:
        return (f"Submission covers {len(seen)}/{len(valid_ids)} examples; "
                f"{missing} are missing. Submit predictions for all examples.")
    return None


def summary_to_row(model: str, model_type: str, summary: Dict) -> Dict:
    """Flatten a compute_metrics summary into a leaderboard table row."""
    ci = summary.get("overall_accuracy_95ci") or [None, None]
    by_fps = summary.get("accuracy_by_min_fps_bucket", {})

    def pct(x):
        return round(100 * x, 1) if isinstance(x, (int, float)) else None

    def bucket_acc(b):
        d = by_fps.get(b)
        return pct(d["accuracy"]) if isinstance(d, dict) and "accuracy" in d else None

    return {
        "Model": model,
        "Type": model_type or "submission",
        "Overall Acc (%)": pct(summary.get("overall_accuracy")),
        "95% CI": (f"[{pct(ci[0])}, {pct(ci[1])}]"
                   if ci and ci[0] is not None else ""),
        "minFPS 4": bucket_acc("4"),
        "minFPS 10+": bucket_acc("10+"),
        "No-answer (%)": pct(summary.get("no_answer_rate")),
        "# scored": summary.get("num_scored"),
        "Submitted": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        # keep the full metrics for transparency / re-rendering
        "_summary": summary,
    }


def score_submission(model: str, model_type: str, preds: List[Dict],
                     annotations: List[Dict]) -> Tuple[Optional[Dict], Optional[str]]:
    """Validate + score one submission. Returns ``(row, error)``."""
    valid_ids = {r["id"] for r in annotations}
    err = validate_predictions(preds, valid_ids)
    if err:
        return None, err
    summary, _rows = score_predictions(annotations, preds)
    return summary_to_row(model, model_type, summary), None


def build_table(submissions: List[Dict]) -> List[List]:
    """Seed rows + submissions, sorted by overall accuracy desc, as table rows."""
    rows = load_seed_rows() + submissions
    rows = sorted(
        rows,
        key=lambda r: (r.get("Overall Acc (%)") is not None, r.get("Overall Acc (%)") or 0),
        reverse=True,
    )
    return [[r.get(c, "") for c in DISPLAY_COLUMNS] for r in rows]


# --------------------------------------------------------------------------- #
# Gradio UI
# --------------------------------------------------------------------------- #
def _handle_submit(model_name, model_type, pred_file):
    import gradio as gr

    if not model_name or not str(model_name).strip():
        return gr.update(), "Please enter a model name."
    if pred_file is None:
        return gr.update(), "Please upload a predictions .jsonl file."
    try:
        preds = _read_jsonl(Path(pred_file.name if hasattr(pred_file, "name") else pred_file))
    except Exception as e:
        return gr.update(), f"Could not parse the predictions file: {e}"

    annotations = load_annotations()
    row, err = score_submission(model_name.strip(), (model_type or "").strip(), preds, annotations)
    if err:
        return gr.update(), f"❌ {err}"

    persist_submission(row)
    table = build_table(load_submissions())
    acc = row["Overall Acc (%)"]
    return table, f"✅ Scored **{model_name}** — overall accuracy {acc}% (random ~20%). Added to the leaderboard."


def build_demo():
    import gradio as gr

    with gr.Blocks(title="FPS-Bench Leaderboard") as demo:
        gr.Markdown(
            "# FPS-Bench Leaderboard\n"
            "High-frame-rate video understanding. Answers are **held out**: upload "
            "predictions and we score them server-side. Build a predictions file with "
            "`scripts/evaluate.py` (see the [repo](https://github.com/KartikSharma907/FPSBench))."
        )
        with gr.Tab("Leaderboard"):
            table = gr.Dataframe(
                headers=DISPLAY_COLUMNS, value=build_table(load_submissions()),
                interactive=False, wrap=True,
            )
            gr.Button("Refresh").click(lambda: build_table(load_submissions()), outputs=table)
        with gr.Tab("Submit"):
            gr.Markdown(
                "Upload a predictions JSONL covering all 1000 examples. Each line:\n"
                "`{\"id\": \"fpsbench_000000\", \"prediction\": \"A\"}` "
                "(or `{\"id\": ..., \"raw_response\": \"...\"}`)."
            )
            name = gr.Textbox(label="Model name", placeholder="e.g. GPT-4o (frames@minFPS)")
            mtype = gr.Textbox(label="Type / affiliation (optional)", placeholder="e.g. proprietary VLM")
            f = gr.File(label="predictions.jsonl", file_types=[".jsonl"])
            status = gr.Markdown()
            gr.Button("Score & submit", variant="primary").click(
                _handle_submit, inputs=[name, mtype, f], outputs=[table, status]
            )
    return demo


if __name__ == "__main__":
    build_demo().launch()
