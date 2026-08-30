"""Pulling audio down from a link with yt-dlp."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import audio as A

URL_RE = re.compile(r"^https?://", re.IGNORECASE)
PROGRESS_RE = re.compile(r"\[download\]\s+([\d.]+)%")


def is_url(text: str) -> bool:
    return bool(URL_RE.match((text or "").strip()))


class FetchError(RuntimeError):
    pass


def fetch(url: str, dest_dir: Path, on_progress=None) -> Path:
    """Download the best available audio and return the file.

    Taken as the source's own codec with no re-encode: transcoding here would
    be a generation of loss before the separation has even started. ffmpeg
    decodes whatever comes back anyway.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    before = {p for p in dest_dir.iterdir()} if dest_dir.exists() else set()

    proc = subprocess.Popen(
        [sys.executable, "-m", "yt_dlp",
         "-f", "bestaudio/best",
         "--no-playlist",
         "--newline",                      # one progress line at a time
         "--no-part",
         "--restrict-filenames",
         "-o", str(dest_dir / "%(title).100B.%(ext)s"),
         "--print", "after_move:filepath",
         url],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        # yt-dlp calls ffmpeg itself, and an app launched from Finder has a
        # PATH that cannot find it.
        env={**_env(), "PATH": _path()},
    )
    printed: list[str] = []
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        match = PROGRESS_RE.search(line)
        if match and on_progress:
            on_progress(float(match.group(1)))
        elif not line.startswith("["):
            printed.append(line)
    proc.wait()
    stderr = proc.stderr.read()

    if proc.returncode != 0:
        raise FetchError(_explain(stderr))

    for candidate in reversed(printed):
        path = Path(candidate)
        if path.is_file():
            return path
    new = [p for p in dest_dir.iterdir() if p not in before and p.is_file()]
    if not new:
        raise FetchError("The download finished but produced no file.")
    return max(new, key=lambda p: p.stat().st_mtime)


def _env() -> dict:
    import os

    return dict(os.environ)


def _path() -> str:
    """A PATH that includes ffmpeg, wherever it turned out to be."""
    import os

    ffmpeg_dir = str(Path(A.tool("ffmpeg")).parent)
    return os.pathsep.join([ffmpeg_dir, os.environ.get("PATH", "/usr/bin:/bin")])


def _explain(stderr: str) -> str:
    """Turn yt-dlp's output into something worth reading."""
    text = stderr.strip()
    low = text.lower()
    if "sign in to confirm" in low or "bot" in low:
        return ("YouTube asked this download to prove it is not a bot. That usually "
                "passes on its own after a while.")
    if "private video" in low or "members-only" in low:
        return "That video is private or members-only, so it cannot be downloaded."
    if "video unavailable" in low or "not available" in low:
        return "That video is unavailable — check the link, or it may be region blocked."
    if "unsupported url" in low:
        return "That link is not one yt-dlp recognises."
    if "unable to extract" in low or "nsig" in low or "player" in low:
        return ("YouTube changed something and yt-dlp needs updating. In Terminal, in "
                "the guitar-splitter folder, run:  ./venv/bin/pip install -U yt-dlp")
    return "Download failed.\n" + text[-500:]
