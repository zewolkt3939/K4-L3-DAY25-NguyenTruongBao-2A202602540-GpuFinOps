"""Independent scenario tests; original grading tests remain untouched."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from finops.extensions import reasoning_budget, carbon_schedule
from finops.sustainability import wh_per_query
from missions.m2_inference_levers import MODEL_PRICES, run as inference
from missions.m3_purchasing import run as purchasing
from missions._common import load_csv


def request(reasoning, tier="large"):
    return {"input_tokens": "1000", "output_tokens": "1000", "cached_input_tokens": "0",
            "is_batch": "0", "is_reasoning": str(int(reasoning)), "route_tier": tier}


def test_reasoning_cap_preserves_tokens_and_prices():
    result = reasoning_budget([request(True), request(False, "small")], MODEL_PRICES, cap=0)
    assert result["rerouted"] == 1
    assert result["before_usd"] == pytest.approx(.0186)
    assert result["after_usd"] == pytest.approx(.0012)
    assert result["before_wh"] == pytest.approx(48.6)
    assert result["after_wh"] == pytest.approx(1.2)


def test_reasoning_already_under_cap_no_changes():
    rows = [request(False)] * 9 + [request(True)]
    result = reasoning_budget(rows, MODEL_PRICES)
    assert result["rerouted"] == 0
    assert result["saved_usd"] == result["saved_wh"] == 0


def test_reasoning_rounds_quota_down():
    result = reasoning_budget([request(True)] * 11, MODEL_PRICES)
    assert result["rerouted"] == 10


def test_reasoning_empty_and_invalid_cap():
    assert reasoning_budget([], MODEL_PRICES)["traffic_pct"] == 0
    with pytest.raises(ValueError):
        reasoning_budget([], MODEL_PRICES, cap=1.1)


def test_carbon_uses_days_and_filters_noninterruptible():
    job = {"job_id": "x", "interruptible": "1", "hours_per_day": "2", "days": "3", "num_gpus": "2", "gpu_type": "test"}
    result = carbon_schedule([job, dict(job, interruptible="0")], {"test": {"watts": "100"}})
    assert result["wh"] == 1200
    assert len(result["jobs"]) == 1
    assert result["saved_g"] == pytest.approx(420)
    assert result["cleanest"] == "europe-north1"
    assert result["cheapest"] == "us-east-wa"
    assert result["balanced"] == "us-east-wa"
    assert len(result["regions"]) == 5


def test_carbon_empty_jobs():
    result = carbon_schedule([], {})
    assert result["wh"] == result["saved_g"] == 0
    assert all(r["g"] == r["usd"] == 0 for r in result["regions"])


def test_reasoning_multiplier_is_energy_only():
    assert wh_per_query(2000, is_reasoning=True) / wh_per_query(2000) == 80


def test_dataset_extensions_reconcile_missions():
    result = inference(False)
    budget = result["reasoning_budget"]
    assert round(budget["before_usd"], 2) == result["optimized_daily"]
    rows = load_csv("token_usage.csv")
    reasoning_n = sum(int(r["is_reasoning"]) for r in rows)
    assert reasoning_n - budget["rerouted"] <= .1 * len(rows)
    assert budget["rerouted"] == 0
    assert budget["saved_usd"] == budget["saved_wh"] == 0
    tighter = result["reasoning_5pct"]
    assert tighter["rerouted"] == reasoning_n - int(.05 * len(rows))
    assert tighter["saved_usd"] > 0 and tighter["saved_wh"] > 0
    schedule = purchasing(False)["carbon_schedule"]
    assert schedule["wh"] == sum(j["wh"] for j in schedule["jobs"])
    assert schedule["saved_g"] == pytest.approx(sum(j["baseline_g"]-j["cleanest_g"] for j in schedule["jobs"]))
