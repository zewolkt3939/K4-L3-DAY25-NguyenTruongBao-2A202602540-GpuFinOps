"""Measured lab scenarios; synthetic coefficients, not production forecasts."""
from math import floor
from finops import pricing, sustainability as s


def reasoning_budget(rows, model_prices, cap=0.10):
    """Cap reasoning requests by rerouting largest-cost candidates first.

    Preserve input/output lengths and cache/batch eligibility. The CSV has no
    task complexity or quality labels: this is a potential, not validated routing.
    """
    if not 0 <= cap <= 1:
        raise ValueError("cap must be in [0, 1]")
    groups = {"reasoning": {"requests": 0, "usd": 0.0, "wh": 0.0},
              "standard": {"requests": 0, "usd": 0.0, "wh": 0.0}}
    candidates = []
    for r in rows:
        inp, out = int(r["input_tokens"]), int(r["output_tokens"])
        reasoning = bool(int(r["is_reasoning"]))
        kwargs = {"cached_in": int(r["cached_input_tokens"]), "batch": bool(int(r["is_batch"]))}
        cost = pricing.request_cost(inp, out, *model_prices[r["route_tier"]], **kwargs)
        wh = s.wh_per_query(inp + out, is_reasoning=reasoning)
        g = groups["reasoning" if reasoning else "standard"]
        g["requests"] += 1
        g["usd"] += cost
        g["wh"] += wh
        if reasoning:
            small_cost = pricing.request_cost(inp, out, *model_prices["small"], **kwargs)
            candidates.append((cost - small_cost, wh - s.wh_per_query(inp + out)))
    n = sum(g["requests"] for g in groups.values())
    reroute = max(0, len(candidates) - floor(cap * n))
    selected = sorted(candidates, reverse=True)[:reroute]
    total_usd = sum(g["usd"] for g in groups.values())
    total_wh = sum(g["wh"] for g in groups.values())
    saved_usd = sum(x[0] for x in selected)
    saved_wh = sum(x[1] for x in selected)
    return {"groups": groups, "traffic_pct": len(candidates) / n * 100 if n else 0,
            "cost_pct": groups["reasoning"]["usd"] / total_usd * 100 if total_usd else 0,
            "rerouted": reroute, "cap": cap, "saved_usd": saved_usd, "saved_wh": saved_wh,
            "before_usd": total_usd, "after_usd": total_usd - saved_usd,
            "before_wh": total_wh, "after_wh": total_wh - saved_wh}


def carbon_schedule(jobs, catalog):
    """Move interruptible jobs; use actual job days and catalog rated GPU watts.

    Excludes CPU/network/PUE and assumes equal runtime across regions. Electricity
    is a component estimate, not an extra discount on a cloud rental invoice.
    """
    cleanest = min(s.REGION_CARBON, key=s.REGION_CARBON.get)
    cheapest = min(s.REGION_PRICE_KWH, key=s.REGION_PRICE_KWH.get)
    workloads = []
    for j in jobs:
        if not int(j["interruptible"]):
            continue
        wh = (float(j["hours_per_day"]) * float(j["days"]) * int(j["num_gpus"])
              * float(catalog[j["gpu_type"]]["watts"]))
        workloads.append({"job_id": j["job_id"], "wh": wh,
                          "baseline_g": s.carbon_g(wh), "cleanest_g": s.carbon_g(wh, cleanest)})
    wh = sum(j["wh"] for j in workloads)
    regions = [{"region": r, "usd_kwh": s.REGION_PRICE_KWH[r], "g_kwh": s.REGION_CARBON[r],
                "usd": s.energy_cost_usd(wh, r), "g": s.carbon_g(wh, r)} for r in s.REGION_CARBON]
    # Equal weight of normalized electricity cost and carbon; explicit objective.
    max_price, max_carbon = max(s.REGION_PRICE_KWH.values()), max(s.REGION_CARBON.values())
    balanced = min(regions, key=lambda r: r["usd_kwh"] / max_price + r["g_kwh"] / max_carbon)["region"]
    return {"jobs": workloads, "regions": regions, "wh": wh, "cleanest": cleanest,
            "cheapest": cheapest, "balanced": balanced,
            "saved_g": s.carbon_g(wh) - s.carbon_g(wh, cleanest)}
