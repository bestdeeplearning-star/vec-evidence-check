# Scope and sources

VEC Evidence Check is an independent packaging tool. It does not implement or replace an official scientific metric.

The [official Rules, section 9](https://virtualembryo.ai/challenge/rules) describe the relationship between a submitted prediction and evidence of the run that produced it. This tool addresses the practical file-assembly step: explicit run labels, byte identity, completeness for a chosen phase and evidence storage estimates. The 31 October 2026 update uses the per-submission evidence limits in section 9 and the [official evidence API guide](https://virtualembryo.ai/challenge/account/api-keys).

## What was already available

The public [veckit](https://github.com/aristoteleo/veckit) repository was inspected at commit `46d41e63f42a9aab815db20b742feeccd249cb17`.

- Its README and `score_h5ad.py` describe and implement offline metric evaluation against files supplied by the entrant.
- Its `veckit_tutorial.ipynb` teaches scorer installation, CLI/API use and reference-file roles.
- [PR #2](https://github.com/aristoteleo/veckit/pull/2) concerns memory and interruption handling.
- [PR #4](https://github.com/aristoteleo/veckit/pull/4) and [PR #5](https://github.com/aristoteleo/veckit/pull/5) address synthetic conformance and adversarial metric controls.
- [PR #6](https://github.com/aristoteleo/veckit/pull/6) concerns metric definitions and a version change.

Those public materials did not expose a selected-run evidence-package checker when inspected. This is a bounded comparison, not a claim that no similar tool exists anywhere. No upstream code or notebook content has been copied into this package, and no upstream sample datasets were used.

## Boundaries

The [official data and format guidance](https://virtualembryo.ai/challenge/data) remains authoritative for an actual prediction. The executable example here uses invented eight-cell matrices and fictional evidence, solely to reproduce packaging errors. It is not an eligible board submission or a scientific benchmark.

The [Community Award page](https://virtualembryo.ai/challenge/community) describes discretionary review of public contributions. This package does not claim organizer acceptance, endorsement, adoption or any award.
