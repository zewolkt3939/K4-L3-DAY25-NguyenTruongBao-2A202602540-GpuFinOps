"""Generate analysis and submission write-up from the same mission results."""
from missions._common import load_csv, num, catalog_by_type
from missions.m2_inference_levers import MODEL_PRICES
from finops import pricing


def build_analysis(r1, r2, r3, r4, baseline, optimized, levers):
    budget, carbon = r2["reasoning_budget"], r3["carbon_schedule"]
    tighter = r2["reasoning_5pct"]
    lines = ["", "## Phạm vi và phương pháp", "",
             "Dữ liệu tổng hợp seed=25; catalog tháng 06/2026 của bài lab. M2 coi 2.400 request là một ngày và nhân 30 để dự phóng tháng. M3 gốc dùng hours_per_day × 30 × num_gpus cho mọi job, bỏ qua cột days; đây là run-rate 30 ngày, không phải tổng tiền theo lịch job thực tế.",
             "M5 giữ phương pháp rubric: baseline = M2 baseline × 30 + M3 on-demand; optimized = baseline − tổng 4 lever. M1 telemetry không có job_id để đối chiếu workload M3, nên cộng right-size/idle có nguy cơ trùng với purchasing; kết quả là kịch bản lab, chưa phải savings được xác nhận trên hóa đơn. Cần map resource→job, tính purchasing trên footprint sau right-size/idle và không cộng API bill với GPU bill nếu cùng phục vụ một traffic.",
             "Right-size H100→A100 và A10G→L4 là giả định của M5; MFU thấp chưa đủ để khẳng định GPU nhỏ hơn đáp ứng VRAM, bandwidth và p95 latency. Carbon/reasoning scenarios bên dưới không được cộng thêm vào 4 lever để tránh trộn phạm vi hoặc cộng hai lần.",
             "Sustainability snapshot đầu báo cáo dùng request tham chiếu 800 token không reasoning: 0,24 Wh và 0,0912 gCO2e ở us-east-1; đây không phải trung bình/median đo từ CSV. Extension D.4 bên dưới mới tính toàn bộ token thực tế của dataset.",
             "", "## Unit economics và phân tích inference", "",
             f"{r2['total_tokens']:,} token/ngày; baseline **${r2['baseline_daily']:.2f}/ngày, ${r2['baseline_per_m']:.3f}/1M-token** → optimized **${r2['optimized_daily']:.2f}/ngày, ${r2['optimized_per_m']:.3f}/1M-token**; giảm **{r2['savings_pct']:.1f}%**. Mẫu số token giữ nguyên để so sánh cùng sản lượng; chất lượng model chưa được đo.",
             "", "| Bước tuần tự | USD/ngày | Savings tăng thêm USD/ngày |", "|---|---:|---:|"]
    totals = [0.0] * 4
    for r in load_csv("token_usage.csv"):
        inp, out = int(r["input_tokens"]), int(r["output_tokens"])
        prices = MODEL_PRICES[r["route_tier"]]
        totals[0] += pricing.request_cost(inp, out, *MODEL_PRICES["large"])
        totals[1] += pricing.request_cost(inp, out, *prices)
        totals[2] += pricing.request_cost(inp, out, *prices, cached_in=int(r["cached_input_tokens"]))
        totals[3] += pricing.request_cost(inp, out, *prices, cached_in=int(r["cached_input_tokens"]), batch=bool(int(r["is_batch"])))
    for i, name in enumerate(["Large, không cache/batch", "Cascade", "+ Cache", "+ Batch"]):
        lines.append(f"| {name} | {totals[i]:.4f} | {(totals[i-1]-totals[i]) if i else 0:.4f} |")
    largest = max(levers, key=levers.get)
    lines += ["", f"Trong tổng M5, **{largest}** đóng góp lớn nhất: **${levers[largest]:,.0f}/tháng**. Purchasing tác động trực tiếp phần GPU-hours có quy mô lớn; inference tiết kiệm tỷ lệ cao nhưng baseline API nhỏ hơn. Breakdown cascade→cache→batch là attribution tuần tự, phụ thuộc thứ tự; chiết khấu nhân chứ không cộng.",
              "", "## GPU-Util lie: cơ chế và tác động tài chính", "",
              "GPU-Util đo tỷ lệ thời gian trong cửa sổ lấy mẫu có kernel thực thi, không đo tỷ lệ peak FLOPs tạo ra. Memory stalls, kernel nhỏ, đồng bộ và overhead có thể giữ GPU bận nhưng ít phép tính hữu ích. Đây là các giả thuyết cần profiler, không phải nguyên nhân đã được telemetry chứng minh. Decode thường memory-bound vì đọc weights/KV cache để tạo từng token; prefill xử lý nhiều token cùng lúc nên tái sử dụng weights tốt hơn. MFU thấp trong decode không tự động là lãng phí; phải xem MBU, throughput và SLO.",
              "", "| GPU | Util % | MFU | MBU | Giá thuê USD/tháng (24×30) |", "|---|---:|---:|---:|---:|"]
    cat = catalog_by_type()
    for g in r1["lies"]:
        lines.append(f"| {g['gpu_id']} | {g['gpu_util_pct']:.1f} | {g['mfu']:.3f} | {g['mbu']:.3f} | {num(cat[g['gpu_type']]['on_demand_hr'])*720:.2f} |")
    lines += ["", f"Idle (<10% util) làm mất **${r1['idle_waste_daily']:.2f}/ngày = ${r1['idle_waste_daily']*30:.0f}/tháng**. Không thể lấy (1−MFU)×bill làm savings chắc chắn: workload vẫn có chi phí bộ nhớ/I/O và nhu cầu phục vụ.",
              "", "## Extension D.4 — Ngân sách reasoning", "",
              "Code: `finops/extensions.py::reasoning_budget`, tích hợp trong M2. Chi phí dùng route_tier và cache/batch thực tế; năng lượng dùng số token từng request, hệ số lab 0,30 Wh/1K token và reasoning ×80.",
              "", "| Nhóm | Requests/ngày | USD/ngày | Wh/ngày |", "|---|---:|---:|---:|"]
    for name, g in budget["groups"].items():
        lines.append(f"| {name} | {g['requests']} | {g['usd']:.4f} | {g['wh']:.2f} |")
    lines += ["", f"Reasoning chiếm **{budget['traffic_pct']:.2f}% traffic**, **{budget['cost_pct']:.2f}% chi phí**. ×80 là hệ số mô phỏng năng lượng với cùng số token, không phải hệ số giá API; tỷ lệ Wh trung bình thực tế còn phụ thuộc độ dài token.",
              "", "| Kịch bản | USD/ngày | Wh/ngày |", "|---|---:|---:|",
              f"| Routing hiện tại | {budget['before_usd']:.4f} | {budget['before_wh']:.2f} |",
              f"| Reasoning ≤10% traffic | {budget['after_usd']:.4f} | {budget['after_wh']:.2f} |",
              f"| Tiết kiệm | {budget['saved_usd']:.4f} | {budget['saved_wh']:.2f} |", "",
              "**Insight: dataset hiện chỉ có 8,375% reasoning, đã dưới 10%; cap 10% không reroute và tiết kiệm bằng 0.** Không thay dữ liệu hoặc giả định traffic cao hơn để tạo savings.",
              f"Sensitivity cap **5%**: chuyển **{tighter['rerouted']} request**, USD/ngày **{tighter['before_usd']:.4f} → {tighter['after_usd']:.4f}**, Wh/ngày **{tighter['before_wh']:.2f} → {tighter['after_wh']:.2f}**; giảm **${tighter['saved_usd']:.4f}/ngày và {tighter['saved_wh']:.2f} Wh/ngày**, tương đương **${tighter['saved_usd']*30:.2f} và {tighter['saved_wh']*30/1000:.2f} kWh/30 ngày**. Không phải mặc định triển khai; cần xác nhận quality trước khi giảm quota.",
              f"Chuyển **{budget['rerouted']} request/ngày** từ reasoning sang small, ưu tiên request có chênh lệch giá lớn nhất; giữ token/cache/batch. Tương đương **${budget['saved_usd']*30:.2f} và {budget['saved_wh']*30/1000:.2f} kWh/30 ngày**. Đây là upper-bound scenario về routing, chưa có bằng chứng task đó đủ đơn giản.",
              "Rule triển khai đề xuất: classifier cho complexity score 0–1; chỉ cho reasoning khi score ≥0,7 và task cần suy luận nhiều bước, kèm quota ≤10% request/ngày. Score threshold là đề xuất cần calibration trên tập đánh giá; CSV không có complexity/quality label. Với pentest assistant, triage/phân loại log có thể dùng small; suy luận chuỗi tấn công cần đánh giá chất lượng kỹ trước khi đổi route. Không reroute khi vi phạm quality/SLO chỉ để đạt quota.",
              "", "## Extension D.5 — Carbon-aware scheduling", "",
              "Code: `finops/extensions.py::carbon_schedule`, tích hợp trong M3. Chỉ job interruptible=1; Wh = hours_per_day × days × num_gpus × watts. Khác M3 run-rate, extension dùng đúng days trong CSV. Watts là rated power catalog, chưa phải điện đo tại ổ cắm; bỏ qua PUE/CPU/network và overhead checkpoint.",
              "", "| Job | kWh/lịch job | us-east-1 gCO2e | Vùng sạch nhất gCO2e | Giảm gCO2e |", "|---|---:|---:|---:|---:|"]
    for j in carbon["jobs"]:
        lines.append(f"| {j['job_id']} | {j['wh']/1000:.2f} | {j['baseline_g']:.0f} | {j['cleanest_g']:.0f} | {j['baseline_g']-j['cleanest_g']:.0f} |")
    lines += ["", "| Vùng | USD/kWh | gCO2e/kWh | Chi phí điện USD/lịch job | Carbon gCO2e/lịch job |", "|---|---:|---:|---:|---:|"]
    for r in carbon["regions"]:
        lines.append(f"| {r['region']} | {r['usd_kwh']:.3f} | {r['g_kwh']} | {r['usd']:.2f} | {r['g']:.0f} |")
    lines += ["", f"Tổng **{carbon['wh']/1000:.2f} kWh**; chuyển sang **{carbon['cleanest']}** giảm **{carbon['saved_g']:,.0f} gCO2e** so với us-east-1. Điện rẻ nhất: **{carbon['cheapest']}**; carbon thấp nhất: **{carbon['cleanest']}**; cân bằng: **{carbon['balanced']}** theo score = price/max(price) + carbon/max(carbon), hai trọng số bằng nhau. Thay trọng số có thể đổi lựa chọn.",
              "Đây là nhãn vùng và hệ số minh họa của lab, không xác nhận vị trí địa lý/giá cloud hiện hành. Giá điện không phải giá thuê GPU: cloud rental thường đã bao gồm điện, vì vậy không cộng savings điện vào M5. Dịch job batch sang vùng sạch giúp carbon nhưng cần kiểm tra data residency, availability GPU, egress và thời gian chuyển dataset. Với inference tương tác, vùng xa người dùng có thể làm tăng latency; ưu tiên SLO trước carbon.",
              "", "## Hành động ưu tiên và quản trị", "",
              f"1. **P0 — Tắt idle theo lịch/TTL**: tiềm năng ${r1['idle_waste_daily']*30:.0f}/tháng, dễ thực hiện và đảo ngược; đo lại throughput/SLO, giữ warm capacity cần thiết.",
              f"2. **P1 — Purchasing + checkpoint**: khoản lớn nhất ${levers['Purchasing (spot/reserved)']:,.0f}/tháng trong mô hình. Dùng spot cho job có thể resume; fault-injection kiểm tra restore và rework. Reserved chỉ sau khi footprint ổn định, so sánh giá 1yr/3yr và trả đủ giờ cam kết kể cả giờ idle; công thức M3 gốc tính trên giờ sử dụng có thể lạc quan cho job 18h/ngày.",
              "3. **P1 — Cascade/cache/batch**: rollout canary với quality, p95 latency và $/1M-token, batch chỉ task không real-time. Sau đó thử quota reasoning và carbon scheduling cho batch. Right-size thực hiện sau profiling VRAM/MBU và benchmark ở cùng tải, không hạ GPU chỉ vì MFU thấp.",
              f"Tag coverage **{r4['tag_coverage']:.1%}**; chargeback gate **{r4['chargeback_ready']}** theo ngưỡng 80%. Phần thiếu tag vào nhóm unallocated để xử lý, không áp hết cho một team. Export FOCUS-style là schema tối giản phục vụ lab, không khẳng định tuân thủ đầy đủ FOCUS.",
              "", "## Tái tạo và kiểm tra", "",
              "Chạy `python data/generate.py`, `python missions/run_all.py`, `python verify.py`, `python -m pytest -q`, `python -m pytest -q extension_tests`. Tests gốc trong `tests/` giữ nguyên. Extension tests ở thư mục riêng kiểm tra cap, token conservation, energy/carbon và các edge cases. Báo cáo/write-up được M5 tạo lại; không chép tay số liệu."]
    return "\n".join(lines)


