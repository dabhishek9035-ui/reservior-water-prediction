from __future__ import annotations

import re

_NUM = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?")
SAFETY = re.compile(r"\b(evacuat\w+|safe to|is it safe|release\w*|gates?|open the gates|flood warning|emergency|danger\w*|rescue|should (?:we|i|people))\b", re.I)
SAFETY_FOOTER = "_This assistant only reports the app's data and forecasts. It is not an official flood warning — for safety decisions follow your district/state disaster-management authority and the dam operator._"


def _values(text: str) -> list[float]:
    out = []
    for m in _NUM.finditer(text):
        try:
            out.append(abs(float(m.group().replace(",", ""))))
        except ValueError:
            pass
    return out


def check_numbers(answer: str, facts: str) -> list[str]:
    """Numbers in the answer that do not appear in FACTS (small integers and years are ignored)."""
    allowed = _values(facts)
    bad: list[str] = []
    for m in _NUM.finditer(answer):
        raw = m.group()
        try:
            v = abs(float(raw.replace(",", "")))
        except ValueError:
            continue
        if v.is_integer() and (v < 100 or 1900 <= v <= 2100):
            continue
        dec = len(raw.split(".")[1]) if "." in raw else 0
        if any(round(a, dec) == round(v, dec) or abs(a - v) <= a * 0.0005 for a in allowed):
            continue
        bad.append(raw)
    return bad


def needs_safety_footer(message: str) -> bool:
    return bool(SAFETY.search(message))
