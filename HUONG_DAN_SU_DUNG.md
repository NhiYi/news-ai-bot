# HƯỚNG DẪN CÀI ĐẶT VÀ SỬ DỤNG NEWS AI BOT

**Dự án:** News AI Bot — Tự động tổng hợp 5 tin RSS, tạo video, podcast và gửi qua Telegram  
**Ngôn ngữ:** Python  
**Môi trường hướng dẫn:** Windows 10/11 + Visual Studio Code

> **Lưu ý:** Đây là dự án mẫu tự động hóa. Nội dung lời dẫn dựa trên tiêu đề và mô tả RSS, không phải nội dung bài báo đã được kiểm chứng đầy đủ. Hãy kiểm tra độ chính xác, nguồn tin và quyền sử dụng trước khi công bố.

## 1. Chức năng

- Lấy tối đa 5 tin theo các nhóm chủ đề từ nguồn RSS.
- Biên tập lời dẫn tiếng Việt từ dữ liệu RSS; hỗ trợ API AI nếu người dùng tự cấu hình.
- Tạo video dạng dọc 9:16 (`.mp4`) cho từng tin và file giọng đọc (`.mp3`).
- Ghép một podcast tổng hợp (`podcast.mp3`).
- Sinh bài đăng kèm liên kết bài gốc (`social_post.txt`).
- Gửi video và podcast qua Telegram Bot API khi bật chế độ đăng.
- Lưu lịch sử `history.json` để giảm lặp tin; chạy định kỳ bằng Windows Task Scheduler.

## 2. Chuẩn bị

Cần có:

