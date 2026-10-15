# NEWS AI BOT — 5 tin RSS → 5 video dọc → 1 podcast → Telegram

> Dự án Python minh họa tự động hóa tin tức bằng RSS. Mặc định chương trình **chỉ tạo file, không đăng công khai**; đăng Telegram khi chủ động dùng `--publish`. Nội dung **cần được kiểm tra trước khi công khai**.

## 1. Yêu cầu

- Windows 10/11; Python 3.10+; kết nối Internet.
- [FFmpeg](https://ffmpeg.org/download.html) đã cài và thêm vào PATH (`ffmpeg -version`).
- Quyền sử dụng nguồn RSS, quyền gửi bài tới chat/kênh Telegram của mình.

## 2. Cài đặt

Mở Terminal ở thư mục này:

```powershell
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
```

Nếu không dùng môi trường ảo, có thể dùng `python -m pip install -r requirements.txt`. Chạy `python --version` để kiểm tra. Nếu dùng `.venv`, sửa 2 file `.bat` thay `python` bằng `.venv\Scripts\python.exe` để Task Scheduler chạy ổn định.

## 3. Cài Telegram Bot

1. Trên Telegram, mở tài khoản xác thực `@BotFather`; gửi `/newbot`, đặt tên và username. Lưu bot token vào `TELEGRAM_BOT_TOKEN` trong `.env` (không chia sẻ token).
2. Tạo một **kênh thử nghiệm riêng tư** hoặc nhóm Telegram của mình. Thêm bot vào đó; ở kênh, cấp quyền đăng bài cho bot.
3. Đặt `TELEGRAM_CHAT_ID=@username_kenh_cong_khai` nếu kênh có username công khai. Với nhóm/kênh riêng tư, lấy **numeric chat ID** bằng Bot API `getUpdates` sau khi phát sinh một cập nhật mà bot nhận được, hoặc dùng cách xác định chat ID phù hợp. ID riêng tư thường là số âm, không dùng link mời làm chat ID.
4. Nếu `getUpdates` không thấy chat, thêm bot vào nhóm rồi gửi một tin nhắn/đề cập bot; với kênh, một bài `channel_post` mới có thể giúp xác định ID, nếu bot có quyền. Không đăng token lên ảnh chụp hoặc kho mã.

Có thể để trống `OPENAI_API_KEY`: ứng dụng vẫn tạo nội dung bằng cách diễn đạt lại tiêu đề và mô tả RSS. Nếu cấu hình khóa API, ứng dụng yêu cầu mô hình viết lời dẫn ngắn dựa trên metadata RSS (có thể phát sinh phí). Đổi `OPENAI_MODEL` theo mô hình tài khoản bạn hỗ trợ.

## 4. Chạy thử và xem đầu ra

```powershell
python main.py --dry-run --force
```

Tại `output/YYYYMMDD_HHMMSS/` sẽ có:
- `news_01.mp4` ... `news_05.mp4`: video 9:16, ảnh tĩnh + tiếng Việt.
- `news_01.mp3` ...: âm thanh cho từng tin; file `.png` là hình nền.
- `podcast.mp3`: bản đọc nối tiếp toàn bộ tin với lời mở và kết.
- `social_post.txt`: nội dung bài đăng kèm nguồn bài gốc.
- `articles.json`, `script_*.txt`, `podcast_script.txt`: dữ liệu và lời dẫn để rà soát.

**Rà soát trước khi đăng**: xem 5 tiêu đề, lời dẫn, tính đúng đắn và quyền sử dụng hình/tin. Nguồn RSS có thể thay đổi/không truy cập được: chương trình cảnh báo và có thể tạo dưới 5 bản tin. Giọng đọc `edge-tts` cần Internet và dịch vụ bên ngoài nên đôi lúc có thể lỗi.

## 5. Đăng Telegram

Sau khi kiểm tra bản thử, điền token và chat ID vào `.env`:

```powershell
python main.py --publish --force
```

Bot sẽ gửi tin nhắn giới thiệu, từng video có tiêu đề và nguồn bài gốc, sau cùng là podcast. Telegram có giới hạn kích thước file và tốc độ gửi; video dài/lớn có thể bị từ chối. **Không dùng `--force` khi chạy hàng ngày** (sẽ xử lý lại tin cũ).

## 6. Chạy hằng ngày

- Tạo tác vụ Task Scheduler → Create Basic Task → Daily (ví dụ 07:00).
- Program: đường dẫn tuyệt đối tới `python.exe` của `.venv`.
- Arguments: `main.py --publish`
- Start in: đường dẫn tuyệt đối tới thư mục `news-ai-bot`.
- Chạy thử Task Scheduler bằng `--dry-run` trước, chỉ chuyển thành `--publish` sau khi kiểm tra.
- `history.json` lưu URL tin đã xử lý để tránh trùng giữa các lần chạy thành công. Nếu Telegram gửi dở rồi lỗi, chương trình **không** đánh dấu đã xử lý nên khi chạy lại có thể gửi lại một phần; cần kiểm tra kênh trước khi chạy lại.

## 7. Những điểm cần lưu ý

- Không được xem tin RSS là toàn bộ bài báo. Bản tóm tắt chỉ dựa vào **tiêu đề và mô tả RSS**, không khẳng định đã xác minh đầy đủ.
- Ghi nguồn, dẫn về bài gốc và tuân thủ điều kiện sử dụng RSS, quyền tác giả. Không sử dụng ảnh bài báo khi chưa có quyền; video dùng nền tự vẽ.
- Nội dung do AI tạo có thể sai: **nên duyệt thủ công trước khi đăng**, nhất là tin chính trị, sức khỏe, pháp luật và sự kiện nóng.
- Dự án đăng **Telegram**. Tự đăng Facebook/YouTube/TikTok yêu cầu API và quyền riêng; **chưa tích hợp**.
- Giọng đọc Edge TTS không bảo đảm thời gian đáp ứng/khả dụng; chú ý điều khoản dịch vụ.

## 8. Tùy chỉnh

- Đổi 5 chủ đề ở biến `SOURCES` trong `main.py`.
- Đổi giọng bằng `VOICE` trong `.env` (ví dụ `vi-VN-NamMinhNeural`).
- Mặc định mỗi chủ đề ưu tiên 1 tin, sau đó lấy thêm nếu thiếu; tối đa 5 tin.
- Chạy lại đầu ra demo: `python main.py --dry-run --force`.
