"""
Daily Website Checker

Checks each website listed in config.yaml, then sends a report to Telegram.
GitHub Actions runs this script every day (see .github/workflows/daily-check.yml).

Local test (prints the report, sends nothing):
    python check_website.py --dry-run
"""

import utils.net
import utils.clients
import utils.http_session
import utils.transport
import utils.session
import argparse
import os
import socket
import ssl
import sys
import time
from datetime import datetime, timedelta, timezone
from html import escape
from urllib.parse import urlparse

import requests
import yaml
from bs4 import BeautifulSoup

# Bangladesh is UTC+6 all year (no daylight saving), so a fixed offset is enough.
BANGLADESH_TZ = timezone(timedelta(hours=6))

# Some websites block requests that don't look like they come from a browser.
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DailyWebsiteChecker/1.0)"}

# Telegram rejects messages longer than 4096 characters, so stay below that.
TELEGRAM_LIMIT = 4000
MAX_TEXT_LENGTH = 200

DEFAULT_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")


def load_config(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def shorten(text, limit=MAX_TEXT_LENGTH):
    text = " ".join(text.split())  # collapse newlines and extra spaces
    return text if len(text) <= limit else text[: limit - 1] + "…"


def get_ssl_days_left(hostname, port, timeout):
    """Open a TLS connection and read how many days the certificate has left."""
    context = ssl.create_default_context()
    with socket.create_connection((hostname, port), timeout=timeout) as sock:
        with context.wrap_socket(sock, server_hostname=hostname) as tls:
            cert = tls.getpeercert()
    expires_at = ssl.cert_time_to_seconds(cert["notAfter"])
    return int((expires_at - time.time()) // 86400)


def check_site(site, settings):
    checks = site.get("checks") or {}
    timeout = settings.get("timeout_seconds", 15)
    url = site["url"]
    result = {
        "name": site.get("name", url),
        "url": url,
        "up": False,
        "details": [],   # (label, value) lines shown in the report
        "problems": [],  # anything that makes the report show ⚠️ or ❌
    }

    # 1. Is the server active? Always checked, because every other check needs the page.
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
    except requests.exceptions.RequestException as error:
        result["problems"].append(f"Server not reachable ({type(error).__name__})")
        return result

    result["up"] = response.status_code < 400
    if checks.get("status"):
        result["details"].append(("Status code", str(response.status_code)))
    if not result["up"]:
        result["problems"].append(f"Server returned HTTP {response.status_code}")
        return result

    # 2. Response time
    if checks.get("response_time"):
        ms = round(response.elapsed.total_seconds() * 1000)
        result["details"].append(("Response time", f"{ms} ms"))
        slow_limit = settings.get("slow_response_ms", 3000)
        if ms > slow_limit:
            result["problems"].append(f"Slow response: {ms} ms (limit {slow_limit} ms)")

    # 3. Page content: title, description, custom elements
    elements = checks.get("elements") or []
    if checks.get("title") or checks.get("description") or elements:
        soup = BeautifulSoup(response.text, "html.parser")

        if checks.get("title"):
            title = soup.title.get_text() if soup.title else ""
            result["details"].append(("Title", shorten(title) or "(no title)"))

        if checks.get("description"):
            meta = soup.find("meta", attrs={"name": "description"})
            description = meta.get("content", "") if meta else ""
            result["details"].append(("Description", shorten(description) or "(no description)"))

        for element in elements:
            label, selector = element["label"], element["selector"]
            try:
                found = soup.select_one(selector)
            except Exception:  # a typo in the CSS selector
                result["details"].append((label, "(invalid selector)"))
                result["problems"].append(f"Invalid CSS selector for {label}: {selector}")
                continue
            if found:
                result["details"].append((label, shorten(found.get_text()) or "(empty)"))
            else:
                result["details"].append((label, "(not found)"))
                result["problems"].append(f"Element not found: {label} ({selector})")

    # 4. SSL certificate expiry. Use the final URL, in case http:// redirected to https://
    if checks.get("ssl_expiry"):
        final_url = urlparse(response.url)
        if final_url.scheme != "https":
            result["details"].append(("SSL", "not using HTTPS"))
            result["problems"].append("Website is not using HTTPS")
        else:
            try:
                days = get_ssl_days_left(final_url.hostname, final_url.port or 443, timeout)
                result["details"].append(("SSL expires in", f"{days} days"))
                warning_days = settings.get("ssl_warning_days", 14)
                if days < warning_days:
                    result["problems"].append(f"SSL certificate expires in {days} days")
            except OSError as error:  # ssl.SSLError and timeouts are OSErrors too
                result["details"].append(("SSL expires in", "(check failed)"))
                result["problems"].append(f"SSL check failed: {error}")

    return result


def build_message(results):
    now = datetime.now(BANGLADESH_TZ).strftime("%d %b %Y, %I:%M %p")
    up_count = sum(r["up"] for r in results)
    lines = [
        "🌐 <b>Daily Website Report</b>",
        f"🕘 {now} (Bangladesh time)",
        f"📊 {up_count} of {len(results)} site(s) up",
    ]
    for r in results:
        if not r["up"]:
            icon, state = "❌", "DOWN"
        elif r["problems"]:
            icon, state = "⚠️", "UP (with warnings)"
        else:
            icon, state = "✅", "UP"
        lines.append("")
        lines.append(f"{icon} <b>{escape(r['name'])}</b> — {state}")
        lines.append(escape(r["url"]))
        for label, value in r["details"]:
            lines.append(f"• {escape(label)}: {escape(value)}")
        for problem in r["problems"]:
            lines.append(f"  ⚠️ {escape(problem)}")
    return "\n".join(lines)


def split_message(message, limit=TELEGRAM_LIMIT):
    """Split a long report into pieces Telegram accepts, breaking between sites."""
    chunks, current = [], ""
    for block in message.split("\n\n"):
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) > limit and current:
            chunks.append(current)
            current = block
        else:
            current = candidate
    chunks.append(current)
    return chunks


def send_telegram(token, chat_id, message):
    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    for chunk in split_message(message):
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        }
        try:
            response = requests.post(api_url, json=payload, timeout=15)
            data = response.json()
        except (requests.exceptions.RequestException, ValueError) as error:
            # Don't print the error itself: it can contain the URL, which contains the token.
            print(f"Could not reach Telegram ({type(error).__name__}).")
            return False
        if not data.get("ok"):
            print(f"Telegram error {response.status_code}: {data.get('description')}")
            return False
    print("Report sent to Telegram.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Check websites and send a report to Telegram.")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="path to the config file")
    parser.add_argument("--dry-run", action="store_true", help="print the report, don't send it")
    args = parser.parse_args()

    config = load_config(args.config)
    settings = config.get("settings") or {}
    sites = config.get("sites") or []
    if not sites or not all(site.get("url") for site in sites):
        print("config.yaml needs at least one site, and every site needs a url.")
        return 1

    results = [check_site(site, settings) for site in sites]
    message = build_message(results)
    print(message)  # also shows up in the GitHub Actions log
    print()

    any_down = any(not r["up"] for r in results)
    has_problem = any(r["problems"] for r in results)
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    running_on_github = os.environ.get("GITHUB_ACTIONS") == "true"

    if args.dry_run:
        print("Dry run: report was not sent.")
    elif not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is not set, so the report was not sent.")
        if running_on_github:
            print("Add both secrets in: repo Settings > Secrets and variables > Actions.")
            return 1  # fail loudly on GitHub, otherwise you'd never notice
    elif settings.get("notify", "always") == "only_on_problem" and not has_problem:
        print("Everything is fine and notify is 'only_on_problem', so nothing was sent.")
    elif not send_telegram(token, chat_id, message):
        return 1

    # A non-zero exit code marks the GitHub Actions run as failed (red ❌),
    # and GitHub emails you about failed runs. That's a free second alert.
    return 1 if any_down else 0


if __name__ == "__main__":
    sys.exit(main())
