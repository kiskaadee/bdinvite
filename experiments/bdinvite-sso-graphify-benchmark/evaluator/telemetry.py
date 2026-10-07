"""Telemetry logging utility for BDInvite SSO Benchmark."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def log_checkpoint_telemetry(
    results_dir: Path,
    agent: str,
    checkpoint: str,
    started_at: datetime,
    ended_at: datetime,
    status: str,
    outcome_reason: str = "none",
    verification_data: Optional[Dict[str, Any]] = None,
    git_data: Optional[Dict[str, Any]] = None,
    tool_calls: Optional[Dict[str, Any]] = None,
    tokens: Optional[Dict[str, Any]] = None,
    rework_iterations: int = 0,
) -> Path:
    """Record structured telemetry for a completed checkpoint evaluation."""
    agent_dir = results_dir / agent
    agent_dir.mkdir(parents=True, exist_ok=True)
    out_file = agent_dir / f"{checkpoint}.json"

    duration_wall_clock = int((ended_at - started_at).total_seconds())

    record = {
        "agent": agent,
        "checkpoint": checkpoint,
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "duration_wall_clock_seconds": duration_wall_clock,
        "rework_iterations": rework_iterations,
        "status": status,
        "outcome_reason": outcome_reason,
        "verification": verification_data or {},
        "git": git_data or {},
        "tool_calls": tool_calls or {},
        "tokens": tokens or {},
    }

    out_file.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return out_file
