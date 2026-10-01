"""Pure file-reading helpers for the research viewer app. No computation of
result numbers happens here or anywhere else in research/app/ — every number
rendered by the app is read verbatim from a JSON file written by an
experiment script under research/results/.
"""

from __future__ import annotations

import json
import os

RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "results")


def _read_json(path: str):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_progress() -> dict | None:
    return _read_json(os.path.join(RESULTS_DIR, "progress.json"))


def load_phase_summary(phase_dir: str) -> dict | None:
    return _read_json(os.path.join(RESULTS_DIR, phase_dir, "summary.json"))


def load_phase_config(phase_dir: str) -> dict | None:
    return _read_json(os.path.join(RESULTS_DIR, phase_dir, "config.json"))


def load_worked_example(phase_dir: str) -> dict | None:
    return _read_json(os.path.join(RESULTS_DIR, phase_dir, "worked_example.json"))
