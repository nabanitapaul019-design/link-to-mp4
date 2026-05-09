import os
import asyncio
import logging
import time
from pyrogram import Client, filters, enums
from pyrogram.types import Message
import ffmpeg as ff_python

# --- Configuration ---
API_ID = 25399723
API_HASH = '49bf6c6103c8eb427911362c6d5d5bf3'
BOT_TOKEN = '8658754195:AAEZ8LaoBagaX49NSLo8-O2ZapiKCXhs7ro'

MAIN_CHANNEL = "@twitterpanu1"
FORWARD_CHANNELS = ["@twitterpanu2", "@twitterpanu3", "@twitterpanu4"]

# Queue Setup
message_queue = asyncio.Queue()
is_processing = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=100)


# -------------------------------------------------
# 🔍 METADATA
# -------------------------------------------------
def get_video_metadata(file_path):
    try:
        meta = ff_python.probe(file_path)
        video_stream = next(
            (s for s in meta["streams"] if s["codec_type"] == "video"),
            None
        )

        if not video_stream:
            return 0, 0, 0

        duration = int(float(meta["format"].get("duration", 0)))
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))

        return duration, width, height
    except Exception as e:
        logger.error(f"Metadata error: {e}")
        return 0, 0, 0


# -------------------------------------------------
# 🖼️ THUMBNAIL
# -------------------------------------------------
def generate_thumbnail(video_path, thumb_path):
    try:
        (
            ff_python
            .input(video_path)
            .output(
                thumb_path,
                vframes=1,
                ss=30,
                vf="scale=320:-1",
                loglevel="quiet"
            )
            .run()
        )
        return thumb_path
    except Exception as e:
        logger.error(f"Thumbnail error: {e}")
        return None

# -------------------------------------------------
# 📊 PROGRESS
# -------------------------------------------------
async def progress_callback(current, total, file_name, start_time, phase):
    elapsed = time.time() - start_time
    if elapsed == 0:
        return

    percent = current * 100 / total
    speed = current / elapsed

    if speed > 1024 * 1024:
        speed_str = f"{speed/(1024*1024):.2f} MB/s"
    elif speed > 1024:
        speed_str = f"{speed/1024:.2f} KB/s"
    else:
        speed_str = f"{speed:.2f} B/s"

    print(f"\r{phase}: {file_name} | {percent:.2f}% | {speed_str}", end="")

    if current == total:
        print("")


# -------------------------------------------------
# 🚀 MAIN PROCESSOR
# -------------------------------------------------
async def process_file_task(message: Message):
    global is_processing

    file_name = "file"
    local_file_path = None
    thumb_path = None

    duration = 0
    width = 0
    height = 0

    try:
        # Detect media
        if message.video:
            media = message.video
            file_name = media.file_name or "video.mp4"
            mime_type = "video/mp4"
            duration = media.duration
            width = media.width
            height = media.height

        elif message.document:
            media = message.document
            file_name = media.file_name
            mime_type = media.mime_type or ""

        else:
            return

        is_video = mime_type.startswith("video/") or file_name.lower().endswith(".mp4")

        # ✅ STATUS MESSAGE
        status_msg = await message.reply(
            f"⬇️ **𝗗𝗼𝗪𝗡𝗟𝗢𝗔𝗗𝗶𝗡𝗚 : \n\n** `{file_name}`"
        )

        # -------------------------------------------------
        # ⬇️ DOWNLOAD (FULL FILE — NO TRIM)
        # -------------------------------------------------
        start_dl = time.time()

        local_file_path = await app.download_media(
            message,
            file_name=f"downloads/{file_name}",
            progress=progress_callback,
            progress_args=(file_name, start_dl, "DOWNLOADING")
        )

        # -------------------------------------------------
        # 🎬 VIDEO PROCESSING
        # -------------------------------------------------
        if is_video:
            if duration == 0:
                duration, width, height = get_video_metadata(local_file_path)

            thumb_path = f"thumbs/{os.path.splitext(file_name)[0]}.jpg"
            os.makedirs("thumbs", exist_ok=True)
            generate_thumbnail(local_file_path, thumb_path)

        # ✅ UPDATE STATUS
        await status_msg.edit(
            f"⬆️ **𝗨𝗣𝗟𝗢𝗔𝗗𝗶𝗡𝗚 : \n\n** `{file_name}` "
        )

        # -------------------------------------------------
        # ⬆️ UPLOAD (NO TRIMMING GUARANTEED)
        # -------------------------------------------------
        start_ul = time.time()

        if is_video:
            uploaded_msg = await app.send_video(
                chat_id=MAIN_CHANNEL,
                video=local_file_path,
                thumb=thumb_path if thumb_path and os.path.exists(thumb_path) else None,
                caption="",
                supports_streaming=True,
                duration=duration,
                width=width,
                height=height,
                progress=progress_callback,
                progress_args=(file_name, start_ul, "UPLOADING")
            )
        else:
            uploaded_msg = await app.send_document(
                chat_id=MAIN_CHANNEL,
                document=local_file_path,
                caption="",
                progress=progress_callback,
                progress_args=(file_name, start_ul, "UPLOADING")
            )

        # -------------------------------------------------
        # 🔄 FORWARD
        # -------------------------------------------------
        for channel in FORWARD_CHANNELS:
            try:
                await uploaded_msg.forward(chat_id=channel)
            except Exception as e:
                logger.error(f"Forward failed to {channel}: {e}")

        await status_msg.edit(f"✅ ** 𝗗𝗼𝗡𝗘 𝗣𝗥𝗼𝗖𝗘𝗦𝗦𝗶𝗡𝗚 :** `{file_name}`")
        await message.delete()

    except Exception as e:
        logger.error(e)
        try:
            await message.reply(f"❌ Failed: {e}")
        except:
            pass

    finally:
        # cleanup
        try:
            if local_file_path and os.path.exists(local_file_path):
                os.remove(local_file_path)
            if thumb_path and os.path.exists(thumb_path):
                os.remove(thumb_path)
        except:
            pass

        is_processing = False
        if not message_queue.empty():
            next_msg = await message_queue.get()
            asyncio.create_task(process_file_task(next_msg))


# -------------------------------------------------
# 📩 HANDLERS
# -------------------------------------------------
@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    await message.reply(
        "👋 **Hello! Welcome to Message Forwarder Bot.**\n\n"
        "Send me any **Document** or **Video** file.\n"
        "I will:\n"
        "1. Download it.\n"
        "2. Generate a thumbnail (FFmpeg).\n"
        "3. Upload as Video to channels.\n"
        "4. Clean up your chat.\n\n"
        "🚀 *Queue system active. Send multiple files!*",
        parse_mode=enums.ParseMode.MARKDOWN
    )


@app.on_message(filters.private & (filters.document | filters.video))
async def handle_media(client, message: Message):
    global is_processing

    await message_queue.put(message)

    if not is_processing:
        is_processing = True
        next_msg = await message_queue.get()
        asyncio.create_task(process_file_task(next_msg))


# -------------------------------------------------
# 🟢 RUN
# -------------------------------------------------
if __name__ == "__main__":
    os.makedirs("downloads", exist_ok=True)
    os.makedirs("thumbs", exist_ok=True)
    print("🚀 Bot Started...")
    app.run()