# Camera-ready paper and repository verification

Verified 20 November 2026. The supplied 15-page camera-ready PDF is preserved unchanged as `DevMind_Research_Paper_CameraReady.pdf`.

PDF SHA-256: `e1fcef9fd8f2b7e731ecbbc2bbd11b72a45ff055aa9ca39f7f04003f2b45add7`.

## Selected implementation

The paper's Code and Data Availability section (page 14) explicitly identifies `devmind-next`, with platform sources in `server/devmind`. This repository is that fresh implementation. The platform baseline for this publication update is commit `4074460`; this update does not change platform code. The earlier DevMind implementations and downloaded framework archives are not the selected source.

The audited platform includes the root-path rejection and protected-path canonicalization described on pages 9–10. The historical evaluated source in `research/paper_revision/evaluated_source` is retained as evidence for the earlier measurements, not as the current platform.

## Reproducibility limitation

The PDF says that `devmind_eval.py`, `fx_more.py`, `make_variants.py`, `corpus_check.py`, `study_I.py`, `numbers.py` and `figs.py` accompany the submission. These exact scripts were not found in this repository, in the searched Documents/Downloads files, or in the four downloaded DevMind ZIP archives inspected on this date. Their corresponding new experiment artifacts have not been established. Therefore the new paper's 112 scripted runs, 600 random-policy runs, source ablations and new scaling measurements are author-reported, not independently reproduced by this repository audit.

The existing `research/paper_revision` scripts, raw model responses and path corpus support separate earlier measurements; they must not be relabeled as evidence for the new experiments. The PDF was not silently edited to remove or alter its claims.

One implementation detail also differs: the worker heartbeat interval is `min(1.0, lease_seconds / 3)`, rather than an unconditional one-third lease interval described in the paper.

## Publication and execution boundary

Source publication does not establish production readiness or a live deployment. The recorded abstract-audit suite has 59 passed and 3 skipped tests. Docker, PostgreSQL integration, full live-model repair, training and official SWE-bench acceptance remain subject to the gates in `VALIDATION.md` and `ABSTRACT_AUDIT.md`.