1. **Python 3.10 trở lên**, khuyến nghị Python 3.12.
2. **FFmpeg** và lệnh `ffmpeg` truy cập được từ PowerShell.
3. **VS Code** hoặc trình soạn thảo bất kỳ.
4. Internet để đọc RSS, tạo giọng đọc và kết nối Telegram.
5. Tài khoản Telegram cùng bot tạo từ [@BotFather](https://t.me/BotFather), nếu muốn đăng.

### 2.1. Cài Python

Trong PowerShell:

```powershell
winget install -e --id Python.Python.3.12
```

Đóng và mở lại VS Code/PowerShell sau khi cài, rồi kiểm tra:

```powershell
python --version
```

Nếu Windows vẫn báo không tìm thấy Python, kiểm tra PATH và mục **Settings → Apps → Advanced app settings → App execution aliases** (tắt alias Microsoft Store nếu gây xung đột). Khi cài thủ công từ python.org, bật tùy chọn thêm Python vào PATH nếu có.

### 2.2. Cài FFmpeg

```powershell
winget install --id Gyan.FFmpeg -e
```

**Đóng và mở lại VS Code/Terminal** rồi kiểm tra:

```powershell
ffmpeg -version
```

Nếu vẫn không nhận lệnh sau khi mở lại, làm mới PATH cho Terminal hiện tại:

```powershell
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
ffmpeg -version
```

## 3. Mở dự án và cài thư viện

Tải mã nguồn từ GitHub (Download ZIP rồi giải nén, hoặc `git clone`) và mở **thư mục chứa `main.py`** bằng VS Code.

Ví dụ thư mục trên máy phát triển:

```text
D:\New folder\news-ai-bot
```

Trong Terminal của VS Code:

```powershell
cd "D:\New folder\news-ai-bot"
python -m pip install -r requirements.txt
```

Thay đường dẫn trên bằng vị trí thực tế nếu bạn giải nén ở nơi khác.

**Tùy chọn — môi trường ảo:**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Nếu dùng môi trường ảo, có thể chạy chương trình bằng ` .\.venv\Scripts\python.exe ` thay cho `python`.

## 4. Cấu hình `.env` và Telegram

### 4.1. Tạo file cấu hình

Tại thư mục có `main.py`, chạy:

```powershell
Copy-Item .env.example .env
```

Mở file **`.env`** (không phải `.env.example`) và điền:

```dotenv
TELEGRAM_BOT_TOKEN=YOUR_NEW_BOT_TOKEN
TELEGRAM_CHAT_ID=YOUR_CHAT_ID
VOICE=vi-VN-HoaiMyNeural
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
```

- `TELEGRAM_BOT_TOKEN`: token bí mật do BotFather cấp.
- `TELEGRAM_CHAT_ID`: ID cá nhân, nhóm hoặc kênh nhận tin.
- `VOICE`: giọng đọc tiếng Việt; có thể dùng `vi-VN-NamMinhNeural`.
- `OPENAI_API_KEY`: có thể để trống. Khi trống, chương trình vẫn tạo lời dẫn theo quy tắc từ thông tin RSS. Dùng AI API có thể phát sinh phí.

**Bảo mật:** Không tải `.env` lên GitHub, không chụp ảnh lộ token. File `.env.example` đưa lên GitHub phải chỉ chứa giá trị mẫu. Nếu token từng bị chia sẻ, hãy thu hồi tại BotFather và cấp token khác.

### 4.2. Tạo Telegram Bot

1. Mở [@BotFather](https://t.me/BotFather) trên Telegram.
2. Gõ `/newbot`, đặt tên và username có đuôi `bot`.
3. Sao chép token **vào file `.env` của bạn**; không gửi token cho người khác.
4. Mở cuộc trò chuyện với bot mới, nhấn **Start** và gửi `Hello`.

### 4.3. Lấy Chat ID bằng PowerShell

Nhập token một cách riêng tư trên máy của bạn:

```powershell
$token = Read-Host "Nhap Telegram Bot Token" -MaskInput
$response = Invoke-RestMethod "https://api.telegram.org/bot$token/getUpdates"
$response.result | ForEach-Object { $_.message.chat.id }
```

Nếu muốn xác nhận token trước:

```powershell
Invoke-RestMethod "https://api.telegram.org/bot$token/getMe"
```

Kết quả `ok = True` nghĩa là token hợp lệ. Nếu `getUpdates` trả về rỗng, gửi một tin nhắn mới cho bot rồi thử lại. Với kênh Telegram cần cấp quyền thích hợp; ID kênh/nhóm có thể âm, và cấu trúc cập nhật có thể là `channel_post` thay vì `message`.

> Lệnh `Read-Host "Nhap Telegram Bot Token"` dùng văn bản trong ngoặc kép làm **lời nhắc**, không dùng để nhập token. Chỉ dán token khi PowerShell đợi bạn nhập giá trị.

## 5. Tạo thử video và podcast

Chạy trong thư mục dự án:

```powershell
python main.py --dry-run --force
```

Chế độ này **chỉ tạo file**, không gửi Telegram. Nếu RSS và các dịch vụ hoạt động, chương trình sẽ xử lý đến 5 tin và tạo thư mục như:

```text
output/
└── YYYYMMDD_HHMMSS/
    ├── news_01.mp4 ... news_05.mp4
    ├── news_01.mp3 ... news_05.mp3
    ├── news_01.png ... news_05.png
    ├── podcast.mp3
    ├── social_post.txt
    ├── articles.json
    ├── podcast_script.txt
    └── script_*.txt
```

Số file thực tế có thể ít hơn 5 nếu nguồn RSS không có đủ tin sử dụng được. Mở video, nghe podcast, đọc lời dẫn và kiểm tra link nguồn trước khi phát hành.

## 6. Gửi lên Telegram

Sau khi cấu hình `.env` và rà soát nội dung, chạy:

```powershell
python main.py --publish --force
```

Chương trình sẽ tạo bản tin, sau đó gửi nội dung qua Telegram nếu quyền bot và kết nối cho phép. `--force` cho phép sử dụng lại tin cũ để thử nghiệm; **không sử dụng `--force` trong tác vụ chạy mỗi ngày**.

Lưu ý: chế độ `--publish` là **đăng thật**. Nếu phát sinh lỗi khi gửi dở, có thể một số video đã được gửi; hãy kiểm tra Telegram trước khi chạy lại để tránh gửi trùng.

## 7. Lập lịch tự động 7 giờ sáng hằng ngày

### 7.1. Tạo file chạy

Trong thư mục dự án, tạo file `run_bot.bat` với nội dung:

```bat
@echo off
cd /d "D:\New folder\news-ai-bot"
python main.py --publish
```

Đổi đường dẫn thành thư mục cài đặt thực tế. Nếu máy có nhiều bản Python, nên sử dụng đường dẫn tuyệt đối tới `python.exe` trong file `.bat`.

> Bộ mã nguồn còn có thể đi kèm `run_publish.bat`; bạn có thể sử dụng file đó nếu nội dung tương ứng với thư mục cài đặt của bạn.

### 7.2. Cài Windows Task Scheduler

1. Nhấn **Win + R**, gõ `taskschd.msc`.
2. Chọn **Create Basic Task** và đặt tên `Daily News AI Bot`.
3. Trigger: **Daily**; chọn **7:00 AM**, lặp lại mỗi **1 day**.
4. Action: **Start a program**.
5. Cấu hình an toàn với đường dẫn có dấu cách:

**Program/script**

```text
C:\Windows\System32\cmd.exe
```

**Add arguments**

```text
/c ""D:\New folder\news-ai-bot\run_bot.bat""
```

**Start in** (không đặt trong dấu ngoặc kép)

```text
D:\New folder\news-ai-bot
```

6. Nhấn **Next → Finish**.
7. Tại **Task Scheduler Library**, nhấp phải tác vụ → **Run** để thử.

Một số mã trạng thái:

| Mã | Ý nghĩa |
|---|---|
| `0x41301` | Tác vụ đang chạy |
| `0x0` | Tác vụ kết thúc và báo thành công ở cấp Windows; vẫn phải kiểm tra log và Telegram |

Máy cần bật, có Internet và được phép chạy tác vụ. Trong **Properties → Settings** có thể chọn chạy sớm nhất có thể nếu bỏ lỡ lịch; trong **Conditions**, xem lại thiết lập nguồn điện/ngủ nếu cần.

## 8. Lỗi thường gặp và cách xử lý

| Hiện tượng | Nguyên nhân thường gặp | Cách giải quyết |
|---|---|---|
| `Python was not found` | Python chưa cài hoặc chưa vào PATH | Cài Python, mở lại VS Code, kiểm tra alias và `python --version` |
| `ffmpeg is not recognized` | Terminal chưa nhận PATH mới | Đóng mở Terminal, chạy `ffmpeg -version`, kiểm tra PATH |
| `Thiếu TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID trong .env` | Chỉ có `.env.example` hoặc thiếu giá trị | Tạo `.env`, nhập cả hai biến, lưu và chạy lại |
| Telegram API trả về `404 Not Found` | URL/token sai hoặc biến token chưa gán | Nhập lại token bằng `Read-Host`, thử `getMe`; thu hồi token bị lộ |
| Không có Chat ID | Chưa nhấn Start/chưa gửi tin cho bot | Gửi `Hello`, gọi lại `getUpdates` |
| Không thấy file mới | Nguồn RSS lỗi, lỗi dịch vụ hoặc không có tin phù hợp | Xem log Terminal, thư mục `output/` và thử chạy `--dry-run --force` |
| Tác vụ chạy nhưng không có tin trên Telegram | Tin đã được lưu vào lịch sử hoặc gửi thất bại | Kiểm tra `history.json` và log; không kết luận từ `0x0` đơn thuần |

## 9. Đưa source code lên GitHub

Đưa lên repository: `main.py`, `requirements.txt`, `README.md`, `HUONG_DAN_SU_DUNG.md`, `.env.example` (chỉ chứa giá trị mẫu), `.gitignore` và file `.bat` cần thiết.

**Không đưa lên:** `.env`, `output/`, `history.json`, `__pycache__/`, `.venv/` và các file khóa bí mật. File `.gitignore` nên có tối thiểu:

```gitignore
.env
.venv/
__pycache__/
output/
history.json
*.pyc
```

Bạn có thể upload bằng giao diện GitHub: **Add file → Upload files → Commit changes**. `.gitignore` không thay thế việc tự kiểm tra file trước khi upload trên website.

## 10. Giới hạn và hướng phát triển

- Dữ liệu RSS không bao gồm toàn bộ nội dung bài báo. Lời dẫn cần được rà soát thủ công về độ chính xác.
- Video hiện dùng hình nền/tiêu đề và giọng đọc; có thể mở rộng phụ đề, chuyển cảnh và hình ảnh được cấp phép.
- Tích hợp đăng trực tiếp trong dự án là **Telegram**; YouTube, Facebook và TikTok cần API, xác thực và quyền riêng, chưa có trong bản hiện tại.
- Có thể phát triển giao diện quản lý, cơ chế duyệt trước khi đăng, theo dõi log và chạy trên máy chủ.

---

**Trạng thái thử nghiệm:** Đã chạy trên Windows, tạo video/podcast, gửi Telegram và thiết lập Task Scheduler. Khi triển khai trên máy khác, cần tự kiểm tra nguồn RSS, API và cấu hình môi trường.
