import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="TIY")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
def home():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


def get_duration(path):
    command = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ]

    result = subprocess.run(command, capture_output=True, text=True)
    return float(result.stdout.strip())


@app.post("/api/create-clips")
async def create_clips(
    video: UploadFile = File(...),
    clips_count: int = Form(5),
    clip_duration: int = Form(30)
):
    work_dir = tempfile.mkdtemp(prefix="tiy_")
    input_path = os.path.join(work_dir, "input.mp4")

    with open(input_path, "wb") as file:
        shutil.copyfileobj(video.file, file)

    try:
        total_duration = get_duration(input_path)
    except Exception:
        shutil.rmtree(work_dir, ignore_errors=True)
        return {"error": "تعذر قراءة الفيديو"}

    if total_duration <= clip_duration:
        starts = [0]
    elif clips_count == 1:
        starts = [(total_duration - clip_duration) / 2]
    else:
        step = (total_duration - clip_duration) / (clips_count - 1)
        starts = [i * step for i in range(clips_count)]

    output_files = []

    for number, start in enumerate(starts, 1):
        output_path = os.path.join(work_dir, f"TIY_clip_{number}.mp4")

        command = [
            "ffmpeg",
            "-y",
            "-ss", str(start),
            "-i", input_path,
            "-t", str(clip_duration),
            "-vf",
            "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            output_path
        ]

        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if os.path.exists(output_path):
            output_files.append(output_path)

    zip_path = os.path.join(work_dir, "TIY_clips.zip")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in output_files:
            archive.write(file_path, os.path.basename(file_path))

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename="TIY_clips.zip"
  )
