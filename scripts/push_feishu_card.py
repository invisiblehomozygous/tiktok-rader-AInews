#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path

import requests

from feishu_notify import error_notifications_enabled


SCRIPT_DIR = Path(__file__).resolve().parent
ENV_FILE = SCRIPT_DIR / ".env"
WRITE_BITABLE_SCRIPT = SCRIPT_DIR / "write_bitable.py"


def load_env(path: Path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def get_tenant_token(app_id: str, app_secret: str) -> str:
    resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"tenant token failed: {data}")
    return data["tenant_access_token"]


def push_webhook(webhook_url: str, payload: dict):
    resp = requests.post(
        webhook_url,
        headers={"Content-Type": "application/json; charset=utf-8"},
        json=payload,
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") not in (0, None):
        raise RuntimeError(f"webhook push failed: {data}")
    return data


def push_card(token: str, chat_id: str, card_payload: dict):
    resp = requests.post(
        "https://open.feishu.cn/open-apis/im/v1/messages",
        params={"receive_id_type": "chat_id"},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        json={
            "receive_id": chat_id,
            "msg_type": "interactive",
            "content": json.dumps(card_payload["card"], ensure_ascii=False),
        },
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"push failed: {data}")
    return data


def push_text(token: str, chat_id: str, text: str):
    resp = requests.post(
        "https://open.feishu.cn/open-apis/im/v1/messages",
        params={"receive_id_type": "chat_id"},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        json={
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        },
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"push failed: {data}")
    return data


def push_via_best_channel(card_payload: dict | None = None, error_msg: str | None = None, chat_id: str | None = None):
    load_env(ENV_FILE)

    if error_msg and not error_notifications_enabled(os.environ):
        print("Feishu error notifications disabled; skipping push")
        return {"skipped": True, "reason": "error notifications disabled"}

    webhook_url = os.environ.get("FEISHU_WEBHOOK", "")
    if webhook_url:
        if error_msg:
            return push_webhook(
                webhook_url,
                {
                    "msg_type": "text",
                    "content": {"text": f"TikTok Radar Pipeline 运行失败\n{error_msg}"},
                },
            )
        if not card_payload:
            raise RuntimeError("Card payload is required for webhook push")
        return push_webhook(webhook_url, card_payload)

    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    resolved_chat_id = chat_id or os.environ.get("FEISHU_CHAT_ID", "")

    if not app_id or not app_secret or not resolved_chat_id:
        raise RuntimeError("Missing FEISHU_WEBHOOK or FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_CHAT_ID")

    token = get_tenant_token(app_id, app_secret)

    if error_msg:
        return push_text(token, resolved_chat_id, f"TikTok Radar Pipeline 运行失败\n{error_msg}")
    if not card_payload:
        raise RuntimeError("Card payload is required")
    return push_card(token, resolved_chat_id, card_payload)


def maybe_write_bitable(report_per_video_path: Path | None):
    if not WRITE_BITABLE_SCRIPT.exists():
        return
    if not report_per_video_path or not report_per_video_path.exists():
        print("\n[WARN] Skip bitable: report_per_video.json not found")
        return

    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        import write_bitable

        with open(report_per_video_path, "r", encoding="utf-8") as f:
            report = json.load(f)
        written = write_bitable.write_to_bitable(report)
        print(f"[INFO] Bitable write complete: {written} records")
    except Exception as e:
        print(f"[WARN] Bitable write failed: {e}")


def push_feishu_card(
    card_path: Path = None,
    error_msg: str = None,
    report_path: Path = None,
    report_per_video_path: Path = None,
    chat_id: str = None,
) -> dict:
    if error_msg:
        return push_via_best_channel(error_msg=error_msg, chat_id=chat_id)

    if not card_path or not card_path.exists():
        raise RuntimeError("Card file not found")

    card_payload = json.loads(card_path.read_text(encoding="utf-8"))
    result = push_via_best_channel(card_payload=card_payload, chat_id=chat_id)
    maybe_write_bitable(report_per_video_path)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--card")
    ap.add_argument("--error")
    ap.add_argument("--report", default=None, help="report.json path for bitable (category-level)")
    ap.add_argument("--report-per-video", default=None, help="report_per_video.json path for bitable (per-video, preferred)")
    ap.add_argument("--chat-id", default=os.environ.get("FEISHU_CHAT_ID", ""))
    args = ap.parse_args()

    if not args.card and not args.error:
        raise SystemExit("Either --card or --error is required")

    result = push_feishu_card(
        card_path=Path(args.card) if args.card else None,
        error_msg=args.error,
        report_path=Path(args.report) if args.report else None,
        report_per_video_path=Path(args.report_per_video) if args.report_per_video else None,
        chat_id=args.chat_id,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
