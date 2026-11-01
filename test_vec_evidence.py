"""Behavioral tests: mistakes that could change a real submission package."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import vec_evidence as ve


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.capture = self.root / "capture.json"
        self.manifest = self.root / "manifest.json"
        self.doc = {"run": {"id": "synthetic-A", "track": "agent", "framework": "toy", "model": "none"},
                    "artifacts": []}
        for kind in ("prediction", "trajectory", "prompts", "harness"):
            path = kind + ".txt"
            (self.root / path).write_text("synthetic " + kind)
            self.doc["artifacts"].append({"kind": kind, "path": path, "run_id": "synthetic-A"})

    def seal(self):
        self.capture.write_text(json.dumps(self.doc))
        return ve.seal(self.capture, self.manifest)

    def alter_manifest(self, change):
        doc = json.loads(self.manifest.read_text())
        change(doc)
        self.manifest.write_text(json.dumps(doc))

    def check(self, phase="final", used=0):
        return ve.audit(self.manifest, phase, submission_used_bytes=used)

    def test_valid_final_bundle(self):
        self.doc["run"]["unrelated_private_config"] = "synthetic-value-not-for-manifest"
        sealed = self.seal()
        self.assertNotIn("unrelated_private_config", sealed["run"])
        result = self.check()
        self.assertEqual(result["result"], "pass")
        self.assertFalse(result["authorship_or_autonomy_verified"])
        self.assertFalse(result["prediction_format_checked"])

    def test_trajectory_plus_prompts_scores_but_cannot_nominate_for_prize(self):
        self.doc["artifacts"] = self.doc["artifacts"][:-1]
        self.seal()
        self.assertEqual(self.check("scoring")["result"], "pass")
        result = self.check("final")
        self.assertEqual(result["result"], "fail")
        self.assertIn("Final nomination missing: harness", result["errors"])

    def test_two_kinds_without_trajectory_fail(self):
        self.doc["artifacts"] = [x for x in self.doc["artifacts"] if x["kind"] != "trajectory"]
        self.seal()
        self.assertEqual(self.check("scoring")["result"], "fail")

    def test_one_evidence_kind_fails_scoring(self):
        self.doc["artifacts"] = self.doc["artifacts"][:2]
        self.seal()
        self.assertEqual(self.check("scoring")["result"], "fail")

    def test_same_length_prediction_replaced_after_seal(self):
        self.seal()
        path = self.root / "prediction.txt"
        original = path.read_bytes()
        path.write_bytes(b"X" * len(original))
        result = self.check()
        self.assertEqual(result["result"], "fail")
        self.assertTrue(any("SHA-256 changed" in x for x in result["errors"]))

    def test_changed_evidence_fails(self):
        self.seal()
        (self.root / "prompts.txt").write_text("different prompt")
        self.assertEqual(self.check()["result"], "fail")

    def test_capture_cannot_mix_run_ids(self):
        self.doc["artifacts"][2]["run_id"] = "synthetic-B"
        with self.assertRaisesRegex(ve.BundleError, "do not mix runs"):
            self.seal()

    def test_forged_manifest_run_label_is_detected(self):
        self.seal()
        self.alter_manifest(lambda d: d["artifacts"][2].update(run_id="wrong-run"))
        self.assertEqual(self.check()["result"], "fail")

    def test_framework_and_model_required(self):
        for key in ("framework", "model"):
            with self.subTest(key=key):
                run = copy.deepcopy(self.doc["run"])
                run[key] = " "
                with self.assertRaises(ve.BundleError):
                    ve.validate_run(run)

    def test_human_bundle_does_not_require_agent_evidence(self):
        self.doc["run"] = {"id": "synthetic-A", "track": "human"}
        self.doc["artifacts"] = self.doc["artifacts"][:1]
        self.seal()
        self.assertEqual(self.check(used=None)["result"], "pass")

    def test_append_requires_current_submission_usage(self):
        self.seal()
        result = self.check(used=None)
        self.assertEqual(result["result"], "incomplete")
        self.assertIsNone(result["submission_total_bytes_estimate"])

    def test_legacy_team_bytes_cannot_spend_another_submissions_allowance(self):
        self.seal()
        prior_team = 3 * 1024**3
        self.assertEqual(ve.audit(self.manifest, "final", prior_team)["result"], "incomplete")
        current = ve.audit(self.manifest, "final", prior_team, submission_used_bytes=0)
        self.assertEqual(current["result"], "pass")
        self.assertIn("ignored", current["legacy_option_notice"])
        self.assertEqual(current["submission_total_bytes_estimate"], current["bundle_evidence_bytes"])

    def test_exact_submission_limit_and_one_byte_over(self):
        self.seal()
        total = self.check()["bundle_evidence_bytes"]
        self.assertEqual(ve.SUBMISSION_LIMIT, 2_147_483_648)
        self.assertEqual(self.check(used=2_147_483_648-total)["result"], "pass")
        self.assertEqual(self.check(used=2_147_483_649-total)["result"], "fail")
        self.assertEqual(self.check(used=600_000_000)["result"], "pass")

    def test_bundle_alone_over_cap_fails_even_if_current_usage_unknown(self):
        self.seal()
        bundle_bytes = self.check()["bundle_evidence_bytes"]
        with patch.object(ve, "SUBMISSION_LIMIT", bundle_bytes - 1):
            self.assertEqual(self.check(used=None)["result"], "fail")

    def test_explicit_evidence_unit_is_mib(self):
        self.assertEqual(ve.EVIDENCE_LIMIT, 209_715_200)
        self.assertEqual(ve.PREDICTION_LIMIT, 1_200_000_000)

    def test_old_manifest_can_be_audited_without_resealing(self):
        self.seal()
        self.alter_manifest(lambda d: d.update(rules_as_of="2026-09-14", tool_version="1.0.0"))
        before = self.manifest.read_bytes()
        result = self.check()
        self.assertEqual(result["result"], "pass")
        self.assertEqual(result["rules_as_of"], ve.RULES_AS_OF)
        self.assertEqual(self.manifest.read_bytes(), before)

    def test_invalid_current_submission_usage(self):
        self.seal()
        for count in (-1, False, 1.5):
            with self.subTest(count=count), self.assertRaisesRegex(ve.BundleError, "submission_used_bytes"):
                self.check(used=count)

    def test_file_limit_before_reading_sparse_oversized_file(self):
        with (self.root / "huge.log").open("wb") as stream:
            stream.truncate(ve.EVIDENCE_LIMIT + 1)
        with self.assertRaisesRegex(ve.BundleError, "exceeds"):
            ve.file_record(self.root / "huge.log", "trajectory")

    def test_exact_file_limit_and_one_byte_over(self):
        path = self.root / "small.log"
        path.write_bytes(b"12345")
        with patch.object(ve, "EVIDENCE_LIMIT", 5):
            self.assertEqual(ve.file_record(path, "trajectory")["size_bytes"], 5)
            path.write_bytes(b"123456")
            with self.assertRaises(ve.BundleError):
                ve.file_record(path, "trajectory")

    def test_empty_file_not_evidence(self):
        (self.root / "prompts.txt").write_bytes(b"")
        with self.assertRaisesRegex(ve.BundleError, "Empty"):
            self.seal()

    def test_traversal_absolute_and_symlink_paths_rejected(self):
        for path in ("../outside", "/tmp/outside", "a/../b", "a\\b", "./capture.json"):
            with self.subTest(path=path), self.assertRaises(ve.BundleError):
                ve.local_file(self.root, path)
        (self.root / "alias").symlink_to(self.root / "prompts.txt")
        with self.assertRaisesRegex(ve.BundleError, "Symlink"):
            ve.local_file(self.root, "alias")

    def test_duplicate_paths_not_distinct_evidence(self):
        self.doc["artifacts"][2]["path"] = self.doc["artifacts"][1]["path"]
        with self.assertRaisesRegex(ve.BundleError, "several evidence kinds"):
            self.seal()

    def test_hard_links_not_distinct_evidence(self):
        self.seal()
        path = self.root / "prompts.txt"
        path.unlink()
        os.link(self.root / "trajectory.txt", path)
        result = self.check()
        self.assertEqual(result["result"], "fail")
        self.assertTrue(any("Duplicate physical file" in x for x in result["errors"]))

    def test_deleted_artifact_fails(self):
        self.seal()
        (self.root / "harness.txt").unlink()
        self.assertEqual(self.check()["result"], "fail")

    def test_duplicate_keys_and_nonfinite_json_rejected(self):
        for content in ('{"run": {}, "run": {}}', '{"size_bytes": NaN}'):
            self.capture.write_text(content)
            with self.assertRaises(ve.BundleError):
                ve.read_json(self.capture)

    def test_boolean_size_is_not_an_integer_size(self):
        self.seal()
        self.alter_manifest(lambda d: d["artifacts"][0].update(size_bytes=True))
        self.assertEqual(self.check()["result"], "fail")

    def test_container_kind_seal_has_controlled_cli_error(self):
        script = str(Path(ve.__file__).resolve())
        for kind in ([], {}):
            with self.subTest(kind=kind):
                self.doc["artifacts"][0]["kind"] = kind
                self.capture.write_text(json.dumps(self.doc))
                completed = subprocess.run(
                    [sys.executable, script, "seal", str(self.capture), "--out", str(self.manifest)],
                    capture_output=True, text=True)
                self.assertEqual(completed.returncode, 3)
                self.assertEqual(json.loads(completed.stderr)["result"], "error")
                self.assertEqual(completed.stdout, "")
                self.assertNotIn("Traceback", completed.stderr)
                self.assertFalse(self.manifest.exists())

    def test_container_kind_audit_has_controlled_cli_failure(self):
        self.seal()
        script = str(Path(ve.__file__).resolve())
        for kind in ([], {}):
            with self.subTest(kind=kind):
                self.alter_manifest(lambda d: d["artifacts"][0].update(kind=kind))
                completed = subprocess.run(
                    [sys.executable, script, "audit", str(self.manifest), "--already-used-bytes", "0"],
                    capture_output=True, text=True)
                self.assertEqual(completed.returncode, 1)
                report = json.loads(completed.stdout)
                self.assertEqual(report["result"], "fail")
                self.assertTrue(any("Unknown artifact kind" in x for x in report["errors"]))
                self.assertNotIn("Traceback", completed.stderr)

    def test_invalid_utf8_is_controlled_for_both_cli_commands(self):
        self.capture.write_bytes(b'{"run": "\xff"}')
        script = str(Path(ve.__file__).resolve())
        for command in (["seal", str(self.capture), "--out", str(self.manifest)],
                        ["audit", str(self.capture)]):
            with self.subTest(command=command[0]):
                completed = subprocess.run([sys.executable, script, *command],
                                           capture_output=True, text=True)
                self.assertEqual(completed.returncode, 3)
                self.assertEqual(json.loads(completed.stderr)["result"], "error")
                self.assertEqual(completed.stdout, "")
                self.assertNotIn("Traceback", completed.stderr)
        self.assertFalse(self.manifest.exists())

    def test_policy_version_mismatch_fails(self):
        self.seal()
        self.alter_manifest(lambda d: d.update(rules_as_of="2025-01-01"))
        self.assertEqual(self.check()["result"], "fail")

    def test_reseal_does_not_erase_original_manifest(self):
        self.seal()
        old = self.manifest.read_bytes()
        with self.assertRaises(FileExistsError):
            ve.seal(self.capture, self.manifest)
        self.assertEqual(old, self.manifest.read_bytes())

    def test_cli_exit_codes_and_machine_readable_report(self):
        self.seal()
        script = str(Path(ve.__file__).resolve())
        cases = [([], 2), (["--new-submission"], 0), (["--already-used-bytes", "600000000"], 2),
                 (["--already-used-bytes", "600000000", "--new-submission"], 0),
                 (["--submission-used-bytes", "2147483648"], 1)]
        for extra, expected in cases:
            completed = subprocess.run([sys.executable, script, "audit", str(self.manifest), *extra], capture_output=True, text=True)
            self.assertEqual(completed.returncode, expected)
            self.assertEqual(json.loads(completed.stdout)["exit_code"], expected)
        (self.root / "harness.txt").unlink()
        completed = subprocess.run([sys.executable, script, "audit", str(self.manifest), "--already-used-bytes", "0"], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 1)

    def test_audit_does_not_modify_files(self):
        self.seal()
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        self.check()
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})


if __name__ == "__main__":
    unittest.main()
