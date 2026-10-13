# Write-up — GPU FinOps tại NimbusAI

Sinh viên: Nguyễn Trường Bảo · 2A202602540 · Lab 25 · Phân tích dữ liệu tổng hợp seed=25.

## Baseline và optimized

Kịch bản 30 ngày: baseline **$27,133.10**, optimized **$14,626.10**, savings **$12,507.00 (46.1%)**. Inference riêng: **$6.488 → $1.126/1M-token**, giảm **82.6%**, cùng 7,533,027 token/ngày. Đo $/GPU-hr có thể gây hiểu sai: GPU đắt hơn nhưng throughput tốt hơn vẫn có $/token thấp hơn.

## Đòn bẩy và GPU-Util lie

- Inference (cascade/cache/batch): **$1,212/tháng**.
- Purchasing (spot/reserved): **$10,040/tháng**.
- Right-size util-lies: **$655/tháng**.
- Kill idle GPUs: **$600/tháng**.

**Purchasing (spot/reserved)** đóng góp tuyệt đối lớn nhất vì baseline GPU-hours lớn. Cascade giảm chi phí model, cache giảm tiền phần input lặp, batch giảm bill task không cần phản hồi ngay; mức giảm kết hợp phải nhân và áp trên đúng phần bill.

Các GPU bị flag: **gpu-h100-4, gpu-a10g-1**. GPU-Util cao chỉ nói kernel đang hoạt động trong cửa sổ lấy mẫu; memory stall, synchronization và kernel nhỏ có thể khiến FLOPs thực thấp. Cần profiler để phân biệt nguyên nhân. MFU thấp không đủ kết luận decode lãng phí, bởi decode thường memory-bound; MBU và p95 latency mới giúp quyết định. Idle waste đo được **$20.00/ngày**. Không xem 1−MFU là tỷ lệ tiền chắc chắn thu hồi.

## Hai extension có kết quả định lượng

**D.4 — Ngân sách reasoning:** reasoning chiếm **8.38% traffic**, **16.46% bill inference**. Cap 10% chuyển 0 request sang small, chi phí **$8.4846 → $8.4846/ngày**, năng lượng **31675.31 → 31675.31 Wh/ngày**; tiết kiệm **$0.00 và 0.00 kWh/30 ngày**. Hệ số năng lượng ×80 là giả định lab với cùng số token, không phải benchmark hay hệ số giá. Rule đề xuất: complexity ≥0,7, task nhiều bước và quota ≤10%; phải calibration/quality evaluation vì CSV không có nhãn độ khó. Kịch bản hiện tại ưu tiên reroute theo savings nên chưa đảm bảo chất lượng.

Insight: 8,375% traffic đã dưới cap 10%, vì vậy tiết kiệm bằng 0 là kết quả đúng. Sensitivity cap 5% chuyển **81 request**, chi phí **$8.4846 → $7.2872/ngày**, năng lượng **31675.31 → 17242.57 Wh/ngày**; tiềm năng **$35.92 và 432.98 kWh/30 ngày**, chỉ triển khai nếu quality đạt.

**D.5 — Carbon scheduling:** job interruptible tiêu thụ **1789.00 kWh/lịch job**, dùng đúng cột days và rated watts. Chuyển từ us-east-1 sang **europe-north1** giảm **626,150 gCO2e**. Điện rẻ nhất **us-east-wa**, sạch nhất **europe-north1**, cân bằng **us-east-wa** với trọng số bằng nhau trên giá và carbon chuẩn hóa. Bảng đủ 5 vùng và từng job ở report.md cho thấy mục tiêu tài chính và môi trường không luôn chọn cùng vùng. Latency, residency, egress và GPU availability có thể làm phương án sạch nhất không khả thi.

## Ba hành động đầu tiên

1. Tắt idle bằng scheduler/TTL, giữ warm capacity theo SLO; tiết kiệm nhanh, dễ rollback.
2. Sau khi biết footprint ổn định, dùng spot + checkpoint cho training/batch và reserved cho tải đều; kiểm tra chi phí giờ cam kết, recovery và rework.
3. Canary cascade/cache/batch với quality, p95 và $/1M-token; sau đó thử reasoning quota, carbon scheduling và right-size dựa trên VRAM/bandwidth benchmark.

## Giới hạn và bằng chứng

M5 giữ mô hình rubric: API cost + GPU run-rate 30 ngày, trừ 4 lever. M3 gốc bỏ qua days; M1 chưa map resource vào M3 nên savings right-size/idle có thể trùng purchasing. Đây là kịch bản minh họa, chưa phải savings xác nhận trên hóa đơn. Right-size map chưa chứng minh VRAM/SLO. Giá điện thường đã nằm trong GPU rental; không cộng savings điện/reasoning extension thêm vào M5. Hệ số vùng là dữ liệu lab, không phải báo giá thị trường.

Code hai extension ở `finops/extensions.py`, chạy qua M2/M3; tests tự viết ở `extension_tests/`, giữ nguyên tests gốc. M5 tái tạo report, chart và write-up từ cùng kết quả. Chạy `python verify.py`, `python -m pytest -q` để kiểm tra; xem `outputs/validation.txt` cho log xác nhận.
