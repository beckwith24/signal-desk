"""
Save a YouTube video's transcript, title, description and chapters to research/videos/<id>.md, so the
model notes can be checked against what the author says. Tries youtube-transcript-api first, then yt-dlp's
automatic subtitles.

    python video_transcript.py 2BKyuH7oARw        (Actions tab -> "Video transcript")
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

OUT = Path(__file__).with_name("research") / "videos"


def clock(s: float) -> str:
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def via_api(vid: str) -> list[tuple[float, str]]:
    from youtube_transcript_api import YouTubeTranscriptApi
    try:                                     # 1.x
        fetched = YouTubeTranscriptApi().fetch(vid, languages=["en", "en-US"])
        return [(s.start, s.text) for s in fetched]
    except AttributeError:                   # 0.x
        return [(s["start"], s["text"]) for s in YouTubeTranscriptApi.get_transcript(vid, languages=["en", "en-US"])]


def via_ytdlp(vid: str, tmp: Path) -> list[tuple[float, str]]:
    subprocess.run(["yt-dlp", "--skip-download", "--write-auto-subs", "--write-subs", "--sub-langs", "en.*",
                    "--sub-format", "vtt", "-o", str(tmp / "v"), f"https://www.youtube.com/watch?v={vid}"],
                   check=False, capture_output=True, text=True, timeout=300)
    files = sorted(tmp.glob("v*.vtt"))
    if not files:
        return []
    rows, last = [], None
    for block in files[0].read_text(errors="ignore").split("\n\n"):
        m = re.search(r"(\d+):(\d+):(\d+)\.\d+ -->", block)
        if not m:
            continue
        start = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
        text = " ".join(l for l in block.splitlines()[1:] if "-->" not in l)
        text = re.sub(r"<[^>]+>", "", text).strip()
        if text and text != last:
            rows.append((start, text)); last = text
    return rows


def info(vid: str) -> dict:
    r = subprocess.run(["yt-dlp", "--skip-download", "--dump-json", f"https://www.youtube.com/watch?v={vid}"],
                       capture_output=True, text=True, timeout=300)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"error": (r.stderr or "")[-400:]}


def main(vid: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    meta = info(vid)
    rows, how, err = [], "", ""
    try:
        rows, how = via_api(vid), "youtube-transcript-api"
    except Exception as e:
        err = f"youtube-transcript-api: {type(e).__name__}: {str(e)[:300]}"
    if not rows:
        with tempfile.TemporaryDirectory() as d:
            rows, how = via_ytdlp(vid, Path(d)), "yt-dlp automatic subtitles"
    L = [f"# {meta.get('title', vid)}", "",
         f"Channel: {meta.get('channel') or meta.get('uploader', '?')} · uploaded {meta.get('upload_date', '?')} · "
         f"{clock(meta.get('duration') or 0)} · https://youtu.be/{vid}", ""]
    if meta.get("error"):
        L += [f"(video details unavailable: {meta['error']})", ""]
    if meta.get("description"):
        L += ["## Description", "", meta["description"], ""]
    if meta.get("chapters"):
        L += ["## Chapters", ""] + [f"- {clock(c['start_time'])} {c['title']}" for c in meta["chapters"]] + [""]
    L += [f"## Transcript ({how if rows else 'not available'})", ""]
    if not rows and err:
        L.append(err)
    para, t0 = [], None
    for start, text in rows:                 # one paragraph per ~30 seconds, with its start time
        if t0 is None:
            t0 = start
        para.append(text.replace("\n", " "))
        if start - t0 >= 30:
            L.append(f"[{clock(t0)}] " + " ".join(para)); para, t0 = [], None
    if para:
        L.append(f"[{clock(t0)}] " + " ".join(para))
    (OUT / f"{vid}.md").write_text("\n\n".join(L[:8]) + "\n\n" + "\n\n".join(L[8:]) + "\n")
    print(f"{vid}: {len(rows)} transcript lines via {how or 'none'}; title: {meta.get('title')}")


if __name__ == "__main__":
    for v in sys.argv[1:]:
        main(v)
