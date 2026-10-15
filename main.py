"""Bot tin tức: RSS -> biên tập -> TTS -> Shorts + podcast -> Telegram.
Chạy thử: python main.py --dry-run
Đăng Telegram: python main.py --publish
"""
from __future__ import annotations

import argparse
import asyncio
import html
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
from datetime import datetime
from pathlib import Path

import edge_tts
import feedparser
import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / ".env")
OUTPUT = BASE / "output"
HISTORY = BASE / "history.json"
SOURCES = {
    "Thời sự": "https://vnexpress.net/rss/thoi-su.rss",
    "Thế giới": "https://vnexpress.net/rss/the-gioi.rss",
    "Kinh doanh": "https://vnexpress.net/rss/kinh-doanh.rss",
    "Công nghệ": "https://vnexpress.net/rss/khoa-hoc-cong-nghe.rss",
    "Thể thao": "https://vnexpress.net/rss/the-thao.rss",
}
VOICE = os.getenv("VOICE", "vi-VN-HoaiMyNeural")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
USER_AGENT = "NewsDigestStudentBot/1.0 (+educational, RSS attribution)"
LOG = logging.getLogger("news-bot")


def clean(value: str) -> str:
    s = re.sub(r"<[^>]*>", " ", value or "")
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def read_history() -> set[str]:
    try:
        data = json.loads(HISTORY.read_text(encoding="utf-8"))
        return set(data) if isinstance(data, list) else set()
    except (OSError, json.JSONDecodeError):
        return set()


def save_history(links: set[str]) -> None:
    temp = HISTORY.with_suffix(".tmp")
    temp.write_text(json.dumps(sorted(links), ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(HISTORY)


def fetch_news(max_items: int, seen: set[str]) -> list[dict]:
    candidates: dict[str, list[dict]] = {}
    for category, url in SOURCES.items():
        try:
            response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
            response.raise_for_status()
            parsed = feedparser.parse(response.content)
            entries = []
            for entry in parsed.entries:
                title = clean(entry.get("title", ""))
                link = (entry.get("link") or "").strip()
                summary = clean(entry.get("summary", ""))
                if not title or not link or link in seen:
                    continue
                entries.append({"category": category, "title": title,
                                "summary": summary, "link": link})
            candidates[category] = entries
            LOG.info("%s: %d tin có thể sử dụng", category, len(entries))
        except (requests.RequestException, ValueError) as exc:
            LOG.warning("Không tải được %s: %s", category, exc)
            candidates[category] = []

    result, picked = [], set()
    # Ưu tiên một tin ở mỗi chuyên mục, sau đó bổ sung tới đủ 5 tin.
    for idx in range(max((len(items) for items in candidates.values()), default=0)):
        for category in SOURCES:
            if len(result) >= max_items:
                break
            items = candidates[category]
            if idx < len(items) and items[idx]["link"] not in picked:
                result.append(items[idx]); picked.add(items[idx]["link"])
        if len(result) >= max_items:
            break
    return result


def short_summary(summary: str) -> str:
    # Chỉ dựa vào mô tả RSS. Tránh viết thêm sự kiện không có trong nguồn.
    s = clean(summary)
    if not s:
        return "Chi tiết được trình bày trong bài báo gốc."
    parts = re.split(r"(?<=[.!?])\s+", s)
    result = " ".join(parts[:2]).strip()
    if len(result) > 320:
        result = result[:317].rsplit(" ", 1)[0] + "..."
    return result


def ai_rewrite(item: dict) -> str | None:
    """Tùy chọn: biên tập với API. Cần kiểm tra bản thảo trước đăng."""
    if not OPENAI_API_KEY:
        return None
    instruction = (
        "Bạn biên tập một lời dẫn tin tức tiếng Việt ngắn, trung lập, dễ đọc thành tiếng, "
        "không quá 90 từ. CHỈ dựa vào tiêu đề và mô tả RSS đã cung cấp. "
        "Không đoán chi tiết, không thêm số liệu, không biến cáo buộc thành sự thật. "
        "Nếu thiếu thông tin, nêu rõ là theo mô tả RSS. Không markdown."
    )
    try:
        res = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}",
                     "Content-Type": "application/json"},
            json={"model": OPENAI_MODEL, "temperature": 0.2, "max_tokens": 300,
                  "messages": [{"role": "system", "content": instruction},
                               {"role": "user", "content": json.dumps({
                                   "title": item["title"], "summary": item["summary"]
                               }, ensure_ascii=False)}]},
            timeout=35,
        )
        res.raise_for_status()
        script = clean(res.json()["choices"][0]["message"]["content"])
        return script[:1000] or None
    except (requests.RequestException, KeyError, ValueError, IndexError) as exc:
        LOG.warning("Biên tập AI thất bại, dùng bản tóm tắt RSS: %s", exc)
        return None


