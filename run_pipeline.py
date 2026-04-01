#!/usr/bin/env python3
"""
TikTok Feishu Radar - Cross-platform pipeline runner.

Recommended entry point for Windows, macOS, and Linux.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PYTHON_BIN = Path(sys.executable)
SKILL_RUNS_DIR = BASE_DIR / "skill_runs"
FILTERED_RESULT = BASE_DIR / "trend-scrap" / "tiktok-scraper" / "data" / "filtered-result.json"
CATEGORY_MAP = BASE_DIR / "skill_runs" / "category_map.json"
REPORT_JSON = BASE_DIR / "skill_runs" / "report.json"
REPORT_PER_VIDEO_JSON = BASE_DIR / "skill_runs" / "report_per_video.json"


def log_info(message: str) -> None:
    print(f"[INFO] {message}")


def log_warn(message: str) -> None:
    print(f"[WARN] {message}")


def log_error(message: str) -> None:
    print(f"[ERROR] {message}")


def run_python_script(script: Path, *args: str) -> int:
    """Run a Python script using the current interpreter."""
    command = [str(PYTHON_BIN), str(script), *args]
    result = subprocess.run(command, cwd=BASE_DIR, capture_output=False)
    return result.returncode


def validate_phase2_requirements() -> None:
    if not FILTERED_RESULT.exists():
        raise FileNotFoundError("Phase 2 requires filtered-result.json from Phase 1")
    log_info("Using existing data: filtered-result.json")


def validate_phase2_analysis_requirements() -> None:
    if not CATEGORY_MAP.exists():
        raise FileNotFoundError("Phase 2.2 requires category_map.json from Phase 2.1")
    if not FILTERED_RESULT.exists():
        raise FileNotFoundError("Phase 2.2 requires filtered-result.json")
    log_info("Using existing category_map.json")


def validate_phase2_per_video_requirements() -> None:
    if not CATEGORY_MAP.exists():
        raise FileNotFoundError("Phase 2.2.2 requires category_map.json from Phase 2.1")
    if not FILTERED_RESULT.exists():
        raise FileNotFoundError("Phase 2.2.2 requires filtered-result.json")
    log_info("Using existing category_map.json")


def validate_phase3_requirements() -> None:
    if not REPORT_JSON.exists():
        raise FileNotFoundError("Phase 3 requires report.json from Phase 2")
    log_info("Using existing report: report.json")


def run_parallel_analysis(run_dir: Path) -> None:
    """Run category and per-video analysis in parallel."""
    log_info("Phase 2.2: Running category and per-video analysis in parallel...")

    category_log = run_dir / "phase2_2_1.log"
    per_video_log = run_dir / "phase2_2_2.log"

    with open(category_log, "w", encoding="utf-8") as category_fp, open(
        per_video_log, "w", encoding="utf-8"
    ) as per_video_fp:
        category_proc = subprocess.Popen(
            [
                str(PYTHON_BIN),
                str(BASE_DIR / "scripts" / "phase2_analyze.py"),
                "--category-map",
                str(CATEGORY_MAP),
                "--output",
                str(REPORT_JSON),
                "--max-retries",
                "3",
            ],
            cwd=BASE_DIR,
            stdout=category_fp,
            stderr=subprocess.STDOUT,
        )

        per_video_proc = subprocess.Popen(
            [
                str(PYTHON_BIN),
                str(BASE_DIR / "scripts" / "phase2_analyze_per_video.py"),
                "--category-map",
                str(CATEGORY_MAP),
                "--output",
                str(REPORT_PER_VIDEO_JSON),
                "--max-retries",
                "3",
            ],
            cwd=BASE_DIR,
            stdout=per_video_fp,
            stderr=subprocess.STDOUT,
        )

        exit_category = category_proc.wait()
        exit_per_video = per_video_proc.wait()

    if exit_category != 0:
        log_error("Phase 2.2.1 (category analysis) failed")
        print(category_log.read_text(encoding="utf-8", errors="replace"))
        raise SystemExit(1)
    log_info("Phase 2.2.1 complete")

    if exit_per_video != 0:
        log_error("Phase 2.2.2 (per-video analysis) failed")
        print(per_video_log.read_text(encoding="utf-8", errors="replace"))
        raise SystemExit(1)
    log_info("Phase 2.2.2 complete")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TikTok Feishu Radar pipeline runner")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--phase2", action="store_true", help="Start from Phase 2")
    group.add_argument("--phase2-analysis", action="store_true", help="Run only Phase 2.2.1")
    group.add_argument("--phase2-per-video", action="store_true", help="Run only Phase 2.2.2")
    group.add_argument("--phase3", action="store_true", help="Start from Phase 3")
    parser.add_argument(
        "--no-per-video",
        action="store_true",
        help="Skip per-video analysis when running the full Phase 2 flow",
    )
    parser.add_argument(
        "--skip-phase3",
        action="store_true",
        help="Stop after Phase 2 and do not push to Feishu",
    )
    return parser.parse_args()


def resolve_start_phase(args: argparse.Namespace) -> str:
    if args.phase2:
        return "phase2"
    if args.phase2_analysis:
        return "phase2-analysis"
    if args.phase2_per_video:
        return "phase2-per-video"
    if args.phase3:
        return "phase3"
    return "all"


def main() -> int:
    args = parse_args()
    start_phase = resolve_start_phase(args)
    run_per_video = not args.no_per_video
    skip_phase3 = args.skip_phase3

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = SKILL_RUNS_DIR / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    log_info("==========================================")
    log_info(f"TikTok Feishu Radar Pipeline - {timestamp}")
    log_info(f"Start phase: {start_phase}")
    log_info(f"Python: {PYTHON_BIN}")
    log_info("==========================================")

    try:
        if start_phase == "all":
            log_info("Stage 1: Updating product manual prompt...")
            if run_python_script(BASE_DIR / "scripts" / "update_prompt_with_product_manual.py") != 0:
                log_error("Stage 1 failed")
                return 1
            log_info("Stage 1 complete")
        else:
            log_warn("Skipping Stage 1 (product manual update)")

        if start_phase == "all":
            log_info("Phase 1: Scraping and validating...")
            if run_python_script(BASE_DIR / "scripts" / "phase1_scrape.py") != 0:
                log_error("Phase 1 failed")
                return 1
            log_info("Phase 1 complete")
        else:
            log_warn("Skipping Phase 1 (scraping)")
            validate_phase2_requirements()

        if start_phase in {"all", "phase2", "phase2-analysis", "phase2-per-video"}:
            if start_phase in {"phase2-analysis", "phase2-per-video"}:
                log_warn("Skipping Phase 2.1 (classification)")
                validate_phase2_analysis_requirements()
            else:
                log_info("Phase 2.1: Classifying videos...")
                if (
                    run_python_script(
                        BASE_DIR / "scripts" / "phase2_classify.py",
                        "--output",
                        str(CATEGORY_MAP),
                        "--max-retries",
                        "3",
                    )
                    != 0
                ):
                    log_error("Phase 2.1 (classification) failed")
                    return 1
                log_info("Phase 2.1 complete")

            run_category = start_phase != "phase2-per-video"
            run_per_video_now = run_per_video or start_phase == "phase2-per-video"

            if run_category and run_per_video_now:
                run_parallel_analysis(run_dir)
            elif run_category:
                log_info("Phase 2.2.1: Analyzing categories...")
                if (
                    run_python_script(
                        BASE_DIR / "scripts" / "phase2_analyze.py",
                        "--category-map",
                        str(CATEGORY_MAP),
                        "--output",
                        str(REPORT_JSON),
                        "--max-retries",
                        "3",
                    )
                    != 0
                ):
                    log_error("Phase 2.2.1 (category analysis) failed")
                    return 1
                log_info("Phase 2.2.1 complete")
            elif run_per_video_now:
                validate_phase2_per_video_requirements()
                log_info("Phase 2.2.2: Analyzing videos individually...")
                if (
                    run_python_script(
                        BASE_DIR / "scripts" / "phase2_analyze_per_video.py",
                        "--category-map",
                        str(CATEGORY_MAP),
                        "--output",
                        str(REPORT_PER_VIDEO_JSON),
                        "--max-retries",
                        "3",
                    )
                    != 0
                ):
                    log_error("Phase 2.2.2 (per-video analysis) failed")
                    return 1
                log_info("Phase 2.2.2 complete")

            log_info("Phase 2 complete")
        else:
            log_warn("Skipping Phase 2 (analysis)")
            validate_phase3_requirements()

        if not skip_phase3 and start_phase in {"all", "phase2", "phase3"}:
            log_info("Phase 3: Building and pushing Feishu card...")
            command = [
                str(PYTHON_BIN),
                str(BASE_DIR / "scripts" / "phase3_push.py"),
                "--report",
                str(REPORT_JSON),
                "--raw",
                str(FILTERED_RESULT),
                "--card-output",
                str(run_dir / "feishu_card.json"),
            ]

            if REPORT_PER_VIDEO_JSON.exists():
                command.extend(["--report-per-video", str(REPORT_PER_VIDEO_JSON)])
                log_info("Using per-video report for bitable")
            else:
                log_warn("Per-video report not found - bitable will be skipped")

            if subprocess.run(command, cwd=BASE_DIR, capture_output=False).returncode != 0:
                log_error("Phase 3 failed")
                return 1
            log_info("Phase 3 complete")
        elif skip_phase3:
            log_warn("Skipping Phase 3 (Feishu push)")

        log_info("==========================================")
        log_info("Pipeline complete")
        log_info("==========================================")
        return 0

    except FileNotFoundError as exc:
        log_error(str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
