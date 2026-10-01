"""Minimal Telegram Bot API client (stdlib only)."""

import json
import urllib.error
import urllib.request

_API = "https://api.telegram.org/bot{token}/{method}"


class TelegramError(RuntimeError):
    pass


def call(token, method, payload=None, timeout=20):
    req = urllib.request.Request(
        _API.format(token=token, method=method),
        data=json.dumps(payload or {}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.load(resp)
    except urllib.error.HTTPError as e:
        try:
            body = json.load(e)
        except ValueError:
            raise TelegramError(f"HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise TelegramError(str(getattr(e, "reason", e))) from e
    if not body.get("ok"):
        raise TelegramError(body.get("description", "unknown error"))
    return body["result"]


def find_chats(token):
    """Chats that have messaged the bot recently, as (chat_id, display name)."""
    chats = {}
    for update in call(token, "getUpdates"):
        msg = update.get("message") or update.get("channel_post") or {}
        chat = msg.get("chat")
        if chat:
            name = chat.get("title") or " ".join(filter(None, [chat.get("first_name"), chat.get("last_name")]))
            chats[chat["id"]] = name or chat.get("username") or "?"
    return list(chats.items())


class Telegram:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id

    def send(self, text):
        """Send a message; never raises, so a Telegram hiccup can't stop the watcher."""
        try:
            call(self.token, "sendMessage", {"chat_id": self.chat_id, "text": text, "disable_web_page_preview": True})
            return True
        except TelegramError as e:
            print(f"  ! Telegram send failed: {e}")
            return False
