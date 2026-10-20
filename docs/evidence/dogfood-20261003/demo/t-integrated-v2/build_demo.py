"""Assemble actual evidence stills and captions; never alter their UI content."""
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parent
story = json.loads((root / "storyboard.json").read_text())
assert sum(s["seconds"] for s in story["scenes"]) == story["duration_sec"] == 72
for i, scene in enumerate(story["scenes"]):
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-loop", "1", "-framerate", "12", "-i", str(root / scene["image"]),
        "-loop", "1", "-framerate", "12", "-i", str(root / f"caption-{i:02}.png"),
        "-filter_complex", "[0:v]scale=1920:900:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:0:black[screen];[screen][1:v]overlay=0:900,scale=1920:1080,setsar=1[out]",
        "-map", "[out]", "-t", str(scene["seconds"]), "-an", "-c:v", "libx264",
        "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(root / f"segment-{i:02}.mp4"),
    ], check=True)
(root / "segments.txt").write_text("".join(f"file 'segment-{i:02}.mp4'\n" for i in range(len(story["scenes"]))))
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(root / "segments.txt"),
                "-c", "copy", "-movflags", "+faststart", str(root / "local-evidence-walkthrough-72s.mp4")], check=True)
print(root / "local-evidence-walkthrough-72s.mp4")
