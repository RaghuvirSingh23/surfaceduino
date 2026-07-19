"""Agent runners for SurfaceOS agent console mode.

Each runner accepts a config dict and returns a result dict with a 'kind' field
that the frontend uses to decide how to render the tile.

Result shapes:
  {"kind": "clock",   "time": str, "date": str | None}
  {"kind": "text",    "text": str}
  {"kind": "list",    "items": [str, ...]}
  {"kind": "stocks",  "entries": [{"ticker", "price", "change_pct", "signal?"}]}
  {"kind": "metric",  "value": str | float, "unit": str, "label": str | None}
  {"kind": "error",   "message": str}
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Any


def run_agent(agent_cfg: dict[str, Any]) -> dict[str, Any]:
    kind = agent_cfg.get("type", "")
    cfg: dict[str, Any] = agent_cfg.get("config", {})
    try:
        if kind == "clock":
            return _clock(cfg)
        if kind == "note":
            return _note(cfg)
        if kind == "news":
            return _news(cfg)
        if kind == "stocks":
            return _stocks(cfg)
        if kind == "ai_query":
            return _ai_query(cfg)
        if kind == "metric":
            return _metric(cfg)
        return {"kind": "error", "message": f"Unknown agent type: {kind!r}"}
    except Exception as exc:
        return {"kind": "error", "message": str(exc)}


def load_presets(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"active": "", "presets": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── runners ──────────────────────────────────────────────────────────────────

def _clock(cfg: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now()
    fmt = cfg.get("format", "24h")
    show_seconds = cfg.get("show_seconds", False)
    show_date = cfg.get("show_date", True)

    if fmt == "12h":
        time_str = now.strftime("%I:%M:%S %p" if show_seconds else "%I:%M %p").lstrip("0")
    else:
        time_str = now.strftime("%H:%M:%S" if show_seconds else "%H:%M")

    date_str: str | None = None
    if show_date:
        date_str = now.strftime("%A, %B %-d")

    return {"kind": "clock", "time": time_str, "date": date_str}


def _note(cfg: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "text", "text": cfg.get("text", "")}


def _news(cfg: dict[str, Any]) -> dict[str, Any]:
    source = cfg.get("source", "hackernews")
    max_items = min(int(cfg.get("max_items", 4)), 10)

    if source == "hackernews":
        return _news_hackernews(max_items)
    if source == "bbc_tech":
        return _news_rss("http://feeds.bbci.co.uk/news/technology/rss.xml", max_items)
    if source == "techcrunch":
        return _news_rss("https://techcrunch.com/feed/", max_items)
    return {"kind": "list", "items": [f"Unknown news source: {source!r}"]}


def _news_hackernews(max_items: int) -> dict[str, Any]:
    req = urllib.request.Request(
        "https://hacker-news.firebaseio.com/v0/topstories.json",
        headers={"User-Agent": "SurfaceOS/1.0"},
    )
    with urllib.request.urlopen(req, timeout=6) as resp:
        ids: list[int] = json.loads(resp.read())

    items: list[str] = []
    for sid in ids[:max_items]:
        item_req = urllib.request.Request(
            f"https://hacker-news.firebaseio.com/v0/item/{sid}.json",
            headers={"User-Agent": "SurfaceOS/1.0"},
        )
        with urllib.request.urlopen(item_req, timeout=4) as resp:
            story = json.loads(resp.read())
        title = story.get("title", "")
        score = story.get("score", 0)
        if title:
            items.append(f"[{score}] {title}")

    return {"kind": "list", "items": items}


def _news_rss(url: str, max_items: int) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "SurfaceOS/1.0"})
    with urllib.request.urlopen(req, timeout=6) as resp:
        content = resp.read().decode("utf-8", errors="replace")

    items: list[str] = []
    for chunk in content.split("<item>")[1:max_items + 1]:
        title_start = chunk.find("<title>")
        title_end = chunk.find("</title>")
        if title_start != -1 and title_end != -1:
            raw = chunk[title_start + 7:title_end]
            title = raw.replace("<![CDATA[", "").replace("]]>", "").strip()
            items.append(title)

    return {"kind": "list", "items": items}


def _stocks(cfg: dict[str, Any]) -> dict[str, Any]:
    tickers: list[str] = cfg.get("tickers", [])
    algo: str = cfg.get("algo", "price_change")
    period: str = cfg.get("period", "1d")

    try:
        import yfinance as yf  # type: ignore[import]
    except ImportError:
        return _stocks_simulated(tickers, algo)

    entries = []
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            if len(hist) < 2:
                entries.append({"ticker": ticker, "price": 0.0, "change_pct": 0.0, "signal": "no data"})
                continue
            prev = float(hist["Close"].iloc[-2])
            curr = float(hist["Close"].iloc[-1])
            change_pct = (curr - prev) / prev * 100 if prev else 0.0
            signal = _compute_signal(hist["Close"].tolist(), algo)
            entries.append({
                "ticker": ticker,
                "price": round(curr, 2),
                "change_pct": round(change_pct, 2),
                "signal": signal,
            })
        except Exception as exc:
            entries.append({"ticker": ticker, "price": 0.0, "change_pct": 0.0, "signal": f"err: {exc}"})

    return {"kind": "stocks", "entries": entries}


def _stocks_simulated(tickers: list[str], algo: str) -> dict[str, Any]:
    import random
    import hashlib
    entries = []
    for t in tickers:
        seed = int(hashlib.md5(t.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed + int(datetime.now().strftime("%Y%m%d%H")))
        price = round(rng.uniform(80, 600), 2)
        change = round(rng.uniform(-3.5, 3.5), 2)
        entries.append({"ticker": t, "price": price, "change_pct": change, "signal": "~simulated"})
    return {"kind": "stocks", "entries": entries, "note": "install yfinance for live data"}


def _compute_signal(closes: list[float], algo: str) -> str:
    if algo == "rsi_momentum":
        if len(closes) < 14:
            return "—"
        gains = [max(closes[i] - closes[i - 1], 0) for i in range(-14, 0)]
        losses = [max(closes[i - 1] - closes[i], 0) for i in range(-14, 0)]
        avg_gain = sum(gains) / 14 or 1e-9
        avg_loss = sum(losses) / 14 or 1e-9
        rsi = 100 - (100 / (1 + avg_gain / avg_loss))
        if rsi > 70:
            return "overbought"
        if rsi < 30:
            return "oversold"
        return f"RSI {rsi:.0f}"
    if algo == "volume_spike":
        return "—"
    return ""


def _ai_query(cfg: dict[str, Any]) -> dict[str, Any]:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"kind": "text", "text": "Set ANTHROPIC_API_KEY to enable AI tiles."}

    now = datetime.now()
    prompt: str = cfg.get("prompt", "")
    prompt = prompt.replace("{date}", now.strftime("%Y-%m-%d")).replace("{time}", now.strftime("%H:%M"))

    system: str = cfg.get("system", "You are a concise assistant. Never add preamble or sign-off.")
    model: str = cfg.get("model", "claude-haiku-4-5-20251001")
    max_tokens: int = int(cfg.get("max_tokens", 200))

    body = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())

    text: str = data["content"][0]["text"] if data.get("content") else ""
    return {"kind": "text", "text": text.strip()}


def _metric(cfg: dict[str, Any]) -> dict[str, Any]:
    url: str = cfg.get("url", "")
    if not url:
        return {"kind": "error", "message": "No URL configured"}

    headers: dict[str, str] = cfg.get("headers", {})
    req = urllib.request.Request(url, headers={"User-Agent": "SurfaceOS/1.0", **headers})

    with urllib.request.urlopen(req, timeout=6) as resp:
        data = json.loads(resp.read())

    def _dig(obj: Any, path: str) -> Any:
        for key in path.split("."):
            if not key:
                continue
            if isinstance(obj, dict):
                obj = obj.get(key)
            elif isinstance(obj, (list, tuple)):
                try:
                    obj = obj[int(key)]
                except (IndexError, ValueError):
                    return None
            else:
                return None
        return obj

    value = _dig(data, cfg.get("value_path", ""))
    label = _dig(data, cfg.get("label_path", ""))
    return {
        "kind": "metric",
        "value": value,
        "unit": cfg.get("unit", ""),
        "label": str(label) if label is not None else None,
    }
