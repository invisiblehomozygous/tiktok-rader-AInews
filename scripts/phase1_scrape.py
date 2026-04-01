"""
Phase 1: Scrape and Validate

Runs the TikTok scraper, post-processes the output, generates video
summaries, and validates the result.
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

# Import shared utilities
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
from utils import parse_video_datetime


BASE_DIR = SCRIPT_DIR.parent
TREND_SCRAP_DIR = BASE_DIR / "trend-scrap"
SCRAPER_DIR = TREND_SCRAP_DIR / "tiktok-scraper"
DATA_FILE = SCRAPER_DIR / "data" / "filtered-result.json"
SCRAPER_ENTRY = SCRAPER_DIR / "src" / "scraper.js"
VIDEO_ANALYZER = SCRAPER_DIR / "analyze_videos.py"


def get_target_date() -> date | None:
    """Read an optional YYYY-MM-DD target date from the environment."""
    raw = os.environ.get("TARGET_DATE", "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid TARGET_DATE '{raw}', expected YYYY-MM-DD") from exc


def check_dependencies() -> bool:
    """Check that required executables and project files exist."""
    if not shutil.which("node"):
        print("ERROR: 'node' is not installed or not available in PATH")
        return False
    if not SCRAPER_ENTRY.exists():
        print(f"ERROR: Scraper entry not found: {SCRAPER_ENTRY}")
        return False
    if not VIDEO_ANALYZER.exists():
        print(f"ERROR: Video analyzer not found: {VIDEO_ANALYZER}")
        return False
    return True


def run_tiktok_scraper() -> int:
    """Run the Node.js TikTok scraper. Returns exit code."""
    print("Phase 1: running TikTok scraper...")
    result = subprocess.run(["node", "src/scraper.js"], cwd=SCRAPER_DIR, capture_output=False)
    return result.returncode


def run_video_analyzer() -> int:
    """Run the Python video summarizer using the current interpreter."""
    print("Phase 1: generating video summaries...")
    result = subprocess.run([sys.executable, str(VIDEO_ANALYZER)], cwd=SCRAPER_DIR, capture_output=False)
    return result.returncode


def get_play_count(video: dict[str, Any]) -> int:
    """Safely parse play count for sorting."""
    try:
        return int(video.get("playCount") or 0)
    except (TypeError, ValueError):
        return 0


def contains_ai_keyword(video: dict[str, Any]) -> bool:
    """Mimic the old jq filter in Python."""
    text_parts = [
        video.get("text", ""),
        video.get("desc", ""),
        video.get("authorMeta", {}).get("name", ""),
        video.get("authorMeta", {}).get("nickName", ""),
    ]

    hashtags = video.get("hashtags") or []
    if isinstance(hashtags, list):
        text_parts.extend(str(tag) for tag in hashtags if tag)

    haystack = " ".join(str(part) for part in text_parts if part).lower()
    return "ai" in haystack


def filter_by_time_window(data: list, max_hours: int = 168) -> list:
    """Filter videos to only include those within time window."""
    now = datetime.now()
    filtered = []

    for video in data:
        dt = parse_video_datetime(video)
        if not dt:
            continue

        hours = (now - dt).total_seconds() / 3600.0
        if hours <= max_hours:
            filtered.append(video)

    return filtered


def filter_by_target_date(data: list, target_date: date | None) -> list:
    """Filter videos to a specific calendar date when requested."""
    if target_date is None:
        return data

    filtered = []
    for video in data:
        dt = parse_video_datetime(video)
        if not dt:
            continue
        if dt.date() == target_date:
            filtered.append(video)
    return filtered


def prepare_scraper_output() -> tuple[bool, int, str]:
    """
    Post-process scraper output before video analysis.

    Returns:
        (is_valid, kept_count, error_message)
    """
    if not DATA_FILE.exists():
        return False, 0, f"Data file not found: {DATA_FILE}"

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    target_date = get_target_date()
    print(f"  - Loaded {len(data)} videos from scraper")

    ai_filtered = [video for video in data if contains_ai_keyword(video)]
    print(f"  - After AI keyword filter: {len(ai_filtered)} videos")

    time_filtered = filter_by_time_window(ai_filtered, max_hours=168)
    print(f"  - After time filter (168h): {len(time_filtered)} videos")

    date_filtered = filter_by_target_date(time_filtered, target_date)
    if target_date is not None:
        print(f"  - After target date filter ({target_date.isoformat()}): {len(date_filtered)} videos")

    final_videos = sorted(date_filtered, key=get_play_count, reverse=True)[:10]
    for video in final_videos:
        video.pop("video_summary", None)

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(final_videos, f, ensure_ascii=False, indent=2)

    if not final_videos:
        if target_date is not None:
            return False, 0, f"No AI-related videos found for target date {target_date.isoformat()}"
        return False, 0, "No AI-related videos found after filtering"

    print(f"  - Keeping top {len(final_videos)} videos by play count")
    return True, len(final_videos), "OK"


def validate_scraper_output() -> tuple[bool, int, str]:
    """
    Validate scraper output.

    Returns:
        (is_valid, valid_count, error_message)
    """
    if not DATA_FILE.exists():
        return False, 0, f"Data file not found: {DATA_FILE}"

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    target_date = get_target_date()
    print(f"  - Loaded {len(data)} analyzed videos")

    filtered = filter_by_time_window(data, max_hours=168)
    print(f"  - After time filter (168h): {len(filtered)} videos")

    filtered = filter_by_target_date(filtered, target_date)
    if target_date is not None:
        print(f"  - After target date filter ({target_date.isoformat()}): {len(filtered)} videos")

    filtered = sorted(filtered, key=get_play_count, reverse=True)[:10]

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(filtered, f, ensure_ascii=False, indent=2)

    valid_count = sum(
        1
        for video in filtered
        if video.get("video_summary") and not str(video.get("video_summary", "")).startswith("ERROR")
    )

    print(f"  - Valid videos with summaries: {valid_count}")

    if valid_count < 3:
        return False, valid_count, f"Insufficient valid videos: {valid_count} (need at least 3)"

    return True, valid_count, "OK"


def main():
    if not check_dependencies():
        sys.exit(1)

    exit_code = run_tiktok_scraper()
    if exit_code != 0:
        print(f"ERROR: Scraper failed with exit code {exit_code}")
        sys.exit(1)

    is_ready, kept_count, error_msg = prepare_scraper_output()
    if not is_ready:
        print(f"ERROR: {error_msg}")
        sys.exit(1)

    print(f"  - Prepared {kept_count} videos for summary generation")

    exit_code = run_video_analyzer()
    if exit_code != 0:
        print(f"ERROR: Video analyzer failed with exit code {exit_code}")
        sys.exit(1)

    is_valid, valid_count, error_msg = validate_scraper_output()
    if not is_valid:
        print(f"ERROR: {error_msg}")
        sys.exit(1)

    print(f"\nPhase 1 complete: {valid_count} valid videos")
    sys.exit(0)


if __name__ == "__main__":
    main()