def edit_item(item: dict) -> str:
    rewritten = ai_rewrite(item)
    body = rewritten if rewritten else f'{item["title"]}. {short_summary(item["summary"])}'
    return f'Chuyên mục {item["category"]}. {body} Nguồn tin: VnExpress.'


def font_path(bold: bool) -> str:
    options = (["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf"]
               if bold else ["C:/Windows/Fonts/arial.ttf"])
    options += ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
                else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    for p in options:
        if Path(p).exists():
            return p
    raise RuntimeError("Không tìm thấy font Unicode. Cần cài Arial hoặc DejaVu Sans.")


def draw_wrapped(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
                 x: int, y: int, width: int, spacing: int, fill: str) -> int:
    line = ""
    for word in text.split():
        trial = (line + " " + word).strip()
        if draw.textbbox((0, 0), trial, font=font)[2] <= width:
            line = trial
        else:
            if line:
                draw.text((x, y), line, font=font, fill=fill); y += spacing
            line = word
    if line:
        draw.text((x, y), line, font=font, fill=fill); y += spacing
    return y


def make_cover(item: dict, target: Path, number: int) -> None:
    image = Image.new("RGB", (1080, 1920), (13, 25, 47))
    d = ImageDraw.Draw(image)
    regular = ImageFont.truetype(font_path(False), 35)
    bold = ImageFont.truetype(font_path(True), 59)
    d.rounded_rectangle((65, 125, 1015, 245), radius=25, fill=(35, 91, 160))
    d.text((99, 160), f"BẢN TIN • {number:02d}", font=regular, fill="white")
    d.text((85, 430), item["category"].upper(), font=regular, fill=(100, 203, 245))
    y = draw_wrapped(d, item["title"], bold, 85, 580, 910, 93, "white")
    if y < 1480:
        d.line((85, y + 50, 995, y + 50), fill=(83, 117, 158), width=3)
    d.text((85, 1680), "TIN TỨC TÓM TẮT • NGUỒN: VNEXPRESS",
           font=ImageFont.truetype(font_path(False), 27), fill=(188, 205, 222))
    d.text((85, 1750), "Xem liên kết bài gốc trong bài đăng", font=regular,
           fill=(188, 205, 222))
    image.save(target)


def ffmpeg(args: list[str]) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"] + args
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"FFmpeg lỗi: {exc.stderr}") from exc


async def speech(text: str, path: Path) -> None:
    await edge_tts.Communicate(text, VOICE, rate="-3%").save(str(path))


def telegram_post(method: str, data: dict, file_path: Path | None = None,
                  field: str = "video") -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    if file_path is None:
        res = requests.post(url, data=data, timeout=40)
    else:
        with file_path.open("rb") as file:
            res = requests.post(url, data=data, files={field: file}, timeout=180)
    res.raise_for_status()
    reply = res.json()
    if not reply.get("ok"):
        raise RuntimeError(f"Telegram không chấp nhận: {reply.get('description', 'unknown')}")


