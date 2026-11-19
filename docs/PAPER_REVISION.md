# Revision audit — 19 November 2026

The supplied v2 paper was read end to end (12 pages). Its historical experiment
artifacts could not be located in the provided project, Documents, Downloads or
inspected DevMind ZIP files. Historical results are preserved as reported and marked
unreproduced, not attributed to newly executed experiments.

| Review item | Action |
|---|---|
| Section IV-D reference to “Section F” | Replaced with explicit Section IV-E and Section V-F |
| Unchanged-source availability claim | Clarified main studies vs temporary source mutations |
| Unsupported accompanying-artifact claim | Removed/qualified in availability and page-2 footnote |
| Broad title | Narrowed to controller safeguards and independent verification |
| No live model results | Added 24 real first-action responses; no repair-success inference |
| safe_name accepts dot | Fixed source predicate and added regression coverage |
| Missing raw evidence | Added full new response records, fuzz inputs, test XML and hashes |
| Docker and PostgreSQL | Retried, recorded OS denials; gates remain unpassed |
| Public artifact URL | Not fabricated; no authenticated repository or DOI was available |

The new supplement is not a replacement for the absent historical scripts/data.
Old timing values are not re-benchmarked or relabelled as current measurements.
The new corpus has 151 pre-fix dot disagreements, not the historical corpus's 167.
The sample has 12 correlated issue prompts, not 12 real repository repairs.

Code changes are limited to rejecting dot at the name boundary and retaining the
most recent provider response in memory for explicit research capture. A failed
schema validation still raises and cannot reach the machine. Research scripts add
paired live-action measurement, path-oracle comparison, PDF reproduction, and a
production-path repair launcher that refuses missing dependencies.

Current verification: 47 tests passed, 3 external-service tests skipped. Paper
rendering was visually inspected. Main-project instructions and release limitations
continue to apply; no production-readiness or publication-acceptance claim is made.
