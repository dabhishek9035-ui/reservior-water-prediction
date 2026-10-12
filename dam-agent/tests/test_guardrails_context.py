from app.config import settings
from app.context import build_messages, est_tokens
from app.guardrails import check_numbers, needs_safety_footer
from app.schemas import PageContext
from app.tools.base import ToolResult


def test_number_grounding():
    facts = "- Level on 2026-09-27: 2,147.7 ft\n- change -0.86 ft"
    assert check_numbers("The level was 2,147.7 ft on 27 September 2026.", facts) == []
    assert check_numbers("It dropped 0.86 ft.", facts) == []
    assert check_numbers("The level was 2,150.3 ft.", facts) == ["2,150.3"]


def test_safety_footer_trigger():
    assert needs_safety_footer("Should we evacuate if Bhadra overflows?")
    assert not needs_safety_footer("How full is Bhadra?")


def test_context_budget_truncates_facts():
    dams = [{"id": "x", "name": "X", "district": "D"}]
    big = ToolResult("t", "Big", [f"- line {i} " + "word " * 30 for i in range(400)])
    b = build_messages(dams=dams, page=PageContext(), history=[], question="q?", results=[big], latest="2026-01-01", s=settings)
    assert b.stats["facts_truncated"] is True
    total = sum(est_tokens(m["content"]) for m in b.messages)
    assert total < settings.num_ctx - settings.max_new_tokens
