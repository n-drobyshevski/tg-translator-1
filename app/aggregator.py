"""aggregator.py – lightweight helpers only

This module has **no Flask side‑effects**.  It provides small utility
functions used by *flask_app.py* and by unit tests.
"""

from __future__ import annotations

import json
import datetime
import os
from collections import Counter, defaultdict
from datetime import timedelta, date, timezone
from pathlib import Path
from typing import Any, Dict, List
import logging

# Path to the JSON‑Lines or JSON stats file written by stats_logger.
# Update this if your stats logger writes somewhere else.
STATS_PATH = Path(__file__).resolve().parent.parent / "translator/cache" / "stats.json"

logger = logging.getLogger(__name__)

###############################################################################
# Public helpers                                                              #
###############################################################################


def load_messages() -> List[Dict[str, Any]]:
    logger.info("load_messages: reading STATS_PATH=%s", STATS_PATH)
    if not os.path.exists(STATS_PATH):
        logger.info("load_messages: file not found, returning empty list")
        return []
    with open(STATS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    msgs = data.get("messages", [])
    logger.info("load_messages: loaded %d messages", len(msgs))
    return msgs


def build_summary(messages: List[Dict[str, Any]], days: int = 10) -> Dict[str, List]:
    # logger.info("build_summary: messages=%d, days=%d", len(messages), days)
    today = date.today()
    labels = [(today - timedelta(days=d)).isoformat() for d in reversed(range(days))]
    day_counter: Counter[str] = Counter()
    for evt in messages:
        ts = evt.get("timestamp")
        if not ts:
            continue
        try:
            dt = datetime.datetime.fromisoformat(ts)
            day = dt.date().isoformat()
            # logger.info("build_summary: incrementing count for day %s", day)
            day_counter[day] += 1
        except ValueError as e:
            logger.info("build_summary: skip evt, parse error %s", e)
    counts = [day_counter.get(label, 0) for label in labels]
    # logger.info("build_summary: labels=%s counts=%s", labels, counts)
    return {"labels": labels, "counts": counts}


def build_10d_channels(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    logger.info("build_10d_channels: messages=%d", len(messages))
    today = date.today()
    labels = [(today - timedelta(days=d)).isoformat() for d in reversed(range(10))]
    per_chan: Dict[str, Counter[str]] = {}
    for evt in messages:
        if evt.get("event") != "create" or not evt.get("timestamp"):
            continue
        chan = evt.get("source_channel_name") or evt.get("source_channel", "")
        ts = evt.get("timestamp")
        if not ts:
            continue
        try:
            dt = datetime.datetime.fromisoformat(ts)
            day = dt.date().isoformat()
            per_chan.setdefault(chan, Counter())[day] += 1
        except ValueError as e:
            logger.info("build_10d_channels: skip evt, parse error %s", e)
    series = [
        {"label": chan, "data": [per_chan[chan].get(d, 0) for d in labels]}
        for chan in sorted(per_chan)
    ]
    logger.info("build_10d_channels: labels=%s series=%s", labels, series)
    return {"labels": labels, "series": series}


def build_hourly_matrix(messages: list[dict]) -> dict:
    # logger.info("build_hourly_matrix: messages=%d", len(messages))
    counts = Counter()
    maxv = 0
    for m in messages:
        if m.get("event") != "create" or not m.get("timestamp"):
            continue
        ts = m.get("timestamp")
        if not ts:
            continue
        try:
            dt = datetime.datetime.fromisoformat(ts)
        except Exception as e:
            logger.info("build_hourly_matrix: skip m, parse error %s", e)
            continue
        hour = dt.strftime("%H")
        dow = dt.strftime("%a")
        counts[(hour, dow)] += 1
        maxv = max(maxv, counts[(hour, dow)])
    xLabels = [f"{h:02d}" for h in range(24)]
    yLabels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    data = [{"x": x, "y": y, "v": counts.get((x, y), 0)} for y in yLabels for x in xLabels]
    # logger.info("build_hourly_matrix: xLabels=%s yLabels=%s max=%d", xLabels, yLabels, maxv)
    return {"data": data, "xLabels": xLabels, "yLabels": yLabels, "max": maxv}


def build_10d_by_channel(messages: list[dict]) -> dict:
    logger.info("build_10d_by_channel: messages=%d", len(messages))
    # use timezone-aware UTC now
    cutoff = datetime.datetime.now(timezone.utc) - datetime.timedelta(days=10)
    data = defaultdict(int)
    for m in messages:
        if m.get("event") != "create":
            continue
        ts = m.get("timestamp")
        if not ts:
            continue
        try:
            dt = datetime.datetime.fromisoformat(ts)
        except Exception as e:
            logger.info("build_10d_by_channel: skip m, parse error %s", e)
            continue
        if dt > cutoff:
            ch = m.get("source_channel_name", "Unknown")
            data[ch] += 1
    labels = list(data.keys())
    counts = [data[ch] for ch in labels]
    logger.info("build_10d_by_channel: labels=%s counts=%s", labels, counts)
    return {"labels": labels, "counts": counts}
