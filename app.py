"""GuitarSplit — upload a song, get every instrument, download what you want.

Runs on your own machine. Nothing is uploaded anywhere.

The server is Python's own http.server on purpose: a job queue with five
endpoints does not justify a web framework, and every dependency avoided is
disk space and one less thing to break.
"""

from __future__ import annotations

import json
import mimetypes
import shutil
import tempfile
import threading
import time
import traceback
import urllib.parse
import uuid
import zipfile
import webbrowser
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import audio as A
from page import PAGE
from player import build_html

WORK = Path(tempfile.gettempdir()) / "guitarsplit"
MAX_UPLOAD = 400 * 1024 * 1024


@dataclass
class Job:
    id: str
    title: str
    state: str = "running"     # running | done | error
    stage: str = "Starting"
    started: float = field(default_factory=time.monotonic)
    duration: float = 0.0      # song length, so the page can estimate
    result: dict | None = None
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "id": self.id, "title": self.title, "state": self.state,
            "stage": self.stage, "elapsed": round(time.monotonic() - self.started, 1),
            "duration": self.duration, "result": self.result, "error": self.error,
        }


class Jobs:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def start(self, source: Path, title: str) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], title=title)
        with self._lock:
            self._jobs[job.id] = job
        threading.Thread(target=self._work, args=(job, source), daemon=True).start()
        return job

    def _work(self, job: Job, source: Path) -> None:
        try:
            job.stage = "Reading the file"
            original, info = A.load(source)
            job.duration = info.duration

            job.stage = f"Separating {info.duration_str} of audio"
            stems, elapsed = A.separate(original, info.samplerate)

            job.stage = "Building tracks"
            out = WORK / job.id
            (out / "tracks").mkdir(parents=True, exist_ok=True)
            A.save_lossless(out / "original", original, info.samplerate)

            song = A.safe_name(job.title)
            tracks = []
            for key in A.TRACK_ORDER:
                if key not in stems:
                    continue
                stem, label = stems[key], A.TRACK_LABELS[key]
                used = A.is_used(stem)
                entry = {"key": key, "label": label, "used": used,
                         "peaks": A.peaks(stem) if used else [],
                         "preview": "", "stem": "", "filename": ""}
                if used:
                    job.stage = f"Building {label}"
                    A.save_lossless(out / "tracks" / key, stem, info.samplerate)
                    # Same file for playing and for saving: 24-bit lossless.
                    # Serving compressed previews only makes sense when
                    # bandwidth costs something, and here it is a local disk.
                    entry["preview"] = f"/media/{job.id}/tracks/{key}.flac"
                    entry["stem"] = f"/media/{job.id}/tracks/{key}"
                    entry["filename"] = f"{song} - {label}"
                tracks.append(entry)

            # Keep the stems so a custom mix can be rendered without separating
            # again. numpy's own format, no extra dependency.
            import numpy as np

            np.savez(out / "stems.npz", samplerate=np.int32(info.samplerate), **stems)

            job.result = {
                "html": build_html(job.id, tracks, info.duration),
                "session": job.id,
                "song": song,
                "tracks": tracks,
                "duration": info.duration,
                "samplerate": info.samplerate,
                "channels": info.channels,
                "duration_str": info.duration_str,
                "elapsed": round(elapsed),
                "played": [t["label"] for t in tracks if t["used"]],
                "absent": [t["label"] for t in tracks if not t["used"]],
            }
            job.state = "done"
            job.stage = "Done"
        except Exception as exc:  # noqa: BLE001 — the page should see any failure
            job.state = "error"
            job.error = f"{type(exc).__name__}: {exc}"
            job.stage = "Failed"
            traceback.print_exc()


def render_mix(session: str, gains: dict[str, float], fmt: str = "flac") -> tuple[Path, str]:
    """Render the current fader positions to a lossless file."""
    import numpy as np

    out = WORK / session
    npz = out / "stems.npz"
    if not npz.exists():
        raise FileNotFoundError("That song is no longer loaded. Split it again.")

    data = np.load(npz)
    samplerate = int(data["samplerate"])
    stems = {k: data[k] for k in data.files if k != "samplerate"}
    original, _ = A.load(out / "original.flac")

    mix = A.render_mix(original, stems, gains)

    # Name it after what was removed, so it still means something in a Downloads
    # folder six months from now.
    silenced = [A.TRACK_LABELS.get(k, k).lower() for k, g in sorted(gains.items()) if g < 0.01]
    if silenced:
        label = "no " + " and no ".join(silenced)
    elif all(g > 0.99 for g in gains.values()):
        label = "original"
    else:
        label = "custom mix"
    base = out / f"mix-{abs(hash((label, fmt))) % 10**6}"
    path = A.save_mp3(base, mix, samplerate) if fmt == "mp3" else A.save_lossless(base, mix, samplerate)
    return path, f"{label}.{fmt}"


def zip_tracks(session: str, song: str, fmt: str = "flac") -> Path:
    """Every instrument as its own file, in one folder.

    Stored rather than deflated: FLAC is already compressed, so squeezing it
    again just burns CPU for nothing. Each entry is inside a folder named after
    the song, so unzipping gives a folder rather than loose files.
    """
    out = WORK / session
    tracks = sorted((out / "tracks").glob("*.flac"))
    if not tracks:
        raise FileNotFoundError("That song is no longer loaded. Split it again.")

    path = out / f"stems-{fmt}.zip"
    # Stored rather than deflated either way: both formats are already
    # compressed, so squeezing them again just burns CPU for nothing.
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as z:
        for f in tracks:
            label = A.TRACK_LABELS.get(f.stem, f.stem.title())
            member = f
            if fmt == "mp3":
                member = f.with_suffix(".mp3")
                if not member.is_file():
                    A.transcode(f, member)
            z.write(member, arcname=f"{song}/{label}.{fmt}")
    return path


