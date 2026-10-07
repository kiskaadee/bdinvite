# BDInvite Graphify-assisted SSO benchmark: retrospective

## Purpose

This experiment compared two agents implementing application-level OpenID Connect single sign-on in BDInvite. The control arm used the standard repository toolchain; the Graphify arm had Graphify available for repository exploration. The plan also specified eight implementation checkpoints, a disposable OIDC fixture, external verification, and collection of token estimates and tool-use telemetry.

## Outcome

The saved telemetry contains records for CP1 through CP8 for both arms. Every record is marked `PASS`. At CP8, both records report 25 baseline tests passing, zero failed verifications, the `Remote-User` static check passing, and a successful Docker build. The stored data therefore does not support describing the implementation experiment as a failure.

The token estimates do not show lower usage in the Graphify arm. Summing the per-checkpoint `total_tokens_est` values gives:

| Arm | Estimated tokens | Checkpoint records |
| --- | ---: | ---: |
| Control | 19,907,364 | 8 |
| Graphify | 22,923,088 | 8 |

The Graphify sum is approximately 15.1% higher. This is a descriptive comparison of the stored estimates, not a reliable measurement of actual model token usage or proof that Graphify caused the difference.

## Measurement limitations

The records identify the estimation method as `character_density_approximation`, with a ratio of 3.8. These are not direct token counts from the model provider. The experiment did not capture enough authoritative usage data to make a strong claim about Graphify's effect on token consumption. Treat the percentages as exploratory only.

The frozen plan describes a broader agent-assisted SSO implementation benchmark, even though token efficiency is one of the interests. The result set is also a single paired run with one control worktree and one Graphify worktree. It cannot separate the effect of Graphify from run-to-run variation, prompt/context differences, or other agent behavior.

## What is still useful

- The frozen plan records the intended checkpoints, security requirements, and evaluation protocol.
- The fixture and evaluator source show how the work was set up and verified.
- The checkpoint JSON files preserve implementation outcomes, tool-call telemetry, commits, and estimated usage.
- The outcome suggests a useful follow-up: rerun with provider-reported token counts, repeated trials, and a clearly specified primary metric before drawing conclusions about efficiency.

## Preserved artifacts

The accompanying directories retain the frozen specification, manifest, evaluator, disposable OIDC fixture, and raw control/Graphify result records. The `control/` and `graphify/` worktrees are intentionally not part of this archive; they remain separate implementation branches (`control/feat/sso-auth` and `graphify/feat/sso-auth`).

| Artifact | Path in archive | Description & handling |
| --- | --- | --- |
| Benchmark specification | `specification/bdinvite_sso_benchmark_plan.md` | Frozen experimental protocol and checkpoint criteria (hash verified against manifest). |
| Experiment manifest | `manifest.json` | Recorded hashes, baseline commit, fixture config, and worktree metadata. |
| Gatekeeper & Evaluator | `evaluator/` (`gatekeeper.py`, `static_checks.py`, `telemetry.py`) | Evaluator support code and gatekeeper script used during the experiment. |
| Disposable OIDC Fixture | `fixture/` (`config.json`, `docker-compose.yml`, `start.sh`, `stop.sh`, `README.md`) | Disposable mock OAuth2 test fixture configuration and run scripts. |
| Raw checkpoint telemetry | `results/control/*.json`, `results/graphify/*.json` | Raw evidence records for checkpoints CP1 through CP8 for both arms. |

## Machine-specific paths and archival integrity

Certain preserved files contain absolute paths tied to the host environment where the benchmark ran:
- `manifest.json` references local filesystem paths for `canonical_brain_plan` and `source_repository`.
- `evaluator/gatekeeper.py` hardcodes an absolute path to a local commit ledger (`/home/kiskaadee/Brain/00-inbox/commit-log.csv`).

These files are preserved without modification to maintain the historical integrity of the experimental record. Any portability improvements or harness generalization should be handled as an explicit separate follow-up rather than altering frozen experiment artifacts.
