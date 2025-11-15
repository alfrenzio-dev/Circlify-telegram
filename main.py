import os
import asyncio
import logging
import uuid
from pathlib import Path

import ffmpeg
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# -----------------------
# Configuration
# -----------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
MAX_DURATION_SECONDS = 60          # max allowed video duration
MAX_SIMULTANEOUS = 2               # concurrent processing limit
RESIZE = 480                       # output square size (480x480)
FFMPEG_PRESET = "ultrafast"        # preset for speed
FFMPEG_CRF = 24                    # quality (lower -> better quality)
TEMP_DIR = Path(os.getenv(
    "TEMP_DIR",
    str(Path.home() / "tmp" / "circlify")
)) # temp directory
AFTER_PROCESS_TEXT = "Я так скруглил, что геометры мной гордятся 🤓🔵 Повторим?"
START_MESSAGE = ("Здарова, братишка 👋
                 "Подпишись на канал разработчика: @alfrenziodev
                 "Кидай видео — я быстро сделаю из него круг.")
ERROR_MESSAGE = "Ошибка при обработке видео. Убедитесь, что видео не длиннее 60 секунд и формат mp4/mov."

# -----------------------
# Setup
# -----------------------
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
TEMP_DIR.mkdir(parents=True, exist_ok=True)
semaphore = asyncio.Semaphore(MAX_SIMULTANEOUS)

# -----------------------
# Helpers
# -----------------------
def _unique_path(suffix: str) -> Path:
    return TEMP_DIR / f"{uuid.uuid4().hex}{suffix}"

async def run_ffmpeg_async(stream):
    # Run blocking ffmpeg in thread
    await asyncio.to_thread(stream.run, overwrite_output=True)

async def convert_to_video_note(input_path: str, output_path: str):
    # Probe to get video info
    try:
        info = ffmpeg.probe(input_path)
    except ffmpeg.Error as e:
        logger.exception("ffprobe failed")
        raise

    video_stream = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    if not video_stream:
        raise ValueError("No video stream found")

    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))
    duration = float(video_stream.get("duration", info.get("format", {}).get("duration", 0)) or 0)

    size = min(width, height) or min(width, height) or RESIZE

    # crop center square then scale
    crop_w = size
    crop_h = size

    # Build ffmpeg pipeline using ffmpeg-python
    stream = (
        ffmpeg
        .input(input_path)
        .crop(f"(iw-{crop_w})/2", f"(ih-{crop_h})/2", crop_w, crop_h)
        .filter("scale", RESIZE, RESIZE)
        .filter("format", "yuv420p")
        .output(
            output_path,
            vcodec="libx264",
            preset=FFMPEG_PRESET,
            crf=FFMPEG_CRF,
            movflags="+faststart",
            pix_fmt="yuv420p"
        )
    )

    await run_ffmpeg_async(stream)
    return duration

# -----------------------
# Bot handlers
# -----------------------
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(START_MESSAGE)

async def video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    # Only accept if message has video
    video = message.video or (message.document if getattr(message, "document", None) and (getattr(message.document, "mime_type", "") or "").startswith("video") else None)
    if not video:
        await message.reply_text("Пожалуйста, отправь видео (mp4/mov).")
        return

    # Best-effort reaction: try known methods (names may vary across PTB versions)
    try:
        react_fn = getattr(message, "react", None) or getattr(message, "set_reaction", None) or getattr(context.bot, "set_reaction", None)
        if callable(react_fn):
            try:
                await react_fn("👌")
            except TypeError:
                try:
                    await react_fn(["👌"])
                except Exception:
                    pass
    except Exception:
        logger.debug("Reaction attempt failed", exc_info=True)

    # Limit concurrency
    async with semaphore:
        input_path = _unique_path(".mp4")
        output_path = _unique_path(".mp4")
        try:
            # download file
            file = await context.bot.get_file(video.file_id)
            await file.download_to_drive(str(input_path))

            # quick probe for duration
            try:
                info = ffmpeg.probe(str(input_path))
                fmt_duration = float(info.get("format", {}).get("duration", 0) or 0)
                if fmt_duration > MAX_DURATION_SECONDS:
                    await message.reply_text(f"Видео слишком длинное ({int(fmt_duration)}s). Максимум {MAX_DURATION_SECONDS}s.")
                    return
            except Exception:
                logger.warning("Could not probe duration; proceeding")

            # convert
            await message.reply_chat_action("record_video")
            duration = await convert_to_video_note(str(input_path), str(output_path))

            # send as video_note (makes it round in Telegram)
            try:
                await message.reply_video_note(video_note=open(output_path, "rb"))
            except TypeError:
                await message.reply_video_note(open(output_path, "rb"))

            await message.reply_text(AFTER_PROCESS_TEXT)
        except Exception as e:
            logger.exception("Processing failed")
            await message.reply_text(ERROR_MESSAGE)
        finally:
            # cleanup
            try:
                if input_path.exists():
                    input_path.unlink()
                if output_path.exists():
                    output_path.unlink()
            except Exception:
                logger.debug("Cleanup failed", exc_info=True)


def build_application():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set. Exiting.")
        raise RuntimeError("BOT_TOKEN environment variable is required")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, video_handler))
    return app

def main():
    app = build_application()
    logger.info("Starting Circlify Bot")
    app.run_polling()

if __name__ == "__main__":
    main()
