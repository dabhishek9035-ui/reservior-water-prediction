"""Deterministic intent + entity router.

A 7B model is unreliable at choosing tools, so Python decides WHAT data to fetch and the
LLM only writes the answer from those facts. (Native LLM tool-calling can be added later.)"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from .memory import Session
from .schemas import PageContext

SNAP = (1, 7, 14, 30)
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

# order = priority of the *primary* intent
INTENT_PATTERNS: list[tuple[str, str]] = [
    ("forecast", r"\b(predict\w*|forecast\w*|will\b|going to|expected?|outlook|tomorrow|next (?:day|week|month|\d+ ?days?)|in (?:a|the next|\d+) (?:days?|weeks?|months?)|future|ahead)\b"),
    ("performance", r"\b(accura\w+|error|mae|rmse|backtest\w*|how good|reliab\w+|trust|confiden\w+|persistence|beat\w*|skill|performance|evaluat\w+)\b"),
    ("model", r"\b(model|lstm|algorithm|neural|trained|training|architecture|features?|strateg\w+|baseline|how (?:does|do|is|are) (?:the )?(?:forecast|prediction)s?\b)"),
    ("sources", r"\b(sources?|datasets?|data from|where (?:does|do|is|are) .{0,20}data|provided by|collected|measured|observations?|update frequency|how often|refresh\w*|api)\b"),
    ("compare", r"\b(compar\w+|versus|vs\.?|which (?:dam|reservoir)|highest|lowest|fullest|emptiest|rank\w*|all (?:the )?(?:dams|reservoirs))\b"),
    ("region", r"\b(regions?|places?|near\w*|affect\w*|overflow\w*|flood\w*|downstream|districts?|villages?|towns?|people|evacuat\w+|nearby|around|surround\w*|taluks?|impact\w*)\b"),
    ("history", r"\b(history|histor\w+|past|trends?|last \d+|previous\w*|changed?|recent\w*|since|rose|dropped|fell|rising|falling)\b"),
    ("level", r"\b(levels?|how full|full\b|current\w*|now|today|latest|status|fill\w*|percent\w*|%|waterline)\b"),
    ("info", r"\b(about|details?|capacity|storage|built|construct\w+|purpose|river|located|location|where is|catchment|frl|information|info)\b"),
    ("help", r"\b(how (?:do|can) i|how to|what can (?:you|i)|use (?:the )?(?:app|page)|date picker|toggle|slider|window|step through|play button)\b"),
    ("glossary", r"\b(what (?:is|does|are)|meaning of|define|stands? for|explain)\b"),
]
DOMAIN = re.compile(r"\b(dams?|reservoirs?|water|levels?|forecast\w*|predict\w*|model|data|datasets?|rivers?|regions?|flood\w*|overflow\w*|capacity|storage|frl|tmc|rain\w*|lstm|delta|mae|rmse|baseline|catchment|inflow|outflow|horizon|persistence|confidence|backtest|as-of|app|page|chart|graph|karnataka|district|jaladrishti)\b", re.I)
OFFTOPIC = re.compile(r"\b(poem|joke|song|recipe|python|javascript|code|bitcoin|crypto|stock|cricket|movie|politic\w*|homework|essay|translate)\b", re.I)
GREETING = re.compile(r"^\s*(hi|hello|hey|namaste|namaskara|good (?:morning|afternoon|evening)|thanks|thank you)\b", re.I)
FOLLOWUP = re.compile(r"\b(it|its|this|that|there|same|the dam|this dam|that dam|here)\b", re.I)


@dataclass
class Plan:
    intent: str
    dam_ids: list[str] = field(default_factory=list)
    horizon: Optional[int] = None
    as_of: Optional[str] = None
    window_days: Optional[int] = None
    calls: list[tuple[str, dict]] = field(default_factory=list)
    canned: Optional[str] = None
    matched: list[str] = field(default_factory=list)


def _norm(name: str) -> str:
    return re.sub(r"\b(dam|reservoir|lake)\b", "", name.lower()).strip()


def extract_dams(text: str, dams: list[dict]) -> list[str]:
    low = text.lower()
    found: list[tuple[int, str]] = []
    words = [w for w in re.findall(r"[a-z]{4,}", low)]
    for d in dams:
        names = {_norm(d["name"]), _norm(d.get("reservoir") or ""), d["id"].lower(), *[a.lower() for a in d.get("aliases", [])]}
        names.discard("")
        pos = -1
        for n in names:
            m = re.search(rf"\b{re.escape(n)}\b", low)
            if m:
                pos = m.start() if pos < 0 else min(pos, m.start())
        if pos < 0:
            heads = {n.split()[0] for n in names if n.split()}
            for w in words:
                if difflib.get_close_matches(w, heads, n=1, cutoff=0.84):
                    pos = low.find(w)
                    break
        if pos >= 0:
            found.append((pos, d["id"]))
    return [i for _, i in sorted(found)]


def extract_horizon(text: str) -> Optional[int]:
    low = text.lower()
    m = re.search(r"\b(\d{1,3})\s*-?\s*(?:day|days|d)\b", low)
    if m:
        return min(SNAP, key=lambda x: abs(x - int(m.group(1))))
    if re.search(r"\b(tomorrow|next day|one day)\b", low):
        return 1
    if re.search(r"\b(two weeks?|fortnight)\b", low):
        return 14
    if re.search(r"\b(month)\b", low):
        return 30
    if re.search(r"\b(week)\b", low):
        return 7
    return None


def extract_as_of(text: str, latest: date) -> Optional[str]:
    low = text.lower()
    d: Optional[date] = None
    if m := re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", low):
        d = _safe(int(m[1]), int(m[2]), int(m[3]))
    elif m := re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3})[a-z]*\.?,?\s+(\d{4})\b", low):
        d = _safe(int(m[3]), MONTHS.get(m[2], 0), int(m[1]))
    elif m := re.search(r"\b([a-z]{3})[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", low):
        d = _safe(int(m[3]), MONTHS.get(m[1], 0), int(m[2]))
    elif re.search(r"\b(a|one|1) year ago\b", low):
        d = latest - timedelta(days=365)
    elif m := re.search(r"\b(\d{1,3}) (day|week|month)s? ago\b", low):
        d = latest - timedelta(days=int(m[1]) * {"day": 1, "week": 7, "month": 30}[m[2]])
    return min(d, latest).isoformat() if d else None


def extract_window(text: str) -> Optional[int]:
    m = re.search(r"\b(?:last|past|previous)\s+(\d{1,3})\s*(day|week|month)s?\b", text.lower())
    return int(m[1]) * {"day": 1, "week": 7, "month": 30}[m[2]] if m else None


def _safe(y: int, mo: int, d: int) -> Optional[date]:
    try:
        return date(y, mo, d)
    except ValueError:
        return None


GREETING_TEXT = "Hi! I can answer questions about the reservoirs, their water levels and forecasts, the model, data sources, and the regions around each dam. Try: “How full is Bhadra?” or “What will the level be in 7 days?”"
OFFTOPIC_TEXT = "I can only help with this app's topics: dams and reservoirs, water levels, forecasts, the model, data sources, and regions around the reservoirs. Could you ask something along those lines?"


def make_plan(message: str, dams: list[dict], page: PageContext, session: Session, latest_iso: str) -> Plan:
    text = message.strip()
    latest = date.fromisoformat(latest_iso)
    mentioned = extract_dams(text, dams)
    words = len(text.split())

    if GREETING.match(text) and words <= 6 and not mentioned:
        return Plan("greeting", canned=GREETING_TEXT)
    in_scope = bool(mentioned) or bool(DOMAIN.search(text))
    if OFFTOPIC.search(text) and not mentioned and not DOMAIN.search(text):
        in_scope = False
    if not in_scope and session.turns and words <= 8 and not OFFTOPIC.search(text):
        in_scope = True   # short follow-up like "and for 14 days?"
    if not in_scope:
        return Plan("out_of_scope", canned=OFFTOPIC_TEXT)

    matched = [name for name, pat in INTENT_PATTERNS if re.search(pat, text, re.I)]
    # "how does the forecasting model work?" is about the model, not a request for a forecast
    meta = re.search(r"\b(how (?:does|do|is|are|did)|what (?:is|are)|explain|why)\b", text, re.I) and re.search(r"\b(model|lstm|algorithm|forecast\w*|prediction\w*|work\w*|trained)\b", text, re.I)
    if meta and not mentioned and extract_horizon(text) is None and "performance" not in matched:
        matched = [m for m in matched if m not in ("forecast", "level", "history", "glossary")]
        if "model" not in matched:
            matched.insert(0, "model")
    horizon = extract_horizon(text) or (page.horizon if page.horizon in SNAP else None) or (session.last_horizon if "forecast" in matched else None)
    as_of = extract_as_of(text, latest) or (page.as_of if page.as_of and page.as_of <= latest_iso else None)
    window = extract_window(text)

    if "performance" in matched and not re.search(r"\b(will|predict\w*)\b", text, re.I):
        matched = [m for m in matched if m != "forecast"]
    TERMS = r"\b(frl|mddl|tmc|cusec|dead storage|live storage|gross storage|catchment|persistence|mae|rmse|as-of|active range|horizon)\b"
    if not mentioned and re.search(r"\b(what (?:is|does|are)|meaning of|define|stands? for|explain)\b", text, re.I) and re.search(TERMS, text, re.I) and "model" not in matched:
        matched = ["glossary"]
    if "help" in matched and not mentioned:
        matched = ["help"]

    dam_ids = list(mentioned)
    if not dam_ids:
        for cand in (page.dam_id, session.last_dam_id):
            if cand and any(d["id"] == cand for d in dams):
                dam_ids = [cand]
                break
    if len(dams) == 1 and not dam_ids:
        dam_ids = [dams[0]["id"]]

    # only treat generic words as a primary intent if nothing more specific matched
    specific = [m for m in matched if m not in ("glossary", "help", "info", "level")]
    primary = specific[0] if specific else (matched[0] if matched else "unknown")
    plan = Plan(primary, dam_ids, horizon, as_of, window, matched=matched)
    dam = dam_ids[0] if dam_ids else None
    needs_dam = {"forecast", "performance", "history", "level"}

    if primary in needs_dam and not dam:
        names = ", ".join(d["name"] for d in dams[:12])
        plan.canned = f"Which reservoir do you mean? I have data for: {names}."
        return plan

    calls: list[tuple[str, dict]] = []
    h = horizon or 7
    if "forecast" in matched and dam:
        calls += [("get_forecast", {"dam_id": dam, "as_of": as_of, "horizon": h}), ("get_latest_level", {"dam_id": dam, "as_of": as_of})]
    if "performance" in matched and dam:
        calls += [("get_model_performance", {"dam_id": dam, "horizon": h, "n_days": 14}), ("search_knowledge", {"query": "confidence persistence baseline model performance", "k": 2})]
    if "model" in matched and "performance" not in matched:
        calls.append(("search_knowledge", {"query": text, "k": 3}))
    if "sources" in matched:
        calls.append(("search_knowledge", {"query": text + " data source", "k": 3}))
    if "compare" in matched:
        calls.append(("compare_dams", {"dam_ids": dam_ids if len(dam_ids) > 1 else None}))
    if "region" in matched:
        calls.append(("get_region_info", {"dam_id": dam, "query": text}))
    if "history" in matched and dam:
        calls.append(("get_history_summary", {"dam_id": dam, "as_of": as_of, "days": window or 90}))
    if "level" in matched and dam and "forecast" not in matched:
        calls.append(("get_latest_level", {"dam_id": dam, "as_of": as_of}))
    if "info" in matched:
        calls.append(("get_dam_info", {"dam_id": dam}) if dam else ("list_dams", {}))
    if "help" in matched:
        calls.append(("search_knowledge", {"query": "app guide " + text, "k": 3}))
    if "glossary" in matched and not calls:
        calls.append(("search_knowledge", {"query": text, "k": 3}))
    if not calls:   # in scope but unclear: give the model the dam basics + best notes
        if dam:
            calls += [("get_dam_info", {"dam_id": dam}), ("get_latest_level", {"dam_id": dam, "as_of": as_of})]
        calls.append(("search_knowledge", {"query": text, "k": 3}))

    seen, uniq = set(), []
    for name, args in calls:
        key = (name, tuple(sorted((k, str(v)) for k, v in args.items())))
        if key not in seen:
            seen.add(key)
            uniq.append((name, args))
    plan.calls = uniq[:4]
    return plan
