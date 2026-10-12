import json

from app.config import settings
from app.memory import Session
from app.router import extract_as_of, extract_dams, extract_horizon, make_plan
from app.schemas import PageContext
from datetime import date

DAMS = json.loads((settings.data_dir / "dams.json").read_text(encoding="utf-8"))
LATEST = "2026-09-27"


def plan(msg, page=None, sess=None):
    return make_plan(msg, DAMS, page or PageContext(), sess or Session(), LATEST)


def test_greeting_and_offtopic_are_canned():
    assert plan("hi").intent == "greeting" and plan("hello there").canned
    assert plan("write me a poem about cats").intent == "out_of_scope"


def test_dam_extraction_and_typos():
    assert extract_dams("how full is Bhadra today", DAMS) == ["bhadra"]
    assert extract_dams("what about bhadhra dam", DAMS) == ["bhadra"]
    assert extract_dams("tell me about lakkavalli", DAMS) == ["bhadra"]


def test_horizon_and_dates():
    assert extract_horizon("forecast for 10 days") == 7
    assert extract_horizon("what about tomorrow") == 1
    assert extract_horizon("in a month") == 30
    assert extract_as_of("as of 12 March 2026", date(2026, 9, 27)) == "2026-03-12"
    assert extract_as_of("on 2025-01-05", date(2026, 9, 27)) == "2025-01-05"
    assert extract_as_of("a year ago", date(2026, 9, 27)) == "2025-09-27"


def test_forecast_plan_uses_page_context():
    p = plan("what will the level be in 14 days?", PageContext(page="predictions", dam_id="bhadra"))
    assert p.intent == "forecast" and p.horizon == 14
    assert p.calls[0][0] == "get_forecast" and p.calls[0][1]["dam_id"] == "bhadra"


def test_level_history_region_model_sources():
    assert plan("how full is Bhadra?").calls[0][0] == "get_latest_level"
    assert plan("show the trend for Bhadra over the last 30 days").calls[0][0] == "get_history_summary"
    assert plan("which regions are affected if Bhadra overflows?").calls[0][0] == "get_region_info"
    assert plan("how does the forecasting model work?").calls[0][0] == "search_knowledge"
    assert plan("where does the data come from?").calls[0][0] == "search_knowledge"


def test_followup_uses_session_dam():
    s = Session(turns=[{"role": "user", "content": "x"}], last_dam_id="bhadra", last_horizon=7)
    p = plan("and the forecast for it?", sess=s)
    assert p.calls and p.calls[0][1]["dam_id"] == "bhadra"


def test_calls_capped():
    assert len(plan("forecast accuracy history region compare Bhadra").calls) <= 4
