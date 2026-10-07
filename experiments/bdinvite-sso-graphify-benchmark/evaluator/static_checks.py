"""Static architectural assertion checks for BDInvite SSO Benchmark."""

import ast
import re
from pathlib import Path
from typing import List, Tuple


def check_remote_user_purged(worktree_path: Path) -> List[str]:
    """Verify that runtime code contains zero occurrences of Remote-User header checks."""
    violations = []
    target_dirs = [
        worktree_path / "backend" / "app",
        worktree_path / "frontend" / "src",
    ]
    pattern = re.compile(r"remote[-_]user", re.IGNORECASE)

    for target_dir in target_dirs:
        if not target_dir.exists():
            continue
        for file_path in target_dir.rglob("*"):
            if not file_path.is_file() or file_path.suffix not in {
                ".py",
                ".ts",
                ".tsx",
                ".js",
                ".jsx",
            }:
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
                for line_no, line in enumerate(content.splitlines(), start=1):
                    if pattern.search(line):
                        violations.append(
                            f"{file_path.relative_to(worktree_path)}:{line_no}: {line.strip()}"
                        )
            except Exception as e:
                violations.append(
                    f"Error reading {file_path.relative_to(worktree_path)}: {e}"
                )

    return violations


def check_application_domain_imports(worktree_path: Path) -> List[str]:
    """Verify application domain code does not import OIDC/OAuth/JWT/cryptography libraries directly."""
    violations = []
    app_dir = worktree_path / "backend" / "app"
    forbidden_modules = {
        "authlib",
        "jwt",
        "jose",
        "cryptography",
        "oauth2",
        "oauthlib",
    }

    # Directories to inspect (routes, models, schemas, utils) excluding any dedicated auth module
    for target in app_dir.rglob("*.py"):
        rel_path = target.relative_to(app_dir)
        # Skip auth module itself and tests
        parts = rel_path.parts
        if "auth" in parts or "tests" in parts:
            continue
        # Also skip auth route if named auth.py under routes
        if rel_path.name in {"auth.py", "oidc.py"}:
            continue

        try:
            tree = ast.parse(target.read_text(encoding="utf-8"), filename=str(target))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        base = alias.name.split(".")[0]
                        if base in forbidden_modules:
                            violations.append(
                                f"{target.relative_to(worktree_path)}:{node.lineno}: import {alias.name}"
                            )
                elif isinstance(node, ast.ImportFrom) and node.module:
                    base = node.module.split(".")[0]
                    if base in forbidden_modules:
                        violations.append(
                            f"{target.relative_to(worktree_path)}:{node.lineno}: from {node.module} import ..."
                        )
        except Exception as e:
            violations.append(
                f"Error parsing AST in {target.relative_to(worktree_path)}: {e}"
            )

    return violations


def check_auth_port_abstraction(worktree_path: Path) -> Tuple[bool, List[str]]:
    """Verify that AuthPort and Identity abstractions are defined."""
    app_dir = worktree_path / "backend" / "app"
    notes = []
    has_identity = False
    has_auth_port = False

    for py_file in app_dir.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
            if "class Identity" in content:
                has_identity = True
                notes.append(
                    f"Found Identity class in {py_file.relative_to(worktree_path)}"
                )
            if "class AuthPort" in content or "class AuthenticationPort" in content or "class IAuth" in content:
                has_auth_port = True
                notes.append(
                    f"Found AuthPort interface in {py_file.relative_to(worktree_path)}"
                )
        except Exception:
            pass

    return (has_identity and has_auth_port), notes
