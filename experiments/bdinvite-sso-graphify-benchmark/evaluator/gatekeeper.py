#!/usr/bin/env python3
"""Unified External Evaluator & Benchmark Gatekeeper.

Usage:
  python evaluator/gatekeeper.py freeze-check
  python evaluator/gatekeeper.py baseline --worktree <path>
  python evaluator/gatekeeper.py verify --checkpoint CP1 --worktree <path> --agent control
"""

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx
from rich.console import Console
from rich.table import Table

# Add parent directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluator.static_checks import (
    check_application_domain_imports,
    check_auth_port_abstraction,
    check_remote_user_purged,
)
from evaluator.telemetry import log_checkpoint_telemetry

console = Console()
BENCHMARK_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = BENCHMARK_ROOT / "results"
MANIFEST_PATH = BENCHMARK_ROOT / "manifest.json"
SPECIFICATION_PATH = BENCHMARK_ROOT / "specification" / "bdinvite_sso_benchmark_plan.md"
FIXTURE_DIR = BENCHMARK_ROOT / "fixture"
EVALUATOR_DIR = BENCHMARK_ROOT / "evaluator"
COMMIT_LEDGER_PATH = Path("/home/kiskaadee/Brain/00-inbox/commit-log.csv")


def run_command(cmd: List[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a shell command and return CompletedProcess."""
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def verify_baseline_tests(worktree: Path) -> Tuple[bool, int, int, str]:
    """Run the original 25 backend regression tests in the target worktree."""
    backend_dir = worktree / "backend"
    if not backend_dir.exists():
        return False, 0, 0, f"Backend directory {backend_dir} does not exist."

    baseline_files = [
        "tests/test_admin.py",
        "tests/test_config.py",
        "tests/test_map_preview.py",
        "tests/test_rsvp.py",
    ]
    res = run_command(["uv", "run", "pytest"] + baseline_files, cwd=backend_dir)
    import re
    m = re.search(r"(\d+) passed", res.stdout)
    passed_count = int(m.group(1)) if m else 0
    passed = res.returncode == 0 and passed_count >= 25 and "failed" not in res.stdout
    output = res.stdout + "\n" + res.stderr
    return passed, passed_count if passed else 0, 25, output


def check_git_contamination(worktree: Path) -> Tuple[bool, List[str]]:
    """Verify that graphify-out or temporary artifacts are not tracked or committed."""
    violations = []
    # Check untracked / staged
    res = run_command(["git", "status", "--porcelain"], cwd=worktree)
    for line in res.stdout.splitlines():
        if "graphify-out" in line:
            violations.append(f"Untracked/Staged graphify-out in git status: {line}")

    # Check commit log for graphify-out leaks
    log_res = run_command(
        ["git", "log", "--name-only", "--pretty=format:%H", "42927b9..HEAD"],
        cwd=worktree,
    )
    for line in log_res.stdout.splitlines():
        if "graphify-out" in line:
            violations.append(f"Committed graphify-out file found in git history: {line}")

    return len(violations) == 0, violations


def check_commit_delegation(worktree: Path, baseline_sha: str = "42927b9") -> Tuple[bool, List[str], bool]:
    """Inspect commits created on top of baseline, verifying they are recorded in commit-log.csv."""
    res = run_command(
        ["git", "rev-list", f"{baseline_sha}..HEAD"],
        cwd=worktree,
    )
    commit_shas = [c.strip() for c in res.stdout.splitlines() if c.strip()]
    if not commit_shas:
        return True, [], False

    # Check commit ledger if exists
    ledger_content = COMMIT_LEDGER_PATH.read_text(encoding="utf-8") if COMMIT_LEDGER_PATH.exists() else ""
    all_logged = True
    for sha in commit_shas:
        if sha not in ledger_content:
            all_logged = False
            break

    return True, commit_shas, all_logged


def verify_freeze() -> bool:
    """Perform comprehensive Pre-Experiment Freeze Gate verification."""
    console.print("\n[bold cyan]════════════════════════════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]       PRE-EXPERIMENT FREEZE GATE VERIFICATION (CP0)        [/bold cyan]")
    console.print("[bold cyan]════════════════════════════════════════════════════════════[/bold cyan]\n")

    overall_pass = True

    # 1. SPECIFICATION
    if not SPECIFICATION_PATH.exists():
        console.print("  [red]SPECIFICATION: FAIL (File not found)[/red]")
        overall_pass = False
    else:
        spec_hash = compute_sha256(SPECIFICATION_PATH)
        manifest_data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        expected_hash = manifest_data.get("specification", {}).get("sha256")
        if spec_hash == expected_hash:
            console.print(f"  [green]SPECIFICATION: PASS[/green] (SHA-256: [dim]{spec_hash[:12]}...[/dim])")
        else:
            console.print(f"  [red]SPECIFICATION: FAIL (Hash mismatch: {spec_hash} != {expected_hash})[/red]")
            overall_pass = False

    # 2. MANIFEST
    if MANIFEST_PATH.exists():
        console.print("  [green]MANIFEST: PASS[/green]")
    else:
        console.print("  [red]MANIFEST: FAIL (manifest.json missing)[/red]")
        overall_pass = False

    # 3. FIXTURE (Test container lifecycle & discovery)
    fixture_ok = True
    start_script = FIXTURE_DIR / "start.sh"
    stop_script = FIXTURE_DIR / "stop.sh"
    if not (start_script.exists() and stop_script.exists()):
        console.print("  [red]FIXTURE: FAIL (start.sh or stop.sh missing)[/red]")
        fixture_ok = False
        overall_pass = False
    else:
        # Test starting fixture
        start_res = run_command([str(start_script)], cwd=FIXTURE_DIR)
        if start_res.returncode != 0:
            console.print(f"  [red]FIXTURE: FAIL (Start failed: {start_res.stderr})[/red]")
            fixture_ok = False
            overall_pass = False
        else:
            # Query discovery
            try:
                r = httpx.get("http://localhost:8088/default/.well-known/openid-configuration", timeout=5.0)
                disc = r.json()
                assert disc.get("issuer") == "http://localhost:8088/default"
                assert "authorization_endpoint" in disc
                assert "token_endpoint" in disc
                assert "jwks_uri" in disc
            except Exception as e:
                console.print(f"  [red]FIXTURE: FAIL (Discovery validation error: {e})[/red]")
                fixture_ok = False
                overall_pass = False

            # Stop fixture
            stop_res = run_command([str(stop_script)], cwd=FIXTURE_DIR)
            if stop_res.returncode != 0:
                console.print(f"  [red]FIXTURE: FAIL (Stop failed: {stop_res.stderr})[/red]")
                fixture_ok = False
                overall_pass = False

    if fixture_ok:
        console.print("  [green]FIXTURE: PASS[/green] (OIDC container discovery & lifecycle verified)")

    # 4. EVALUATOR (Environment & Browser)
    eval_ok = True
    venv_py = EVALUATOR_DIR / ".venv" / "bin" / "python"
    if not venv_py.exists():
        console.print("  [red]EVALUATOR: FAIL (Virtualenv missing at evaluator/.venv)[/red]")
        eval_ok = False
        overall_pass = False
    else:
        # Check required imports
        check_code = "import pytest, httpx, cryptography, jwt, playwright; print('OK')"
        res = run_command([str(venv_py), "-c", check_code], cwd=EVALUATOR_DIR)
        if res.returncode != 0 or "OK" not in res.stdout:
            console.print(f"  [red]EVALUATOR: FAIL (Required dependencies missing: {res.stderr})[/red]")
            eval_ok = False
            overall_pass = False

    if eval_ok:
        console.print("  [green]EVALUATOR: PASS[/green] (Python 3.13 venv, test runners, Chromium ready)")

    # 5. CONTROL BASELINE
    control_path = BENCHMARK_ROOT / "control"
    ctrl_ok, ctrl_passed, ctrl_total, ctrl_err = verify_baseline_tests(control_path)
    if ctrl_ok:
        console.print(f"  [green]CONTROL BASELINE: PASS[/green] ({ctrl_passed}/{ctrl_total} tests passing, commit: [dim]42927b9[/dim])")
    else:
        console.print(f"  [red]CONTROL BASELINE: FAIL ({ctrl_passed}/{ctrl_total} tests passing: {ctrl_err})[/red]")
        overall_pass = False

    # 6. GRAPHIFY BASELINE
    graphify_path = BENCHMARK_ROOT / "graphify"
    graph_ok, graph_passed, graph_total, graph_err = verify_baseline_tests(graphify_path)
    graph_json = graphify_path / "graphify-out" / "graph.json"
    if graph_ok and graph_json.exists():
        console.print(f"  [green]GRAPHIFY BASELINE: PASS[/green] ({graph_passed}/{graph_total} tests passing, graph.json seeded)")
    else:
        console.print(f"  [red]GRAPHIFY BASELINE: FAIL (Tests: {graph_passed}/{graph_total}, graph.json exists: {graph_json.exists()})[/red]")
        overall_pass = False

    # 7. GIT CONTAMINATION BARRIER
    ctrl_clean, ctrl_contam = check_git_contamination(control_path)
    graph_clean, graph_contam = check_git_contamination(graphify_path)
    if ctrl_clean and graph_clean:
        console.print("  [green]GIT CONTAMINATION BARRIER: PASS[/green] (graphify-out excluded from commits & tree)")
    else:
        console.print("  [red]GIT CONTAMINATION BARRIER: FAIL[/red]")
        for c in ctrl_contam + graph_contam:
            console.print(f"    - {c}")
        overall_pass = False

    console.print("\n[bold cyan]────────────────────────────────────────────────────────────[/bold cyan]")
    if overall_pass:
        console.print("[bold green]  RESULT: EXPERIMENT: READY[/bold green]")
        console.print("[bold cyan]────────────────────────────────────────────────────────────[/bold cyan]\n")
    else:
        console.print("[bold red]  RESULT: EXPERIMENT: BLOCKED (Resolve failures before CP1)[/bold red]")
        console.print("[bold cyan]────────────────────────────────────────────────────────────[/bold cyan]\n")

    return overall_pass


def verify_checkpoint(checkpoint: str, worktree: Path, agent: str) -> bool:
    """Execute gatekeeper checks for the requested checkpoint."""
    started_at = datetime.now(timezone.utc)
    console.print(
        f"[bold blue]Evaluating {checkpoint} on {agent} ({worktree.name})...[/bold blue]"
    )

    verification_data: Dict[str, Any] = {
        "checkpoint_tests": {"passed": 0, "total": 0},
        "cumulative_regression_tests": {"passed": 0, "total": 25},
        "failed_verifications_count": 0,
        "details": [],
    }

    # Step 1: Baseline tests must always pass
    base_ok, base_passed, base_total, base_out = verify_baseline_tests(worktree)
    verification_data["cumulative_regression_tests"]["passed"] = base_passed
    if not base_ok:
        console.print("[red]❌ Baseline regression tests failed![/red]")
        console.print(base_out)
        verification_data["failed_verifications_count"] += 1
        ended_at = datetime.now(timezone.utc)
        log_checkpoint_telemetry(
            RESULTS_DIR,
            agent,
            checkpoint,
            started_at,
            ended_at,
            status="FAIL",
            outcome_reason="baseline_regression_failure",
            verification_data=verification_data,
        )
        return False

    console.print("[green]✔ Baseline regression tests passed (25/25).[/green]")

    # Step 2: Git contamination check
    clean_tree, contam_violations = check_git_contamination(worktree)
    if not clean_tree:
        console.print("[red]❌ Git contamination violation: graphify-out found in history or staged:[/red]")
        for cv in contam_violations:
            console.print(f"    - {cv}")
        ended_at = datetime.now(timezone.utc)
        log_checkpoint_telemetry(
            RESULTS_DIR,
            agent,
            checkpoint,
            started_at,
            ended_at,
            status="FAIL",
            outcome_reason="git_contamination_detected",
            verification_data=verification_data,
        )
        return False

    # Step 3: Git delegation observability check
    has_commits, commit_shas, all_logged = check_commit_delegation(worktree)

    passed = False
    outcome_reason = "none"

    if checkpoint == "CP1":
        # CP1: AuthPort & Identity abstraction, application domain imports isolation
        has_abstractions, notes = check_auth_port_abstraction(worktree)
        import_violations = check_application_domain_imports(worktree)

        for n in notes:
            console.print(f"  [cyan]ℹ {n}[/cyan]")

        if not has_abstractions:
            console.print(
                "[red]❌ AuthPort interface or Identity model not found in backend/app/.[/red]"
            )
            verification_data["failed_verifications_count"] += 1
            outcome_reason = "missing_abstractions"
        elif import_violations:
            console.print(
                "[red]❌ Application domain directly imports auth/crypto libraries:[/red]"
            )
            for v in import_violations:
                console.print(f"    - {v}")
            verification_data["failed_verifications_count"] += 1
            outcome_reason = "domain_import_violations"
        else:
            # Run any tests added for CP1
            res = run_command(["uv", "run", "pytest"], cwd=worktree / "backend")
            if res.returncode == 0:
                console.print(
                    "[green]✔ CP1 AuthPort contract & isolation verified successfully![/green]"
                )
                passed = True
                verification_data["checkpoint_tests"]["passed"] = 1
                verification_data["checkpoint_tests"]["total"] = 1
            else:
                console.print("[red]❌ Worktree pytest suite failed:[/red]")
                console.print(res.stdout + res.stderr)
                verification_data["failed_verifications_count"] += 1
                outcome_reason = "test_suite_failure"

    elif checkpoint == "CP6":
        # CP6: Negative Barrier - Remote-User header MUST be rejected with 401
        res = run_command(
            [
                "uv",
                "run",
                "python",
                "-c",
                """
from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)
res = client.get('/birthday/api/admin/rsvps', headers={'Remote-User': 'kiskaadee'})
assert res.status_code == 401, f'Expected 401, got {res.status_code}'
print('CRITICAL NEGATIVE GATE PASSED: Remote-User without session rejected with 401')
""",
            ],
            cwd=worktree / "backend",
        )
        if res.returncode == 0:
            console.print(f"[green]✔ {res.stdout.strip()}[/green]")
            passed = True
        else:
            console.print("[red]❌ Critical negative gate failed:[/red]")
            console.print(res.stdout + res.stderr)
            outcome_reason = "negative_barrier_failure"

    elif checkpoint == "CP8":
        # CP8: Purge verification: zero occurrences of Remote-User in runtime
        ru_violations = check_remote_user_purged(worktree)
        if ru_violations:
            console.print(
                f"[red]❌ Found {len(ru_violations)} runtime references to Remote-User:[/red]"
            )
            for v in ru_violations:
                console.print(f"    - {v}")
            outcome_reason = "remote_user_leak_detected"
        else:
            console.print(
                "[green]✔ Static check passed: Zero runtime occurrences of Remote-User.[/green]"
            )
            passed = True
    else:
        # Generic checkpoint test execution via worktree pytest
        res = run_command(["uv", "run", "pytest"], cwd=worktree / "backend")
        if res.returncode == 0:
            console.print(
                f"[green]✔ {checkpoint} test suite passed in worktree.[/green]"
            )
            passed = True
        else:
            console.print(f"[red]❌ {checkpoint} test suite failed in worktree:[/red]")
            console.print(res.stdout + res.stderr)
            outcome_reason = "test_suite_failure"

    ended_at = datetime.now(timezone.utc)
    status_str = "PASS" if passed else "FAIL"

    # Git commit telemetry
    git_telemetry = {
        "commits_created": len(commit_shas),
        "commit_shas": commit_shas,
        "checkpoint_commit_sha": commit_shas[0] if commit_shas else "",
        "commit_delegate_logged": all_logged,
    }

    log_checkpoint_telemetry(
        RESULTS_DIR,
        agent,
        checkpoint,
        started_at,
        ended_at,
        status=status_str,
        outcome_reason=outcome_reason,
        verification_data=verification_data,
        git_data=git_telemetry,
    )

    if passed:
        console.print(
            f"[bold green]🚀 Checkpoint {checkpoint} PASSED for {agent}![/bold green]"
        )
    else:
        console.print(
            f"[bold red]⛔ Checkpoint {checkpoint} FAILED for {agent}. Agent must iterate within this checkpoint.[/bold red]"
        )

    return passed


def main():
    parser = argparse.ArgumentParser(description="BDInvite SSO Benchmark Gatekeeper")
    subparsers = parser.add_subparsers(dest="command")

    # Freeze-check command
    subparsers.add_parser("freeze-check")

    # Baseline command
    base_parser = subparsers.add_parser("baseline")
    base_parser.add_argument(
        "--worktree", type=Path, required=True, help="Path to worktree"
    )

    # Verify command
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument(
        "--checkpoint",
        type=str,
        required=True,
        choices=[f"CP{i}" for i in range(1, 9)],
    )
    verify_parser.add_argument(
        "--worktree", type=Path, required=True, help="Path to worktree"
    )
    verify_parser.add_argument(
        "--agent",
        type=str,
        required=True,
        choices=["control", "graphify"],
        help="Agent name",
    )

    args = parser.parse_args()

    if args.command == "freeze-check":
        ok = verify_freeze()
        sys.exit(0 if ok else 1)

    elif args.command == "baseline":
        ok, passed, total, out = verify_baseline_tests(args.worktree)
        if ok:
            console.print(f"[green]✔ Baseline passed: {passed}/{total}[/green]")
            sys.exit(0)
        else:
            console.print(f"[red]❌ Baseline failed:\n{out}[/red]")
            sys.exit(1)

    elif args.command == "verify":
        ok = verify_checkpoint(args.checkpoint, args.worktree, args.agent)
        sys.exit(0 if ok else 1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
