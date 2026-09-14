#!/usr/bin/env python3
"""Run an educational package audit with invented data and logs only.

These fixtures must never be submitted to the Challenge as predictions or evidence.
"""
import argparse
import json
import shutil
from pathlib import Path

import anndata as ad
import h5py
import numpy as np

from vec_evidence import TEAM_LIMIT, audit, seal


def run(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    base = output / "complete"
    base.mkdir()
    rng = np.random.default_rng(20260914)
    a = ad.AnnData(X=rng.uniform(0, 2, size=(8, 5)).astype(np.float32))
    a.obs_names = [f"synthetic-cell-{i}" for i in range(8)]
    a.var_names = [f"synthetic-gene-{i}" for i in range(5)]
    a.obsm["spatial_3D"] = rng.normal(size=(8, 3)).astype(np.float32)
    a.uns["synthetic_fixture_only"] = True
    a.uns["warning"] = "Educational fixture. Not Challenge data, valid board submission, or real agent evidence."
    a.write_h5ad(base / "prediction.h5ad")
    check = ad.read_h5ad(base / "prediction.h5ad")
    assert check.shape == (8, 5) and check.uns["synthetic_fixture_only"]
    (base / "trajectory.jsonl").write_text(json.dumps({"fixture_only": True, "event": "Invented example event; no agent run occurred"}) + "\n")
    (base / "prompts.txt").write_text("SYNTHETIC FIXTURE ONLY. Example prompt to illustrate packaging; no model was run.\n")
    (base / "harness.py").write_text('# SYNTHETIC FIXTURE ONLY: no autonomous agent harness is claimed.\nprint("educational toy")\n')
    capture = {"run": {"id": "synthetic-example-A", "track": "agent", "framework": "synthetic-fixture-no-real-agent", "model": "no-model-was-run"},
               "artifacts": [{"kind": kind, "path": path, "run_id": "synthetic-example-A"} for kind, path in (
                   ("prediction", "prediction.h5ad"), ("trajectory", "trajectory.jsonl"),
                   ("prompts", "prompts.txt"), ("harness", "harness.py"))]}
    (base / "capture.json").write_text(json.dumps(capture, indent=2) + "\n")
    seal(base / "capture.json", base / "manifest.json")
    cases = []

    def record(name, folder, phase, used, expected):
        result = audit(folder / "manifest.json", phase, used)
        assert result["result"] == expected, (name, result)
        (folder / (name + "-report.json")).write_text(json.dumps(result, indent=2) + "\n")
        cases.append({"case": name, "expected": expected, "actual": result["result"], "errors": result["errors"], "warnings": result["warnings"]})

    record("complete-final", base, "final", 0, "pass")
    record("unknown-team-storage", base, "final", None, "incomplete")
    record("prior-storage-exhausted", base, "final", TEAM_LIMIT, "fail")
    partial = output / "scoring-only"
    shutil.copytree(base, partial, ignore=shutil.ignore_patterns("*-report.json"))
    doc = json.loads((partial / "manifest.json").read_text())
    doc["artifacts"] = [x for x in doc["artifacts"] if x["kind"] != "harness"]
    (partial / "manifest.json").write_text(json.dumps(doc, indent=2))
    record("two-kinds-scoring", partial, "scoring", 0, "pass")
    record("two-kinds-final", partial, "final", 0, "fail")
    wrong = output / "mixed-run"
    shutil.copytree(base, wrong, ignore=shutil.ignore_patterns("*-report.json"))
    doc = json.loads((wrong / "manifest.json").read_text())
    doc["artifacts"][2]["run_id"] = "synthetic-example-B"
    (wrong / "manifest.json").write_text(json.dumps(doc, indent=2))
    record("wrong-run-label", wrong, "final", 0, "fail")
    changed = output / "changed-prediction"
    shutil.copytree(base, changed, ignore=shutil.ignore_patterns("*-report.json"))
    # A different prediction can remain valid H5AD and exactly the same length.
    path = changed / "prediction.h5ad"
    old_size = path.stat().st_size
    with h5py.File(path, "r+") as h5:
        h5["X"][0, 0] = h5["X"][0, 0] + 0.125
    assert path.stat().st_size == old_size
    assert ad.read_h5ad(path).shape == (8, 5)
    record("same-size-replacement", changed, "final", 0, "fail")
    summary = {"synthetic_only": True, "real_agent_run": False, "scientific_scores_computed": False,
               "official_submission": False, "h5ad_roundtrip_shape": list(check.shape),
               "cases": cases, "all_expected_outcomes_observed": True}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="A new directory; existing examples are not overwritten")
    run(parser.parse_args().out)