def build_writeup(r1, r2, r3, baseline, optimized, levers):
    b, c = r2["reasoning_budget"], r3["carbon_schedule"]
    tighter = r2["reasoning_5pct"]
    largest = max(levers, key=levers.get)
    return f"""# Write-up — GPU FinOps tại NimbusAI

Sinh viên: Nguyễn Trường Bảo · 2A202602540 · Lab 25 · Phân tích dữ liệu tổng hợp seed=25.

## Baseline và optimized

Kịch bản 30 ngày: baseline **${baseline:,.2f}**, optimized **${optimized:,.2f}**, savings **${baseline-optimized:,.2f} ({(baseline-optimized)/baseline*100:.1f}%)**. Inference riêng: **${r2['baseline_per_m']:.3f} → ${r2['optimized_per_m']:.3f}/1M-token**, giảm **{r2['savings_pct']:.1f}%**, cùng {r2['total_tokens']:,} token/ngày. Đo $/GPU-hr có thể gây hiểu sai: GPU đắt hơn nhưng throughput tốt hơn vẫn có $/token thấp hơn.

## Đòn bẩy và GPU-Util lie

{chr(10).join(f'- {name}: **${amount:,.0f}/tháng**.' for name, amount in levers.items())}

**{largest}** đóng góp tuyệt đối lớn nhất vì baseline GPU-hours lớn. Cascade giảm chi phí model, cache giảm tiền phần input lặp, batch giảm bill task không cần phản hồi ngay; mức giảm kết hợp phải nhân và áp trên đúng phần bill.

Các GPU bị flag: **{', '.join(g['gpu_id'] for g in r1['lies'])}**. GPU-Util cao chỉ nói kernel đang hoạt động trong cửa sổ lấy mẫu; memory stall, synchronization và kernel nhỏ có thể khiến FLOPs thực thấp. Cần profiler để phân biệt nguyên nhân. MFU thấp không đủ kết luận decode lãng phí, bởi decode thường memory-bound; MBU và p95 latency mới giúp quyết định. Idle waste đo được **${r1['idle_waste_daily']:.2f}/ngày**. Không xem 1−MFU là tỷ lệ tiền chắc chắn thu hồi.

## Hai extension có kết quả định lượng

**D.4 — Ngân sách reasoning:** reasoning chiếm **{b['traffic_pct']:.2f}% traffic**, **{b['cost_pct']:.2f}% bill inference**. Cap 10% chuyển {b['rerouted']} request sang small, chi phí **${b['before_usd']:.4f} → ${b['after_usd']:.4f}/ngày**, năng lượng **{b['before_wh']:.2f} → {b['after_wh']:.2f} Wh/ngày**; tiết kiệm **${b['saved_usd']*30:.2f} và {b['saved_wh']*30/1000:.2f} kWh/30 ngày**. Hệ số năng lượng ×80 là giả định lab với cùng số token, không phải benchmark hay hệ số giá. Rule đề xuất: complexity ≥0,7, task nhiều bước và quota ≤10%; phải calibration/quality evaluation vì CSV không có nhãn độ khó. Kịch bản hiện tại ưu tiên reroute theo savings nên chưa đảm bảo chất lượng.

Insight: 8,375% traffic đã dưới cap 10%, vì vậy tiết kiệm bằng 0 là kết quả đúng. Sensitivity cap 5% chuyển **{tighter['rerouted']} request**, chi phí **${tighter['before_usd']:.4f} → ${tighter['after_usd']:.4f}/ngày**, năng lượng **{tighter['before_wh']:.2f} → {tighter['after_wh']:.2f} Wh/ngày**; tiềm năng **${tighter['saved_usd']*30:.2f} và {tighter['saved_wh']*30/1000:.2f} kWh/30 ngày**, chỉ triển khai nếu quality đạt.

**D.5 — Carbon scheduling:** job interruptible tiêu thụ **{c['wh']/1000:.2f} kWh/lịch job**, dùng đúng cột days và rated watts. Chuyển từ us-east-1 sang **{c['cleanest']}** giảm **{c['saved_g']:,.0f} gCO2e**. Điện rẻ nhất **{c['cheapest']}**, sạch nhất **{c['cleanest']}**, cân bằng **{c['balanced']}** với trọng số bằng nhau trên giá và carbon chuẩn hóa. Bảng đủ 5 vùng và từng job ở report.md cho thấy mục tiêu tài chính và môi trường không luôn chọn cùng vùng. Latency, residency, egress và GPU availability có thể làm phương án sạch nhất không khả thi.

## Ba hành động đầu tiên

1. Tắt idle bằng scheduler/TTL, giữ warm capacity theo SLO; tiết kiệm nhanh, dễ rollback.
2. Sau khi biết footprint ổn định, dùng spot + checkpoint cho training/batch và reserved cho tải đều; kiểm tra chi phí giờ cam kết, recovery và rework.
3. Canary cascade/cache/batch với quality, p95 và $/1M-token; sau đó thử reasoning quota, carbon scheduling và right-size dựa trên VRAM/bandwidth benchmark.

## Giới hạn và bằng chứng

M5 giữ mô hình rubric: API cost + GPU run-rate 30 ngày, trừ 4 lever. M3 gốc bỏ qua days; M1 chưa map resource vào M3 nên savings right-size/idle có thể trùng purchasing. Đây là kịch bản minh họa, chưa phải savings xác nhận trên hóa đơn. Right-size map chưa chứng minh VRAM/SLO. Giá điện thường đã nằm trong GPU rental; không cộng savings điện/reasoning extension thêm vào M5. Hệ số vùng là dữ liệu lab, không phải báo giá thị trường.

Code hai extension ở `finops/extensions.py`, chạy qua M2/M3; tests tự viết ở `extension_tests/`, giữ nguyên tests gốc. M5 tái tạo report, chart và write-up từ cùng kết quả. Chạy `python verify.py`, `python -m pytest -q` để kiểm tra; xem `outputs/validation.txt` cho log xác nhận.
"""
