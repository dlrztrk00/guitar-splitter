"""Audio I/O, separation, and mixing.

Everything that touches sound lives here; app.py is only the interface.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

MODEL_NAME = "htdemucs_6s"

# Display order for the mixer — the instruments a guitarist looks for first.
# `other` is the model's leftover bucket: synths, strings, brass end up there.
TRACK_ORDER = ["guitar", "vocals", "drums", "bass", "piano", "other"]
TRACK_LABELS = {
    "guitar": "Guitar",
    "vocals": "Vocals",
    "drums": "Drums",
    "bass": "Bass",
    "piano": "Piano",
    "other": "Other",
}

# Seconds of audio per chunk. htdemucs was trained on ~7.8s segments and throws
# a shape error on anything longer, so this is a ceiling, not a preference.
SEGMENT = 7.0
# Chunk overlap. Demucs' own default, and the more accurate setting: 0.10 is
# about 20% faster but moves the guitar track by roughly 30 dB below the mix.
# Accuracy wins here — the whole point is what the guitar track sounds like.
OVERLAP = 0.25

class AudioError(RuntimeError):
    pass


# An app launched from Finder does not inherit your shell's PATH — it gets a
# bare one without /usr/local/bin, so Homebrew's ffmpeg is invisible and every
# run dies on "No such file or directory: 'ffprobe'". Resolving the binaries
# ourselves makes the app behave the same however it was started.
_TOOL_DIRS = ("/usr/local/bin", "/opt/homebrew/bin", "/usr/bin", "/bin")
_tools: dict[str, str] = {}


def tool(name: str) -> str:
    """Absolute path to ffmpeg or ffprobe, however this process was launched."""
    if name in _tools:
        return _tools[name]
    import shutil

    found = shutil.which(name)
    if not found:
        for directory in _TOOL_DIRS:
            candidate = Path(directory) / name
            if candidate.is_file():
                found = str(candidate)
                break
    if not found:
        raise AudioError(
            f"{name} is not installed. Open Terminal and run:  brew install ffmpeg"
        )
    _tools[name] = found
    return found


def safe_name(text: str) -> str:
    """A song title that survives being a filename."""
    import re

    cleaned = re.sub(r"[^\w\s.-]", "", text).strip()
    return re.sub(r"\s+", " ", cleaned)[:100] or "song"


@dataclass
class Info:
    samplerate: int
    channels: int
    duration: float

    @property
    def duration_str(self) -> str:
        m, s = divmod(int(round(self.duration)), 60)
        return f"{m}:{s:02d}"


def probe(path: str | Path) -> Info:
    out = subprocess.run(
        [tool("ffprobe"), "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=sample_rate,channels",
         "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        raise AudioError(f"Could not read that file.\n{out.stderr.strip()[:500]}")
    data = json.loads(out.stdout)
    if not data.get("streams"):
        raise AudioError("That file has no audio in it.")
    st = data["streams"][0]
    return Info(
        samplerate=int(st["sample_rate"]),
        channels=int(st["channels"]),
        duration=float(data.get("format", {}).get("duration") or 0.0),
    )


def load(path: str | Path) -> tuple[np.ndarray, Info]:
    """Decode to float32 (channels, samples) at the file's own sample rate."""
    info = probe(path)
    proc = subprocess.run(
        [tool("ffmpeg"), "-v", "error", "-i", str(path), "-f", "f32le",
         "-acodec", "pcm_f32le", "-ac", str(info.channels),
         "-ar", str(info.samplerate), "-"],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise AudioError(f"Could not decode that file.\n{proc.stderr.decode(errors='replace')[:500]}")
    audio = np.frombuffer(proc.stdout, dtype="<f4")
    if audio.size == 0:
        raise AudioError("That file decoded to zero samples.")
    return audio.reshape(-1, info.channels).T.copy(), info


def _encode(path: Path, audio: np.ndarray, samplerate: int, args: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim == 1:
        audio = audio[None, :]
    proc = subprocess.run(
        [tool("ffmpeg"), "-y", "-v", "error", "-f", "f32le", "-ar", str(samplerate),
         "-ac", str(audio.shape[0]), "-i", "-", *args, str(path)],
        input=np.ascontiguousarray(audio.T).tobytes(), capture_output=True,
    )
    if proc.returncode != 0:
        raise AudioError(f"ffmpeg failed writing {path.name}:\n{proc.stderr.decode(errors='replace')[:500]}")
    return path


def save_lossless(path: Path, audio: np.ndarray, samplerate: int) -> Path:
    """24-bit FLAC — what downloads are."""
    return _encode(path.with_suffix(".flac"), audio, samplerate, ["-c:a", "flac", "-sample_fmt", "s32"])


def peaks(audio: np.ndarray, buckets: int = 900) -> list[float]:
    """Per-bucket peak amplitude, for drawing the waveform."""
    mono = np.abs(audio.mean(axis=0) if audio.ndim > 1 else audio)
    if mono.size == 0:
        return [0.0] * buckets
    pad = (-mono.size) % buckets
    if pad:
        mono = np.pad(mono, (0, pad))
    grid = mono.reshape(buckets, -1).max(axis=1)
    top = float(grid.max())
    if top > 0:
        grid = grid / top
    return [round(float(v), 4) for v in grid]


def is_used(audio: np.ndarray, floor_db: float = -50.0, min_ratio: float = 0.02) -> bool:
    """Whether an instrument is actually played, rather than separator noise.

    An unused stem is never digital silence — it holds low-level bleed. Calling
    that a piano would be a lie, so it has to clear an absolute floor and be
    audible for a real stretch of the song.
    """
    mono = audio.mean(axis=0) if audio.ndim > 1 else audio
    if mono.size == 0:
        return False
    peak = float(np.abs(mono).max())
    if peak <= 0 or 20 * np.log10(peak) < floor_db:
        return False
    win = max(1, mono.size // 400)
    frames = mono[: (mono.size // win) * win].reshape(-1, win)
    rms = np.sqrt(np.maximum((frames.astype(np.float64) ** 2).mean(axis=1), 1e-20))
    loud = 20 * np.log10(rms) > max(20 * np.log10(peak) - 35, floor_db)
    return bool(loud.mean() >= min_ratio)


def separate(audio: np.ndarray, samplerate: int, progress=None) -> tuple[dict[str, np.ndarray], float]:
    """Split into six named stems at the source's own sample rate."""
    import time

    import torch
    import torchaudio
    from demucs.apply import apply_model
    from demucs.pretrained import get_model

    model = get_model(MODEL_NAME)
    model.cpu().eval()
    if "guitar" not in model.sources:
        raise AudioError(f"{MODEL_NAME} has no guitar track — wrong model.")

    wav = torch.from_numpy(np.ascontiguousarray(audio, dtype=np.float32))
    if wav.shape[0] == 1 and model.audio_channels == 2:
        wav = wav.repeat(2, 1)
    elif wav.shape[0] > model.audio_channels:
        wav = wav[: model.audio_channels]
    if samplerate != model.samplerate:
        wav = torchaudio.functional.resample(wav, samplerate, model.samplerate)

    # Demucs expects loudness-normalised input. Undoing it on the way out is
    # what makes the tracks add back up to the original, which the subtraction
    # in render_mix depends on.
    ref = wav.mean(0)
    mean, std = ref.mean(), ref.std()

    try:
        model.segment = SEGMENT
    except (AttributeError, ValueError):
        pass

    started = time.monotonic()
    with torch.no_grad():
        out = apply_model(
            model, ((wav - mean) / (std + 1e-8))[None],
            device="cpu", shifts=0, split=True, overlap=OVERLAP,
            progress=False, num_workers=0, segment=SEGMENT,
        )[0]
    elapsed = time.monotonic() - started
    out = out * std + mean

    n = audio.shape[1]
    stems: dict[str, np.ndarray] = {}
    for i, name in enumerate(model.sources):
        x = out[i]
        if model.samplerate != samplerate:
            x = torchaudio.functional.resample(x, model.samplerate, samplerate)
        if audio.shape[0] == 1 and x.shape[0] == 2:
            x = x.mean(0, keepdim=True)
        elif audio.shape[0] == 2 and x.shape[0] == 1:
            x = x.repeat(2, 1)
        arr = x.numpy().astype(np.float32, copy=False)
        # Realign to the source length so subtraction is sample-exact.
        if arr.shape[1] < n:
            arr = np.pad(arr, ((0, 0), (0, n - arr.shape[1])))
        stems[name] = arr[:, :n]
    return stems, elapsed


def render_mix(original: np.ndarray, stems: dict[str, np.ndarray], gains: dict[str, float]) -> np.ndarray:
    """Build a mix at the given fader positions.

        mix = original - Σ (1 - gain_i) * stem_i

    Not the same as summing the tracks you kept. The six stems do not add back
    up to the record exactly; summing discards that difference, subtracting
    keeps it. With every fader at 1.0 this returns the original untouched.
    """
    mix = original.astype(np.float32, copy=True)
    for name, stem in stems.items():
        reduction = 1.0 - float(gains.get(name, 1.0))
        if abs(reduction) > 1e-6:
            mix -= reduction * stem
    peak = float(np.abs(mix).max()) if mix.size else 0.0
    if peak > 1.0:
        # Subtraction can push past full scale. Pull back to -0.1 dBFS.
        mix *= (10 ** (-0.1 / 20)) / peak
    return mix
