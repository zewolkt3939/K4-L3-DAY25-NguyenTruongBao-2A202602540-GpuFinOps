"""Report assembly — the lab's deliverable: baseline vs optimized + savings chart."""
from __future__ import annotations


def build_report(baseline_usd: float, optimized_usd: float, levers: dict,
                 sustainability: dict | None = None, period: str = "monthly") -> str:
    """Return a markdown cost-optimization report."""
    savings = baseline_usd - optimized_usd
    pct = (savings / baseline_usd * 100.0) if baseline_usd > 0 else 0.0
    lines = [
        "# NimbusAI — GPU Cost Optimization Report",
        "",
        f"**Period:** {period}",
        "",
        f"**Baseline spend:** ${baseline_usd:,.2f}",
        "",
        f"**Optimized spend:** ${optimized_usd:,.2f}",
        "",
        f"**Projected savings:** ${savings:,.2f}  (**{pct:.0f}%**, exact: {pct:.1f}%)",
        "",
        "## Savings by lever",
        "",
        "| Lever | Savings (USD) |",
        "|---|---|",
    ]
    for name, amount in levers.items():
        lines.append(f"| {name} | ${amount:,.0f} |")
    if sustainability:
        lines += [
            "",
            "## Sustainability",
            "",
            f"- Energy per query: {sustainability.get('wh_per_query', 0):.2f} Wh",
            f"- Carbon per query: {sustainability.get('carbon_g', 0):.3f} gCO2e",
            f"- Cleanest region: {sustainability.get('best_region', 'n/a')}",
            "- Cheapest electricity region: us-east-wa (illustrative lab catalog).",
        ]
    lines += ["", "_Figures are June-2026 as-of snapshots; re-baseline before acting._"]
    return "\n".join(lines)


def savings_waterfall(levers: dict, path: str, baseline_usd: float | None = None) -> str:
    """Write cumulative waterfall with four reductions and start/end totals."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return ""
    baseline = sum(levers.values()) if baseline_usd is None else baseline_usd
    names = ["Baseline", *levers.keys(), "Optimized"]
    remaining = baseline
    bottoms, heights = [0], [baseline]
    for value in levers.values():
        remaining -= value
        bottoms.append(remaining)
        heights.append(value)
    bottoms.append(0)
    heights.append(remaining)
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(names, heights, bottom=bottoms, color=["#2e548a"] + ["#279c72"] * len(levers) + ["#2e548a"])
    for i, (bottom, height) in enumerate(zip(bottoms, heights)):
        label = f"${height:,.0f}" if i in (0, len(names)-1) else f"-${height:,.0f}"
        ax.annotate(label, (i, bottom + height), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=9)
        if i < len(names)-1:
            level = baseline if i == 0 else bottom
            ax.plot([i + .4, i + .6], [level, level], color="gray", linestyle="--")
    ax.set_ylim(0, baseline * 1.16)
    ax.set_ylabel("Monthly spend (USD)")
    ax.set_title("NimbusAI: baseline to optimized — four FinOps levers")
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path
