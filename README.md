# VEC Evidence Check

Catch a changed prediction, a mixed run, or a missing evidence file before manually uploading a Virtual Embryo Challenge entry.

The local scorer answers whether a prediction can be evaluated. This tool answers a separate question: **are these still the exact files selected for this run, and is the evidence package complete for the intended stage?**

It records file sizes and SHA-256 digests, then rechecks the files without changing or uploading them. A same-sized replacement is detected. The scoring and final-nomination checks are different, and unknown team storage is reported as incomplete rather than assumed empty.

The checker runs on Python 3.10+ using the standard library. The educational `.h5ad` demonstration uses Python 3.11+ with AnnData, NumPy and h5py. Both were exercised on Python 3.14.7. No GPU, reference dataset, target labels, API key or account is needed.

## Try the checked example

```bash
python3 vec_evidence.py audit examples/synthetic-walkthrough/complete/manifest.json \
  --phase final --already-used-bytes 0
python3 -m unittest -v test_vec_evidence.py
```

The first command reports a local packaging pass for deliberately invented fixtures. These small files do **not** meet a real competition board's data requirements and must not be submitted. No autonomous run is claimed for the toy logs.

Rebuild the seven-case demonstration into a fresh directory:

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
  --phase final --already-used-bytes 123456 --out /path/to/run/check-report.json
```

Replace `123456` with the team's actual evidence storage already used, excluding this new bundle. If unknown, omit the option; the result remains incomplete. Never enter zero merely to obtain a pass. The tool cannot read the portal or independently verify that value.

5. Open the official submission page yourself and upload each actual file in the correct field. The local manifest is **not** an official submission format. Preserve the portal's acceptance and scoring receipts separately.

## Interpret the result

| Result | Exit | Meaning |
|---|---:|---|
| `pass` | 0 | Local packaging checks passed using the declared prior storage |
| `fail` | 1 | At least one concrete file, metadata, phase or size check failed |
| `incomplete` | 2 | No local failure found, but prior team evidence storage is unknown |
| `error` | 3 | Input JSON, file access or command setup prevented the audit |

A pass does not prove autonomy, authorship, truthfulness of a run label, scientific quality, data licensing, eligibility or organizer acceptance. Anyone able to rewrite both a file and its manifest could create a new matching pair. Digests detect accidental changes **relative to the preserved snapshot**; they are not a trusted timestamp, signature or adversarial provenance proof.

The checker does not parse or repair `.h5ad`, inspect scientific contents, execute harnesses, unpack archives, decompress logs or validate whether the evidence semantically explains the run. Use the official format checker and scorer for data validation. Keep genuine evidence private unless you intend to publish it.

## Rules snapshot and limits

This implementation follows the [official Rules](https://virtualembryo.ai/challenge/rules), checked on 14 September 2026: agent scoring needs trajectory plus another evidence kind; final nomination needs trajectory, prompts and harness. Framework/model must be stated. File caps are 200 MB evidence, 600 MB evidence per team, and 1200 MB prediction. Recheck the live rules before use.

Because the site does not define MB in bytes, this checker uses conservative decimal limits: 200,000,000 / 600,000,000 / 1,200,000,000 bytes. It measures the actual file being uploaded, including compressed files as stored, and does not estimate uncompressed sizes. It counts all selected new evidence files plus the operator's prior-storage figure; it does not assume server deduplication.

The [FAQ](https://virtualembryo.ai/challenge/faq) still described a lower scoring-evidence threshold when reviewed. The stricter explicit Rules govern this snapshot. No metric semantics or leaderboard scores are implemented here.

## What is included

- `vec_evidence.py`: dependency-free CLI and importable checker
- `test_vec_evidence.py`: 29 behavioral tests covering packaging mistakes and malformed input
- `demo_synthetic.py`: executable seven-case experiment with invented `.h5ad` data
- `examples/synthetic-walkthrough/summary.json`: observed outcomes from a completed run
- `TUTORIAL.es.md`: Spanish walkthrough
- `SOURCES.md`: comparison with existing organizer materials and open work

Original checker and tutorial code are under [MIT](LICENSE). No upstream code or challenge dataset is bundled. This is an independent community tool, not an organizer-endorsed validator.
