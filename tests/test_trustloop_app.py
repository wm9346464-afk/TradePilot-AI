"""Streamlit AppTest coverage for the v0 Deal Room."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parent.parent / "app_trustloop.py"


def test_trustloop_deal_room_runs_full_demo():
    at = AppTest.from_file(str(APP_PATH)).run(timeout=30)
    assert not at.exception

    button = next(item for item in at.button if item.label == "Review deal & build ladder")
    button.click().run(timeout=30)

    assert not at.exception

    for stage in (1, 2, 3):
        approval = next(
            item for item in at.button if item.label.startswith(f"Approve stage {stage}")
        )
        approval.click().run(timeout=30)
        assert not at.exception

    assert any("Trust Passport" in item.value for item in at.markdown)
    assert any("PAID" in item.value for item in at.markdown)
    assert any(metric.label == "Invoice currency" and metric.value == "USD" for metric in at.metric)

