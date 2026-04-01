"""
Feishu Notification Module

Sends error notifications to Feishu.
Webhook is preferred when FEISHU_WEBHOOK is configured.
"""

import json
import os
from pathlib import Path

import requests

from utils import load_env


SCRIPT_DIR = Path(__file__).resolve().parent
ENV_FILE = SCRIPT_DIR / ".env"


def _is_truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def error_notifications_enabled(env_vars: dict | None = None) -> bool:
    env_vars = env_vars or {}
    raw = os.environ.get(
        "FEISHU_ENABLE_ERROR_NOTIFICATIONS",
        env_vars.get("FEISHU_ENABLE_ERROR_NOTIFICATIONS", ""),
    )
    return _is_truthy(raw)


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


def push_webhook_text(webhook_url: str, text: str):
    resp = requests.post(
        webhook_url,
        headers={"Content-Type": "application/json; charset=utf-8"},
        json={"msg_type": "text", "content": {"text": text}},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") not in (0, None):
        raise RuntimeError(f"webhook push failed: {data}")
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


def push_error_notification(error_msg: str) -> bool:
    try:
        env_vars = load_env(ENV_FILE)
        if not error_notifications_enabled(env_vars):
            print("Feishu error notifications disabled; skipping push")
            return True

        webhook_url = env_vars.get("FEISHU_WEBHOOK", "")
        full_msg = f"TikTok Radar Pipeline 运行失败\n{error_msg}"

        if webhook_url:
            push_webhook_text(webhook_url, full_msg)
            print("Error notification sent to Feishu webhook")
            return True

        app_id = env_vars.get("FEISHU_APP_ID")
        app_secret = env_vars.get("FEISHU_APP_SECRET")
        chat_id = env_vars.get("FEISHU_CHAT_ID")

        if not all([app_id, app_secret, chat_id]):
            print("Warning: Feishu credentials not configured, skipping notification")
            return False

        token = get_tenant_token(app_id, app_secret)
        push_text(token, chat_id, full_msg)
        print("Error notification sent to Feishu")
        return True

    except Exception as e:
        print(f"Failed to send Feishu notification: {e}")
        return False


if __name__ == "__main__":
    import sys

    msg = sys.argv[1] if len(sys.argv) > 1 else "Test error message"
    push_error_notification(msg)
