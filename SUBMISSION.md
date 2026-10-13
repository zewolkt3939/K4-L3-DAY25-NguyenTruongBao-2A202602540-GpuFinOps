# Hướng dẫn chấm và nộp — Lab 25

## File nộp

- [Báo cáo kỹ thuật](outputs/report.md): baseline/optimized, 4 lever, unit economics, GPU-Util lie, sustainability, hai extension và ưu tiên hành động.
- [Waterfall](outputs/savings.png): baseline → 4 lever → optimized.
- [FOCUS-style export](outputs/focus_export.csv): đủ 2.400 request, không chỉ 50 dòng mẫu. BilledCost làm tròn 4 chữ số thập phân theo engine gốc.
- [Write-up](outputs/writeup.md): bài phân tích ngắn, tạo tự động bởi M5.
- [Bằng chứng kiểm tra](outputs/validation.txt) và [log missions](outputs/missions.log).

Nộp repo kèm code extension và tests riêng để giảng viên chạy lại phần D.

## Đối chiếu rubric

| Phần | Bằng chứng |
|---|---|
| A — 30 điểm | `python verify.py`: 11/11 pass |
| B — 20 điểm | `python -m pytest -q tests`: 15/15 pass; tests gốc và verify.py không sửa |
| C — 30 điểm | report.md + savings.png + writeup.md; số liệu tạo từ missions |
| D — 20 điểm | D.4 reasoning budget + D.5 carbon scheduling; `finops/extensions.py`, tích hợp M2/M3; 8 tests mới |

Phần C/D cần giảng viên đánh giá chất lượng; bảng này đối chiếu bằng chứng, không tự xác nhận điểm số.

## Tái tạo

```powershell
python -m pip install -r requirements.txt
python data/generate.py
python missions/run_all.py
python verify.py
python -m pytest -q
```

Lệnh pytest cuối chạy 23 tests (15 gốc + 8 extension). M5 tạo lại report, chart và write-up. Dữ liệu seed=25; không cần GPU/cloud/API key. Không sửa report/write-up bằng tay vì sẽ bị ghi đè khi chạy lại.

## Câu hỏi kiểm tra hiểu biết

1. **GPU-Util 98% có hiệu quả không?** Chưa biết. Đây là thời gian kernel hoạt động; xem MFU/MBU, throughput và SLO. Memory stalls/overhead có thể tạo util cao và FLOPs thấp.
2. **Tại sao coverage ≥80% trước chargeback?** Đây là gate quản trị của lab để giảm phân bổ sai. Vẫn cần xử lý phần untagged và kiểm tra coverage theo tiền, không chỉ số request.
3. **70% workload interruptible?** Thử spot với checkpoint/restore; đo interruption, rework, thời hạn job và chi phí effective. Chỉ commit reserved phần tải đều còn lại sau tối ưu footprint.
4. **$/GPU-hr và $/1M-token trái ngược khi nào?** GPU giá giờ cao nhưng tokens/hour tăng nhanh hơn giá sẽ có giá/token thấp hơn; so cùng chất lượng, latency và sản lượng.
5. **Decode memory-bound, prefill compute-bound vì sao?** Decode đọc weights/KV cache cho từng token với ít phép tính trên mỗi byte; prefill xử lý nhiều token song song, tái sử dụng weights tăng arithmetic intensity. Đây là xu hướng, cần benchmark theo batch/model cụ thể.

Insight extension: traffic reasoning thực tế 8,375%, nên cap 10% tiết kiệm đúng bằng 0; cap 5% là sensitivity riêng. Vùng điện rẻ nhất us-east-wa khác vùng sạch nhất europe-north1. M5 là mô hình savings của lab, còn rủi ro overlap và giả định right-size được phân tích trong report.
