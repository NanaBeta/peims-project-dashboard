from pathlib import Path
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from analytics import DATASET_COLUMNS, compute, make_alerts, planned_percentage, select_project, validated_frame, weekly_report

ROOT = Path(__file__).parents[1] / "data"

@pytest.fixture()
def data():
    return {name: validated_frame(name, pd.read_csv(ROOT / f"{name}.csv")) for name in DATASET_COLUMNS}


def test_dataset_weights_and_costs(data):
    for pid in data["projects"]["project_id"]:
        result = compute(select_project(data, pid))
        assert result["activities"]["weight"].sum() == pytest.approx(100)
        assert result["kpi"]["budget"] > 0
        assert 0 <= result["kpi"]["actual_pct"] <= 100
        assert 0 <= result["kpi"]["planned_pct"] <= 100
        assert result["kpi"]["earned_value"] == pytest.approx(result["activities"]["earned_value"].sum())
        assert result["kpi"]["cpi"] == pytest.approx(result["kpi"]["earned_value"] / result["kpi"]["actual_cost"])


def test_explicit_overdue_orders_and_flags(data):
    v = compute(select_project(data, "UGV-001"))
    assert v["kpi"]["overdue_po"] == 2
    assert v["kpi"]["critical_overdue_po"] == 1
    assert v["kpi"]["late_activities"] == 1
    assert v["kpi"]["overdue_actions"] == 2
    assert any(a["area"] == "Procurement" for a in make_alerts(v))


def test_progress_fraction_at_boundaries():
    s = pd.to_datetime(pd.Series(["2026-10-01"] * 3))
    f = pd.to_datetime(pd.Series(["2026-10-10"] * 3))
    assert list(planned_percentage(s, f, pd.Timestamp("2026-09-30"))) == [0.0] * 3
    assert list(planned_percentage(s, f, pd.Timestamp("2026-10-10"))) == [100.0] * 3


def test_reports_not_claimed_ai(data):
    d = compute(select_project(data, "DWP-002"))
    report = weekly_report(d)
    assert "Dewatering Pump" in report
    assert "FICTIONAL DEMONSTRATION" in report
    assert "not AI predictions" in report


def test_bad_activity_input_rejected(data):
    frame = data["activities"].copy()
    frame.loc[0, "actual_pct"] = 150
    with pytest.raises(ValueError):
        validated_frame("activities", frame)


def test_missing_cost_fails(data):
    d = select_project(data, "UGV-001")
    d["costs"] = d["costs"].iloc[:-1]
    with pytest.raises(ValueError, match="matching cost"):
        compute(d)
