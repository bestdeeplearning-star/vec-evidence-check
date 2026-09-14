#!/usr/bin/env python3
"""Offline packaging checks for Virtual Embryo Agent Team evidence.

No network, model execution, HDF5 parsing or claim of autonomous authorship.
The manifest format is local to this tool, not an organizer upload format.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

VERSION = "1.0.0"
RULES_URL = "https://virtualembryo.ai/challenge/rules"
RULES_AS_OF = "2026-09-14"
EVIDENCE_LIMIT = 200_000_000
TEAM_LIMIT = 600_000_000
PREDICTION_LIMIT = 1_200_000_000
KINDS = {"prediction", "trajectory", "prompts", "harness", "other"}


class BundleError(ValueError):
    pass


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BundleError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    def bad_constant(value):
        raise BundleError(f"Non-finite JSON constant: {value}")
    try:
        with Path(path).open(encoding="utf-8") as stream:
            value = json.load(stream, object_pairs_hook=_pairs, parse_constant=bad_constant)
        if not isinstance(value, dict):
            raise BundleError("Expected a JSON object")
        return value
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise BundleError(str(exc)) from exc


def _text(obj, key):
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BundleError(f"{key} must be a non-empty string")
    return value


def local_file(root, relative):
    """Only explicit regular files under the bundle; never follow symlinks."""
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise BundleError("Artifact path must be a relative POSIX path")
    path = PurePosixPath(relative)
    if path.is_absolute() or any(part in ("", ".", "..") for part in relative.split("/")):
        raise BundleError(f"Unsafe artifact path: {relative}")
    current = Path(root).resolve()
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise BundleError(f"Symlink not allowed: {relative}")
    if not current.is_file():
        raise BundleError(f"Missing regular file: {relative}")
    return current


def file_record(path, kind):
    limit = PREDICTION_LIMIT if kind == "prediction" else EVIDENCE_LIMIT
    before = path.stat()
    if before.st_size <= 0:
        raise BundleError("Empty artifact")
    if before.st_size > limit:
        raise BundleError(f"File exceeds conservative decimal-byte limit {limit}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        while block := stream.read(1024 * 1024):
            digest.update(block)
        after = os.fstat(stream.fileno())
    end = path.stat()
    fingerprints = {(s.st_ino, s.st_size, s.st_mtime_ns) for s in (before, opened, after, end)}
    if len(fingerprints) != 1:
        raise BundleError("File changed while being read; freeze the run and retry")
    return {"size_bytes": after.st_size, "sha256": digest.hexdigest()}


def validate_run(run):
    if not isinstance(run, dict):
        raise BundleError("run must be an object")
    _text(run, "id")
    if run.get("track") not in ("agent", "human"):
        raise BundleError("run.track must be agent or human")
    if run["track"] == "agent":
        _text(run, "framework")
        _text(run, "model")


def seal(capture_path, output_path):
    capture_path, output_path = Path(capture_path).resolve(), Path(output_path).absolute()
    if capture_path.parent != output_path.parent.resolve():
        raise BundleError("Place the manifest beside the capture JSON so relative paths stay stable")
    capture = read_json(capture_path)
    run = capture.get("run")
    validate_run(run)
    artifacts = capture.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise BundleError("artifacts must be a non-empty array")
    records, seen = [], set()
    for item in artifacts:
        if (not isinstance(item, dict) or not isinstance(item.get("kind"), str)
                or item["kind"] not in KINDS):
            raise BundleError("Each artifact needs a supported kind")
        if item.get("run_id") != run["id"]:
            raise BundleError("Artifact run_id differs from selected run; do not mix runs")
        relative = _text(item, "path")
        path = local_file(capture_path.parent, relative)
        if path in seen:
            raise BundleError("One physical path cannot stand in for several evidence kinds")
        seen.add(path)
        records.append({"kind": item["kind"], "path": relative, "run_id": item["run_id"],
                        **file_record(path, item["kind"])})
    if sum(item["kind"] == "prediction" for item in records) != 1:
        raise BundleError("A bundle must contain exactly one prediction")
    # Preserve only documented metadata, never arbitrary extra run configuration.
    public_run = {key: run[key] for key in ("id", "track", "framework", "model") if key in run}
    manifest = {"schema_version": 1, "tool_version": VERSION,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "rules_as_of": RULES_AS_OF, "run": public_run, "artifacts": records}
    # Exclusive creation: re-sealing cannot silently erase evidence of a later file change.
    with output_path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    return manifest


def audit(manifest_path, phase="scoring", already_used_bytes=None):
    if phase not in ("scoring", "final"):
        raise BundleError("phase must be scoring or final")
    if already_used_bytes is not None and (type(already_used_bytes) is not int or already_used_bytes < 0):
        raise BundleError("already_used_bytes must be a non-negative integer")
    manifest_path = Path(manifest_path)
    errors, warnings, checks = [], [], []
    result = {"tool_version": VERSION, "phase": phase, "rules_as_of": RULES_AS_OF,
              "rules_url": RULES_URL, "errors": errors, "warnings": warnings, "files": checks,
              "prediction_format_checked": False, "authorship_or_autonomy_verified": False,
              "network_requests": 0, "manifest_is_official_upload_format": False,
              "note": "A pass means local packaging checks passed. It is not acceptance, scoring, eligibility or proof of autonomy."}
    manifest = read_json(manifest_path)
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        errors.append("Unsupported manifest schema_version")
    run = manifest.get("run")
    try:
        validate_run(run)
    except BundleError as exc:
        errors.append(str(exc))
        run = run if isinstance(run, dict) else {}
    if manifest.get("rules_as_of") != RULES_AS_OF:
        errors.append("Manifest policy snapshot differs from this tool; review rules before continuing")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("artifacts must be a non-empty array")
        artifacts = []
    evidence_kinds, seen_paths, seen_file_ids, evidence_bytes = set(), set(), set(), 0
    predictions = 0
    for item in artifacts:
        if not isinstance(item, dict):
            errors.append("Artifact must be an object")
            continue
        kind, relative = item.get("kind"), item.get("path")
        check = {"kind": kind, "path": relative, "ok": False}
        checks.append(check)
        if not isinstance(kind, str) or kind not in KINDS:
            errors.append(f"Unknown artifact kind: {kind}")
            continue
        predictions += kind == "prediction"
        if kind != "prediction":
            evidence_kinds.add(kind)
        if item.get("run_id") != run.get("id"):
            errors.append(f"Artifact run_id mismatch: {relative}")
        try:
            path = local_file(manifest_path.parent, relative)
            stat = path.stat()
            physical_id = (stat.st_dev, stat.st_ino)
            if relative in seen_paths or physical_id in seen_file_ids:
                raise BundleError("Duplicate physical file assigned more than one role")
            seen_paths.add(relative)
            seen_file_ids.add(physical_id)
            actual = file_record(path, kind)
            check.update(actual)
            if kind != "prediction":
                evidence_bytes += actual["size_bytes"]
            if type(item.get("size_bytes")) is not int or actual["size_bytes"] != item["size_bytes"]:
                raise BundleError("Size changed since sealing")
            if not isinstance(item.get("sha256"), str) or actual["sha256"] != item["sha256"]:
                raise BundleError("SHA-256 changed since sealing")
            check["ok"] = True
        except (BundleError, OSError) as exc:
            check["error"] = str(exc)
            errors.append(f"{relative}: {exc}")
    if predictions != 1:
        errors.append("Exactly one prediction is required")
    if run.get("track") == "agent":
        if "trajectory" not in evidence_kinds:
            errors.append("Agent entries require a trajectory")
        if phase == "scoring" and len(evidence_kinds) < 2:
            errors.append("Scoring requires at least two distinct evidence kinds, including trajectory")
        if phase == "final":
            missing = {"trajectory", "prompts", "harness"} - evidence_kinds
            if missing:
                errors.append("Final nomination missing: " + ", ".join(sorted(missing)))
    result["bundle_evidence_bytes"] = evidence_bytes
    result["team_already_used_bytes_declared"] = already_used_bytes
    result["team_total_bytes_estimate"] = None
    if evidence_bytes > TEAM_LIMIT:
        errors.append("This bundle alone exceeds the conservative team evidence limit")
    if evidence_bytes and already_used_bytes is None:
        warnings.append("Team storage already used is unknown. Read it in the official portal; pass --already-used-bytes excluding this new bundle.")
    elif already_used_bytes is not None:
        result["team_total_bytes_estimate"] = evidence_bytes + already_used_bytes
        if result["team_total_bytes_estimate"] > TEAM_LIMIT:
            errors.append("Declared prior storage plus this bundle exceeds the conservative team evidence limit")
    result["result"] = "fail" if errors else "incomplete" if warnings else "pass"
    result["exit_code"] = {"pass": 0, "fail": 1, "incomplete": 2}[result["result"]]
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("seal", help="Record exact local files after the chosen run has finished")
    make.add_argument("capture", type=Path)
    make.add_argument("--out", required=True, type=Path)
    check = sub.add_parser("audit", help="Recheck exact files; never upload or modify them")
    check.add_argument("manifest", type=Path)
    check.add_argument("--phase", choices=["scoring", "final"], default="scoring")
    check.add_argument("--already-used-bytes", type=int)
    check.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "seal":
            manifest = seal(args.capture, args.out)
            print(json.dumps({"result": "sealed", "manifest": str(args.out), "artifacts": len(manifest["artifacts"])}))
            return 0
        result = audit(args.manifest, args.phase, args.already_used_bytes)
        text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            # Exclusive creation also protects accidental evidence/report overwrites.
            with args.out.open("x", encoding="utf-8") as stream:
                stream.write(text)
        print(text, end="")
        return result["exit_code"]
    except (BundleError, OSError) as exc:
        print(json.dumps({"result": "error", "error": str(exc)}), file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