def publish_telegram(news: list[dict], folder: Path) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("Thiếu TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID trong .env")
    telegram_post("sendMessage", {"chat_id": CHAT_ID,
               "text": f"📰 BẢN TIN TỰ ĐỘNG — {datetime.now():%d/%m/%Y}\n"
                       "Tin tổng hợp dựa trên RSS; vui lòng kiểm tra nguồn gốc."})
    for i, item in enumerate(news, start=1):
        caption = f'{i}. {item["title"]}\nNguồn: {item["link"]}'
        telegram_post("sendVideo", {"chat_id": CHAT_ID, "caption": caption[:1000],
                      "supports_streaming": "true"}, folder / f"news_{i:02}.mp4")
        LOG.info("Đã gửi video %d/%d", i, len(news))
        time.sleep(1)
    telegram_post("sendAudio", {"chat_id": CHAT_ID,
                  "caption": "🎧 Podcast tổng hợp bản tin (nguồn ở các video phía trên)",
                  "title": "Podcast bản tin tổng hợp"},
                  folder / "podcast.mp3", field="audio")
    LOG.info("Đã gửi podcast lên Telegram")


async def run(args: argparse.Namespace) -> int:
    if not shutil.which("ffmpeg"):
        LOG.error("Không tìm thấy ffmpeg. Cài FFmpeg và thêm vào PATH.")
        return 1
    history = read_history()
    news = fetch_news(5, set() if args.force else history)
    if not news:
        LOG.warning("Không có tin mới; không tạo bản tin. Dùng --force để chạy thử tin cũ.")
        return 0
    if len(news) < 5:
        LOG.warning("Chỉ lấy được %d/5 tin, kiểm tra nguồn RSS hoặc --force", len(news))
    folder = OUTPUT / datetime.now().strftime("%Y%m%d_%H%M%S")
    folder.mkdir(parents=True, exist_ok=True)
    LOG.info("Tạo bản tin trong %s", folder)
    scripts = []
    try:
        for i, item in enumerate(news, start=1):
            LOG.info("[%d/%d] %s", i, len(news), item["title"])
            script = edit_item(item)
            scripts.append(script)
            (folder / f"script_{i:02}.txt").write_text(script, encoding="utf-8")
            audio = folder / f"news_{i:02}.mp3"
            cover = folder / f"news_{i:02}.png"
            await speech(script, audio)
            make_cover(item, cover, i)
            ffmpeg(["-loop", "1", "-framerate", "25", "-i", str(cover),
                    "-i", str(audio), "-c:v", "libx264", "-preset", "veryfast",
                    "-tune", "stillimage", "-pix_fmt", "yuv420p", "-c:a", "aac",
                    "-b:a", "128k", "-shortest", "-movflags", "+faststart",
                    str(folder / f"news_{i:02}.mp4")])
        podcast_text = (f"Xin chào, đây là podcast tổng hợp {len(news)} tin tức. "
                        + " ".join(scripts)
                        + " Cảm ơn bạn đã theo dõi. Hãy xem liên kết nguồn để tìm hiểu chi tiết.")
        (folder / "podcast_script.txt").write_text(podcast_text, encoding="utf-8")
        await speech(podcast_text, folder / "podcast.mp3")
        social = ["📰 BẢN TIN TỔNG HỢP", ""]
        social.extend(f'{i}. {it["title"]}\nNguồn: {it["link"]}\n'
                      for i, it in enumerate(news, 1))
        social.append("#Tintuc #Podcast #Bantin")
        (folder / "social_post.txt").write_text("\n".join(social), encoding="utf-8")
        (folder / "articles.json").write_text(json.dumps(news, ensure_ascii=False,
                                                  indent=2), encoding="utf-8")
        if args.publish:
            LOG.info("Bắt đầu gửi Telegram")
            publish_telegram(news, folder)
        else:
            LOG.info("Chế độ xem trước: chưa đăng. Chạy --publish để đăng Telegram.")
        # Chỉ đánh dấu đã xử lý sau khi tạo thành công (và đăng thành công nếu --publish).
        history.update(item["link"] for item in news)
        if not args.force:
            save_history(history)
        LOG.info("XONG: %s", folder)
        return 0
    except (RuntimeError, requests.RequestException, OSError, Exception) as exc:
        LOG.exception("Có lỗi. Kiểm tra nội dung trong %s: %s", folder, exc)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Tạo 5 Shorts, podcast và đăng Telegram")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--publish", action="store_true", help="Gửi lên Telegram")
    group.add_argument("--dry-run", action="store_true", help="Chỉ tạo sản phẩm, không đăng")
    parser.add_argument("--force", action="store_true", help="Cho phép lấy lại tin đã dùng (demo)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
