# VEC Evidence Check

Catch a changed prediction, a mixed run, or a missing evidence file before manually uploading a Virtual Embryo Challenge entry.

The local scorer answers whether a prediction can be evaluated. This tool answers a separate question: **are these still the exact files selected for this run, and is the evidence package complete for the intended stage?**

It records file sizes and SHA-256 digests, then rechecks the files without changing or uploading them. A same-sized replacement is detected. The scoring and final-nomination checks are different, and evidence storage is checked for the selected submission.

The checker runs on Python 3.10+ using the standard library. The educational `.h5ad` demonstration uses Python 3.11+ with AnnData, NumPy and h5py. Both were exercised on Python 3.14.7. No GPU, reference dataset, target labels, API key or account is needed.

## Try the checked example

```bash
python3 vec_evidence.py audit examples/synthetic-walkthrough/complete/manifest.json \
  --phase final --new-submission
python3 -m unittest -v test_vec_evidence.py
```

The first command reports a local packaging pass for deliberately invented fixtures. These small files do **not** meet a real competition board's data requirements and must not be submitted. No autonomous run is claimed for the toy logs.

Rebuild the eight-case demonstration into a fresh directory:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-demo.txt
.venv/bin/python demo_synthetic.py --out /tmp/vec-evidence-demo
```

On Windows, use `.venv\Scripts\python` instead. Choose a new output directory each time; existing evidence is never silently overwritten. See [the Spanish walkthrough](TUTORIAL.es.md) for the experiment and fixes.

## Use with your own completed run

1. Keep the selected run's prediction and genuinely captured evidence together. Preserve the original trajectory, prompts and harness as they were produced. This tool never manufactures them.
2. Write `capture.json` beside those files. Paths are explicit and relative; no folder scanning is performed.

```json
{
  "run": {
    "id": "your-actual-run-id",
    "track": "agent",
    "framework": "the-framework-actually-used",
    "model": "the-model-actually-used"
  },
  "artifacts": [
    {"kind": "prediction", "path": "prediction.h5ad", "run_id": "your-actual-run-id"},
    {"kind": "trajectory", "path": "trajectory.jsonl.gz", "run_id": "your-actual-run-id"},
    {"kind": "prompts", "path": "prompts.json", "run_id": "your-actual-run-id"},
    {"kind": "harness", "path": "harness.zip", "run_id": "your-actual-run-id"}
  ]
}
```

The names above are placeholders for this documentation. Use accurate values and actual files in a real package. A trajectory can span several files with the same kind. A single local file cannot be assigned several roles by this checker.

3. After the run finishes, create an immutable-by-default snapshot:

```bash
python3 vec_evidence.py seal /path/to/run/capture.json --out /path/to/run/manifest.json
```

4. Immediately before manual upload, recheck it:

```bash
python3 vec_evidence.py audit /path/to/run/manifest.json \
  --phase final --new-submission --out /path/to/run/check-report.json
```

Use `--new-submission` when this prediction has no attached evidence. For an existing submission, use `--submission-used-bytes N`, where `N` is the number of bytes already attached to **this submission** outside the bundle. Count each stored or planned attachment once. For a bundle containing only new files, `N` is the submission's `used_bytes` in the [official API guide](https://virtualembryo.ai/challenge/account/api-keys). The checker only verifies evidence kinds present locally. If you include previously attached files for that check, exclude their already-counted bytes from `N`. Unknown usage yields `incomplete` when the bundle contains evidence.

Older scripts may still pass `--already-used-bytes`. This team-wide figure is ignored and recorded as a migration notice. Supply one of the new options. The checker can audit the original 1.0 manifests using their stored hashes.

5. Open the official submission page yourself and upload each actual file in the correct field. The local manifest is **not** an official submission format. Preserve the portal's acceptance and scoring receipts separately.

## Interpret the result

| Result | Exit | Meaning |
|---|---:|---|
| `pass` | 0 | Local packaging checks passed for the selected submission |
| `fail` | 1 | At least one concrete file, metadata, phase or size check failed |
| `incomplete` | 2 | No local failure found, but this submission’s prior evidence usage is unknown |
| `error` | 3 | Input JSON, file access or command setup prevented the audit |

A pass does not prove autonomy, authorship, truthfulness of a run label, scientific quality, data licensing, eligibility or organizer acceptance. Anyone able to rewrite both a file and its manifest could create a new matching pair. Digests detect accidental changes **relative to the preserved snapshot**; they are not a trusted timestamp, signature or adversarial provenance proof.

The checker does not parse or repair `.h5ad`, inspect scientific contents, execute harnesses, unpack archives, decompress logs or validate whether the evidence semantically explains the run. Use the official format checker and scorer for data validation. Keep genuine evidence private unless you intend to publish it.

## Rules snapshot and limits

The [official Rules](https://virtualembryo.ai/challenge/rules) and [API guide](https://virtualembryo.ai/challenge/account/api-keys) were checked on 31 October 2026. Each evidence attachment may be at most 200 MiB (209,715,200 bytes). The evidence attached to one submission, including the new bundle, may total at most 2 GiB (2,147,483,648 bytes). Evidence attached to another submission, including P2 entries, does not count. The checker measures compressed files as stored. A prediction is checked separately and excluded from the evidence total. For predictions it retains the original conservative 1,200,000,000-byte limit (the rules use MB and the upload guide uses MiB).

Agent scoring requires a trajectory and another evidence kind. Final nomination requires a trajectory, prompts and a harness. Declare the framework and model. Recheck the official pages for later changes.

The [FAQ](https://virtualembryo.ai/challenge/faq) still described a lower scoring-evidence threshold when reviewed. The stricter explicit Rules govern this snapshot. No metric semantics or leaderboard scores are implemented here.

## What is included

- `vec_evidence.py`: dependency-free CLI and importable checker
- `test_vec_evidence.py`: behavioral tests covering packaging mistakes and malformed input
- `demo_synthetic.py`: executable eight-case experiment with invented `.h5ad` data
- `examples/synthetic-walkthrough/summary.json`: observed outcomes from a completed run
- `TUTORIAL.es.md`: Spanish walkthrough
- `SOURCES.md`: comparison with existing organizer materials and open work

Original checker and tutorial code are under [MIT](LICENSE). No upstream code or challenge dataset is bundled. This is an independent community tool, not an organizer-endorsed validator.
