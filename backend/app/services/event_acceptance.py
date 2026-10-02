"""User-approved, version-bound AI evaluation provenance; never human gold."""
import json
from pathlib import Path

GATE_PATH = Path(__file__).resolve().parents[2] / "config" / "event_quality_gate.json"


def validate_gate(gate: dict) -> dict:
    if (gate.get("schema_version") != 1 or gate.get("approved_by") != "user"
            or gate.get("evaluation_origin") != "ai" or gate.get("independent_gold") is not False
            or gate.get("untouched_holdout") is not False or gate.get("formal_release") is not False
            or gate.get("acceptance_status") != "ai-evaluation-accepted-with-limitations"):
        raise ValueError("Invalid AI evaluation provenance")
    names = ("true_positive", "false_positive", "false_negative", "true_negative", "sample_pairs", "scored_pairs", "uncertain_pairs")
    if any(type(gate.get(name)) is not int or gate[name] < 0 for name in names):
        raise ValueError("Invalid evaluation counts")
    tp, fp, fn, tn = (gate[name] for name in names[:4])
    if (gate["sample_pairs"] < 200 or gate["scored_pairs"] != tp + fp + fn + tn
            or gate["sample_pairs"] != gate["scored_pairs"] + gate["uncertain_pairs"]
            or tp + fp == 0 or tp + fn == 0
            or gate.get("precision") != tp / (tp + fp) or gate.get("recall") != tp / (tp + fn)
            or not isinstance(gate.get("matcher_version"), str) or not gate["matcher_version"]
            or not isinstance(gate.get("limitations"), list) or len(gate["limitations"]) < 3):
        raise ValueError("Inconsistent AI evaluation evidence")
    return gate


def quality_for_matcher(matcher_version: str) -> dict:
    try:
        with GATE_PATH.open("rb") as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise ValueError("Evaluation gate too large")
        gate = validate_gate(json.loads(raw))
        if matcher_version == gate["matcher_version"]:
            return gate
    except (OSError, ValueError, TypeError, KeyError):
        pass
    return {"acceptance_status": "review-required", "matcher_version": matcher_version,
            "evaluation_origin": "unknown", "independent_gold": False, "formal_release": False}


def quality_status(matcher_version: str) -> str:
    return quality_for_matcher(matcher_version)["acceptance_status"]
