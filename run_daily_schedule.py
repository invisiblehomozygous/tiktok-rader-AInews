#!/usr/bin/env python3
"""
Daily scheduler for TikTok Feishu Radar.

- 08:00 Asia/Shanghai: run Stage 1 + Phase 1 + Phase 2
- 09:00 Asia/Shanghai: push the existing report to Feishu

If analysis finishes after 09:00, the push runs immediately after analysis.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PREFERRED_PYTHON = BASE_DIR / ".venv-win" / "Scripts" / "python.exe"
PYTHON_BIN = PREFERRED_PYTHON if PREFERRED_PYTHON.exists() else Path(sys.executable)
TZ = timezone(timedelta(hours=8))
PREPARE_HOUR = 8
PUSH_HOUR = 9
RETRY_MINUTES = 10


def log(message: str) -> None:
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {message}", flush=True)


def build_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("LLM_PROVIDER", "minimax")
    return env


def run_command(*args: str) -> bool:
    command = [str(PYTHON_BIN), *args]
    log(f"Running: {' '.join(command)}")
    result = subprocess.run(command, cwd=BASE_DIR, env=build_env(), capture_output=False)
    log(f"Exit code: {result.returncode}")
    return result.returncode == 0


def shanghai_now() -> datetime:
    return datetime.now(TZ)


def at_today(hour: int) -> datetime:
    now = shanghai_now()
    return now.replace(hour=hour, minute=0, second=0, microsecond=0)


def sleep_until(target: datetime) -> None:
    while True:
        now = shanghai_now()
        seconds = (target - now).total_seconds()
        if seconds <= 0:
            return
        chunk = min(seconds, 300)
        log(f"Sleeping until {target.strftime('%Y-%m-%d %H:%M:%S')} ({int(seconds)}s left)")
        time.sleep(chunk)


def next_prepare_after(now: datetime) -> datetime:
    target = now.replace(hour=PREPARE_HOUR, minute=0, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return target


def main() -> int:
    log(f"Daily scheduler started with Python: {PYTHON_BIN}")
    log("Schedule: 08:00 prepare, 09:00 push (Asia/Shanghai)")

    prepared_for_date = None
    pushed_for_date = None

    while True:
        now = shanghai_now()
        today = now.date()
        prepare_at = at_today(PREPARE_HOUR)
        push_at = at_today(PUSH_HOUR)

        if prepared_for_date != today:
            if now < prepare_at:
                sleep_until(prepare_at)
                continue

            if now >= push_at and prepared_for_date != today:
                next_target = next_prepare_after(now)
                log("Today's 08:00-09:00 preparation window has passed; waiting for next day")
                sleep_until(next_target)
                continue

            log("Starting daily preparation run")
            ok = run_command("run_pipeline.py", "--skip-phase3")
            if ok:
                prepared_for_date = today
                log("Preparation run completed")
            else:
                retry_at = shanghai_now() + timedelta(minutes=RETRY_MINUTES)
                log(f"Preparation failed, retrying at {retry_at.strftime('%Y-%m-%d %H:%M:%S')}")
                sleep_until(retry_at)
            continue

        if pushed_for_date != today:
            now = shanghai_now()
            if now < push_at:
                sleep_until(push_at)
                continue

            log("Starting daily push run")
            ok = run_command("run_pipeline.py", "--phase3")
            if ok:
                pushed_for_date = today
                log("Push run completed")
                sleep_until(next_prepare_after(shanghai_now()))
            else:
                retry_at = shanghai_now() + timedelta(minutes=RETRY_MINUTES)
                log(f"Push failed, retrying at {retry_at.strftime('%Y-%m-%d %H:%M:%S')}")
                sleep_until(retry_at)
            continue

        sleep_until(next_prepare_after(shanghai_now()))


if __name__ == "__main__":
    sys.exit(main())
