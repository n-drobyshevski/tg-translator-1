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
from translator.config import STATS_PATH

logger = logging.getLogger(__name__)

###############################################################################
# Public helpers                                                              #
###############################################################################


def load_messages() -> List[Dict[str, Any]]:
    if not os.path.exists(STATS_PATH):        return []
    with open(STATS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    msgs = data.get("messages", [])
    return msgs


def build_summary(messages: List[Dict[str, Any]], days: int = 10) -> Dict[str, List]:
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
            continue
    counts = [day_counter.get(label, 0) for label in labels]
    # logger.info("build_summary: labels=%s counts=%s", labels, counts)
    return {"labels": labels, "counts": counts}


def build_10d_channels(
    messages: List[Dict[str, Any]], days: int = 10
) -> Dict[str, Any]:
    today = date.today()
    labels = [(today - timedelta(days=d)).isoformat() for d in reversed(range(days))]
    per_chan: Dict[str, Counter[str]] = {}
    for evt in messages:
        # include every message that has a timestamp
        if not evt.get("timestamp"):
            continue
        chan = evt.get("source_channel_name") or evt.get("source_channel", "")
        ts = evt.get("timestamp")
        try:
            dt = datetime.datetime.fromisoformat(ts)
            day = dt.date().isoformat()
            per_chan.setdefault(chan, Counter())[day] += 1
        except ValueError:
            continue
    series = [
        {"label": chan, "data": [per_chan[chan].get(d, 0) for d in labels]}
        for chan in sorted(per_chan)
    ]
    return {"labels": labels, "series": series}


def build_hourly_matrix(messages: list[dict]) -> dict:
    counts = Counter()
    maxv = 0
    events_by_cell = defaultdict(list)
    for m in messages:
        # Accept both event_type and event field for 'create'
        evt = m.get("event_type") or m.get("event") or ""
        # Filter: only messages where event_type or event is 'create'
        if evt and evt != "create":
            continue
        ts = m.get("timestamp")
        if not ts:
            continue
        try:
            dt = datetime.datetime.fromisoformat(ts)
        except Exception as e:
            continue
        hour = dt.strftime("%H")
        dow = dt.strftime("%a")
        counts[(hour, dow)] += 1
        maxv = max(maxv, counts[(hour, dow)])
        events_by_cell[(hour, dow)].append(m)
    xLabels = [f"{h:02d}" for h in range(24)]
    yLabels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    data = [
        {
            "x": x,
            "y": y,
            "v": counts.get((x, y), 0),
            "events": events_by_cell.get((x, y), []),
        }
        for y in yLabels
        for x in xLabels
    ]
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
    return {"labels": labels, "counts": counts}


def build_throughput_latency(messages):
    """
    Returns data for a scatter plot: original_size vs translation_time.
    """
    scatter = [
        {
            "x": m.get("original_size", 0),
            "y": m.get("translation_time", 0),
            "label": m.get("source_channel_name", "") or m.get("source_channel", ""),
            "id": m.get("message_id"),  # <-- Add message_id for tooltip
        }
        for m in messages
        if m.get("original_size") is not None and m.get("translation_time") is not None
    ]
    return {"points": scatter}
