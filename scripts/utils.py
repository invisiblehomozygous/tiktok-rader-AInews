"""
Shared utilities for TikTok Feishu Radar scripts.

Common functions used across multiple scripts to avoid duplication.
"""

import math
import os
from pathlib import Path
from datetime import datetime
from typing import Optional


def load_env(env_file: Path = None) -> dict:
    """
    Load environment variables from .env file.
    
    Args:
        env_file: Path to .env file. If None, looks in script directory.
        
    Returns:
        Dictionary of environment variables
    """
    if env_file is None:
        env_file = Path(__file__).parent / ".env"
    
    env_vars = {}
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    
    return env_vars


def parse_video_datetime(video: dict) -> Optional[datetime]:
    """
    Parse video create time from createTime/createTimeISO safely.
    
    Priority:
    1. Numeric unix timestamp (seconds or milliseconds)
    2. Numeric string unix timestamp
    3. ISO string (from createTimeISO or createTime)
    
    Args:
        video: Video dict with createTime and/or createTimeISO fields
        
    Returns:
        datetime object or None if parsing fails
    """
    create_time = video.get('createTime')
    create_time_iso = video.get('createTimeISO')

    # Priority 1: numeric unix timestamp in seconds or milliseconds
    if isinstance(create_time, (int, float)):
        ts = float(create_time)
        if ts > 1e12:  # milliseconds
            ts = ts / 1000.0
        return datetime.fromtimestamp(ts)

    # Priority 2: numeric string unix timestamp
    if isinstance(create_time, str) and create_time.isdigit():
        ts = float(create_time)
        if ts > 1e12:
            ts = ts / 1000.0
        return datetime.fromtimestamp(ts)

    # Priority 3: ISO string
    iso_src = create_time_iso if isinstance(create_time_iso, str) else create_time
    if isinstance(iso_src, str) and iso_src:
        try:
            return datetime.fromisoformat(iso_src.replace('Z', '+00:00')).replace(tzinfo=None)
        except ValueError:
            pass

    return None


def calculate_days_ago(video: dict) -> str:
    """
    Calculate days ago from video object.
    
    Args:
        video: Video dict with timestamp fields
        
    Returns:
        Days ago as string (e.g., "3" or "?" if unknown)
    """
    try:
        video_time = parse_video_datetime(video)
        if not video_time:
            return "?"
        now = datetime.now()
        delta = now - video_time
        return str(max(1, delta.days))
    except Exception:
        return "?"


def summarize_video_time_window(videos: list[dict]) -> tuple[int, str]:
    """Return the actual time span covered by the provided videos."""
    dt_list = [parse_video_datetime(video) for video in videos]
    dt_list = [dt for dt in dt_list if dt is not None]

    if not dt_list:
        return 0, "Unknown"

    min_time = min(dt_list)
    max_time = max(dt_list)
    span_hours = (max_time - min_time).total_seconds() / 3600.0
    period_hours = max(1, math.ceil(span_hours))
    time_range = f"{min_time.strftime('%Y/%m/%d %H:%M')} - {max_time.strftime('%Y/%m/%d %H:%M')}"
    return period_hours, time_range