class Handler(BaseHTTPRequestHandler):
    jobs: Jobs = None  # type: ignore[assignment]
    server_version = "GuitarSplit"

    def log_message(self, *args):  # quieter console
        pass

    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        self._send(code, json.dumps(payload).encode(), "application/json")

    # --- routes ------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        elif parsed.path.startswith("/api/jobs/"):
            job = self.jobs.get(parsed.path.split("/")[3])
            self._json(200, job.as_dict()) if job else self._json(404, {"error": "no such job"})
        elif parsed.path.startswith("/media/"):
            self._media(parsed)
        else:
            self._json(404, {"error": "not found"})

    def _media(self, parsed) -> None:
        parts = [urllib.parse.unquote(p) for p in parsed.path.split("/")[2:] if p]
        target = WORK.joinpath(*parts).resolve()
        # Never serve outside the working directory, whatever the URL claims.
        if WORK.resolve() not in target.parents:
            self._json(404, {"error": "not found"})
            return

        # An .mp3 that does not exist yet is made from the .flac beside it, once,
        # and cached. Nothing is encoded unless someone actually asks for it.
        if not target.is_file() and target.suffix == ".mp3":
            source = target.with_suffix(".flac")
            if source.is_file():
                try:
                    A.transcode(source, target)
                except A.AudioError:
                    self._json(500, {"error": "could not convert to mp3"})
                    return
        if not target.is_file():
            self._json(404, {"error": "not found"})
            return

        size = target.stat().st_size
        start, end, status = 0, size - 1, 200

        # Byte ranges are what make an <audio> element seekable. Without them a
        # browser can only play from the beginning, which is exactly how this
        # looked: click anywhere in the song, nothing moves.
        header = self.headers.get("Range", "")
        if header.startswith("bytes="):
            spec = header[6:].split(",")[0].strip()
            first, _, last = spec.partition("-")
            try:
                if first:
                    start = int(first)
                    end = int(last) if last else size - 1
                elif last:
                    start = size - int(last)   # suffix range: the final N bytes
            except ValueError:
                start, end = 0, size - 1
            start = max(0, min(start, size - 1))
            end = max(start, min(end, size - 1))
            status = 206

        with target.open("rb") as fh:
            fh.seek(start)
            body = fh.read(end - start + 1)

        extra = {"Accept-Ranges": "bytes"}
        if status == 206:
            extra["Content-Range"] = f"bytes {start}-{end}/{size}"
        # ?name= turns a link into a download with a proper filename.
        wanted = urllib.parse.parse_qs(parsed.query).get("name", [None])[0]
        if wanted:
            extra["Content-Disposition"] = f'attachment; filename="{wanted.replace(chr(34), "")}"'
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self._send(status, body, ctype, extra)

    def do_PUT(self) -> None:  # noqa: N802 — file upload
        if urllib.parse.urlparse(self.path).path != "/api/jobs":
            self._json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", 0))
        if not 0 < length <= MAX_UPLOAD:
            self._json(400, {"error": f"file must be under {MAX_UPLOAD // 1048576} MB"})
            return

        filename = urllib.parse.unquote(self.headers.get("X-Filename", "song.wav"))
        stem, suffix = Path(filename).stem, Path(filename).suffix or ".wav"
        dest = WORK / "uploads" / f"{uuid.uuid4().hex[:8]}{suffix}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as fh:
            remaining = length
            while remaining > 0:
                chunk = self.rfile.read(min(1 << 20, remaining))
                if not chunk:
                    break
                fh.write(chunk)
                remaining -= len(chunk)
        self._json(200, self.jobs.start(dest, stem).as_dict())

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")

        if parsed.path == "/api/zip":
            song = A.safe_name(body.get("song") or "GuitarSplit")
            fmt = "mp3" if body.get("fmt") == "mp3" else "flac"
            try:
                path = zip_tracks(body.get("session", ""), song, fmt)
            except FileNotFoundError as exc:
                self._json(404, {"error": str(exc)})
                return
            except Exception as exc:  # noqa: BLE001
                self._json(500, {"error": f"{type(exc).__name__}: {exc}"})
                return
            rel = path.relative_to(WORK).as_posix()
            label = f"{song} - stems ({fmt}).zip"
            self._json(200, {"url": f"/media/{rel}?name={urllib.parse.quote(label)}"})
            return

        if parsed.path == "/api/mix":
            try:
                path, name = render_mix(body.get("session", ""), body.get("gains") or {},
                                        "mp3" if body.get("fmt") == "mp3" else "flac")
            except FileNotFoundError as exc:
                self._json(404, {"error": str(exc)})
                return
            except Exception as exc:  # noqa: BLE001
                self._json(500, {"error": f"{type(exc).__name__}: {exc}"})
                return
            rel = path.relative_to(WORK).as_posix()
            song = body.get("song", "GuitarSplit")
            self._json(200, {"url": f"/media/{rel}?name={urllib.parse.quote(f'{song} - {name}')}"})
            return

        self._json(404, {"error": "not found"})


def serve(host: str = "127.0.0.1", port: int = 8756, open_browser: bool = True) -> None:
    # Start clean: leftovers from a previous run are just disk.
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True, exist_ok=True)

    Handler.jobs = Jobs()
    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}"
    print(f"GuitarSplit → {url}")
    print("Close this window to stop.")
    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        shutil.rmtree(WORK, ignore_errors=True)


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(prog="guitarsplit")
    p.add_argument("--port", type=int, default=8756)
    p.add_argument("--no-browser", action="store_true")
    a = p.parse_args()
    serve(port=a.port, open_browser=not a.no_browser)
