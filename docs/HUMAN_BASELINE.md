# Thu baseline người thật

Baseline là telemetry khi **bạn tự làm cùng nhiệm vụ** với agent. Không cần quay video để
so sánh thời gian input. Recorder chỉ nghe metadata; không phát chuột/bàn phím, không lưu
ký tự hoặc mã phím thô. Nó ghi hoạt động toàn phiên đăng nhập, nên tránh làm việc khác khi thu.
Không chạy agent trong lúc thu người thật; desktop lock cũng chặn hai công cụ chạy đồng thời.

## 1. Mở website demo — terminal thứ nhất

Tại thư mục dự án:

```bash
uv run python scripts/serve_catalog.py
```

Giữ terminal này mở. Catalog ở `http://127.0.0.1:8765`, dùng đúng ba sản phẩm hư cấu của demo.
Nếu cổng bận, chọn `--port 8766` và dùng URL được in ra.

## 2. Chuẩn bị

Dùng cùng máy, Chrome, LibreOffice, bố cục cửa sổ và mức zoom như lượt agent được so sánh.
Chuẩn bị Calc và Writer với file rỗng. Đọc trước yêu cầu nhiệm vụ, rồi bắt đầu thu:

- Duyệt catalog, cuộn và click Details để lấy giá/bảo hành của ba sản phẩm.
- Nhập bảng 5 cột: Product, Price USD, Warranty months, Price with 8% tax, Source.
- Hàng 2–4 là ba sản phẩm theo thứ tự catalog. D2 dùng `=B2*1.08`, tương tự D3/D4.
- Viết báo cáo gồm giá, giá sau thuế, bảo hành, URL nguồn và đề xuất sản phẩm rẻ nhất.
- Lưu cả bảng tính và báo cáo. Để so sánh chặt hơn, dùng cùng độ dài/nội dung báo cáo như demo.

Làm tự nhiên. Gõ nội dung tương ứng với tác vụ agent thay vì dán cả đoạn. Không cố tình gây lỗi,
chèn delay hoặc bắt chước tốc độ agent. Lỗi nào xảy ra thì sửa như bình thường.

## 3. Thu — terminal thứ hai

```bash
uv run --extra desktop sha capture-human --seconds 600 --output runs/human-01
```

Khi hiện `Recording metadata only...`, tự thực hiện nhiệm vụ. Có tối đa 10 phút; không cần
làm đủ 10 phút. Làm xong thì trở lại **terminal thứ hai** và Ctrl+C để kết thúc; dữ liệu đã thu
được giữ lại. Đừng dừng nhầm terminal đang phục vụ website. Lệnh có thể kết thúc với mã 130
sau Ctrl+C; đó không phải mất dữ liệu.

Đầu ra: `runs/human-01/inputs.jsonl` và `telemetry.jsonl`. Mỗi lượt cần thư mục mới (`human-02`, ...).
Công cụ thu không tự kiểm tra nội dung file bạn làm; hãy kiểm tra đúng dữ liệu/công thức/báo cáo
trước khi sử dụng lượt đó làm baseline. Lượt lỗi vẫn cần ghi nhận, không chỉ giữ các lượt đẹp.

## 4. So sánh với lượt agent đã quay

Trên máy bàn giao, dữ liệu agent đã có ở đường dẫn dưới đây. Nếu clone mới, hãy chạy một lượt
native trước và thay đường dẫn agent bằng `inputs.jsonl` của lượt đó; `runs/` không nằm trên Git.

```bash
uv run sha compare --agent runs/recorded-native-demo-final/inputs.jsonl --human runs/human-01/inputs.jsonl --output runs/baseline-comparison-01.json
```

Công cụ so sánh median/p95 và KS/Wasserstein của khoảng gõ, giữ phím, idle và tốc độ chuột.
Khoảng cách nhỏ hơn nghĩa là các phân bố gần hơn; không có ngưỡng tự động kết luận “giống người”.
Ít nhất 30 khoảng gõ hợp lệ ở mỗi bên và coverage không có gap/drop/error là điều kiện tối thiểu
của công cụ, không phải bảo đảm chất lượng thống kê. `insufficient_evidence` nghĩa là chưa đủ
bằng chứng. Trường `weighted_score` để null; công cụ không tự chấm rubric 30/30/20/20.

Bắt đầu với một lượt để kiểm tra quy trình. Muốn đánh giá đáng tin hơn, thu nhiều lượt/người
(ví dụ 3–5 để khởi đầu), nhiều người và nhiều lượt agent trong cùng điều kiện. Tách các lượt dùng
để chỉnh persona khỏi các lượt kiểm tra cuối. Đây là gợi ý thu ban đầu, không phải cỡ mẫu đã được
chứng minh đủ. Telemetry CPU/RAM được lưu nhưng lệnh compare hiện chỉ so sánh các đặc trưng input;
đánh giá tài nguyên và độ đúng đầu ra cần làm riêng. Mẫu này chỉ đại diện cho công việc đã thu.
