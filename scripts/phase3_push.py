"""
Phase 3: Build and Push Feishu Card

Builds the Feishu card payload and pushes it to Feishu.
Shell should just call this and check exit code.
"""

import argparse
import sys
from pathlib import Path

# Add script directory to path for imports
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from build_feishu_payload import build_feishu_card
from push_feishu_card import push_feishu_card


def main():
    parser = argparse.ArgumentParser(description='Phase 3: Build and push Feishu card')
    parser.add_argument('--report', '-r', type=Path, required=True,
                        help='Path to report.json (for card building)')
    parser.add_argument('--report-per-video', type=Path, default=None,
                        help='Path to report_per_video.json (for bitable, preferred)')
    parser.add_argument('--raw', type=Path, required=True,
                        help='Path to filtered-result.json')
    parser.add_argument('--card-output', '-o', type=Path, default=None,
                        help='Path to write card JSON (optional)')
    args = parser.parse_args()
    
    # Determine card output path
    if args.card_output:
        card_file = args.card_output
    else:
        # Default: same directory as report
        card_file = args.report.parent / "feishu_card.json"
    
    # Build card
    print("📦 Building Feishu card...")
    try:
        build_feishu_card(
            report_path=args.report,
            raw_path=args.raw,
            output_path=card_file
        )
        print(f"✅ Card built: {card_file}")
    except Exception as e:
        print(f"ERROR: Card build failed: {e}")
        sys.exit(1)
    
    # Push card
    print("📤 Pushing to Feishu...")
    try:
        push_feishu_card(
            card_path=card_file,
            report_path=args.report,
            report_per_video_path=args.report_per_video
        )
        print("✅ Card pushed successfully")
    except Exception as e:
        print(f"ERROR: Card push failed: {e}")
        sys.exit(1)
    
    print("\n✅ Phase 3 complete")
    sys.exit(0)


if __name__ == "__main__":
    main()
