import ssl
import urllib.request
import urllib.parse
import json


def _get_ssl_context():
    """Try default SSL, fall back to unverified if certs are broken."""
    try:
        ctx = ssl.create_default_context()
        urllib.request.urlopen("https://api.telegram.org", timeout=5, context=ctx)
        return ctx
    except ssl.SSLError:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    except Exception:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx


_ssl_ctx = None


def get_ssl_ctx():
    global _ssl_ctx
    if _ssl_ctx is None:
        _ssl_ctx = _get_ssl_context()
    return _ssl_ctx


def telegram_request(url, data=None, timeout=10):
    """Make a request to Telegram API with SSL fallback."""
    ctx = get_ssl_ctx()
    if data and isinstance(data, dict):
        data = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=data) if data else urllib.request.Request(url)
    return urllib.request.urlopen(req, timeout=timeout, context=ctx)


def telegram_get_updates(bot_token):
    """Delete webhook and fetch pending updates. Returns list of chat IDs found."""
    del_url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook"
    telegram_request(del_url, timeout=5)

    url = f"https://api.telegram.org/bot{bot_token}/getUpdates?timeout=5"
    response = telegram_request(url, timeout=15)
    result = json.loads(response.read().decode())

    chat_ids = set()
    if result.get("ok") and result.get("result"):
        for update in result["result"]:
            for key in ("message", "my_chat_member", "edited_message", "channel_post"):
                msg = update.get(key)
                if isinstance(msg, dict):
                    chat = msg.get("chat")
                    if chat and chat.get("id"):
                        chat_ids.add(str(chat["id"]))
    return chat_ids


def telegram_send(bot_token, chat_id, message, parse_mode=None):
    """Send a message to a specific chat. Returns True on success."""
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    telegram_request(api_url, data=payload, timeout=10)
    return True
