"""Telegram approvals: the owner approves or rejects from her phone.

Env: TELEGRAM_BOT_TOKEN (from @BotFather), TELEGRAM_CHAT_ID (the owner's chat id;
only this chat may approve anything). Run: python -m closecrew.telegram_bot
Commands: /status  /pending  /run
"""

from __future__ import annotations

import os
import time

import httpx

from .explainer import LABELS
from .models import money

API = "https://api.telegram.org/bot{token}/{method}"


def _call(method: str, **payload):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return None
    r = httpx.post(API.format(token=token, method=method), json=payload, timeout=40)
    return r.json()


def _owner() -> str:
    return os.environ.get("TELEGRAM_CHAT_ID", "")


def item_message(x: dict) -> tuple[str, dict]:
    text = (f"*{LABELS.get(x['cause'], x['cause'])}* · {money(x['impact'])}\n{x['explanation']}"
            + (f"\n_Suggested:_ {x['action']}" if x.get("action") else "")
            + (f"\n_Entry:_ {x['proposed_entry']['description']}" if x.get("proposed_entry") else "")
            + f"\n`{x['id']}`")
    kb = {"inline_keyboard": [[{"text": "✅ Approve", "callback_data": f"a:{x['id']}"},
                               {"text": "✋ Reject", "callback_data": f"r:{x['id']}"}]]}
    return text, kb


def status_text(res: dict) -> str:
    s = res["summary"]
    return (f"*CloseCrew · {res['period']}* · {s['status'].replace('_', ' ')}\n"
            f"Difference {money(s['diff_before'])} → {money(s['diff_after'])}\n"
            f"Auto-fixed {s['auto_fixed']} · approved {s['approved']} · waiting {s['awaiting_approval']}\n"
            f"Auditor {s['checks_passed']}/{s['checks_total']} checks passed")


def notify_summary(res: dict) -> None:
    chat = _owner()
    if not chat:
        return
    _call("sendMessage", chat_id=chat, text=status_text(res), parse_mode="Markdown")
    for x in res["exceptions"]:
        if x["status"] == "open":
            text, kb = item_message(x)
            _call("sendMessage", chat_id=chat, text=text, parse_mode="Markdown", reply_markup=kb)


def handle(update: dict) -> None:
    from . import pipeline

    owner = _owner()
    if "callback_query" in update:
        cq = update["callback_query"]
        chat = str(cq["message"]["chat"]["id"])
        if chat != owner:
            _call("answerCallbackQuery", callback_query_id=cq["id"], text="Not authorised")
            return
        verb, exc_id = cq["data"].split(":", 1)
        who = cq["from"].get("first_name", "owner") + " (Telegram)"
        res = pipeline.decide(exc_id, "approved" if verb == "a" else "rejected", by=who)
        if res.get("rolled_back"):
            msg = "⚠️ Auditor objected, decision rolled back. Nothing changed."
        else:
            msg = ("✅ Approved" if verb == "a" else "✋ Rejected") + f" by {who}. " + res.get("action_result", "")
        _call("answerCallbackQuery", callback_query_id=cq["id"], text=msg[:190])
        _call("editMessageText", chat_id=chat, message_id=cq["message"]["message_id"],
              text=cq["message"].get("text", "") + "\n\n" + msg)
        _call("sendMessage", chat_id=chat, text=status_text(res), parse_mode="Markdown")
        return
    msg = update.get("message") or {}
    chat = str(msg.get("chat", {}).get("id", ""))
    text = (msg.get("text") or "").strip()
    if chat != owner:
        if text == "/start":
            _call("sendMessage", chat_id=chat, text=f"Your chat id is {chat}. Set TELEGRAM_CHAT_ID to it.")
        return
    if text in ("/status", "/start"):
        _call("sendMessage", chat_id=chat, text=status_text(pipeline.run(write_log=False)), parse_mode="Markdown")
    elif text == "/pending":
        res = pipeline.run(write_log=False)
        items = [x for x in res["exceptions"] if x["status"] == "open"]
        if not items:
            _call("sendMessage", chat_id=chat, text="Nothing waiting for you. 🎉")
        for x in items:
            t, kb = item_message(x)
            _call("sendMessage", chat_id=chat, text=t, parse_mode="Markdown", reply_markup=kb)
    elif text == "/run":
        notify_summary(pipeline.run(note="run requested from Telegram"))


def poll_forever() -> None:
    if not os.environ.get("TELEGRAM_BOT_TOKEN"):
        print("TELEGRAM_BOT_TOKEN not set; Telegram approvals disabled")
        return
    offset = 0
    print("CloseCrew Telegram bot polling…")
    while True:
        try:
            r = _call("getUpdates", offset=offset, timeout=30) or {}
            for u in r.get("result", []):
                offset = u["update_id"] + 1
                try:
                    handle(u)
                except Exception as e:  # keep the bot alive; report to owner
                    if _owner():
                        _call("sendMessage", chat_id=_owner(), text=f"Error: {e}"[:300])
        except Exception:
            time.sleep(5)


if __name__ == "__main__":
    poll_forever()
