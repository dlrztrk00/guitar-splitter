<img src="docs/icon.png" width="88" align="right" alt="">

# GuitarSplit

Split a song into its instruments, **mute the guitar, and play it yourself.**

A stem separator for guitarists, built for **Intel Macs** — where Logic Pro's own
Stem Splitter does not run, because Apple ships it only for Apple Silicon.

Everything happens on your own machine. No account, no upload, no service.

---

## What you get

Drop in a song — or paste a YouTube link and it fetches the audio itself — and
you get a mixer, one lane per instrument:

```
▶  1:12 / 3:01  ━━━━━━━●────────────────

Guitar   [M][S]  ▁▃▅▇▅▃▂▁▂▃▅▇▅▃▁   ──────●──  100%   save
Vocals   [M][S]  ▁▂▃▅▃▂▁▁▂▃▅▃▂▁▁   ──────●──  100%   save
Drums    [M][S]  ▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇   ──────●──  100%   save
Bass     [M][S]  ▃▃▄▃▃▄▃▃▄▃▃▄▃▃▄   ──────●──  100%   save
Piano            not played in this song
Other    [M][S]  ▁▁▂▃▂▁▁▂▃▂▁▁▂▃▂   ──────●──  100%   save
```

- **Mute the guitar and play over the rest**, or solo it to work the part out by ear.
- **Click anywhere on a waveform** to play from there.
- Instruments that aren't in the song are **labelled as absent**, rather than
  handed to you as a silent file to wonder about.
- **Download** any single instrument, all of them as a folder, or the exact mix
  you've dialled in — as lossless FLAC or 320 kbps MP3.

Playback in the page is always lossless, whatever format you choose to download.

## Why the backing track sounds like the record

This is the one idea in the project worth reading about.

A mix here is **not** built by adding up the instruments you kept. It's built by
**subtracting the ones you turned down from the original master**:

```
mix = original − Σ (1 − faderᵢ) × trackᵢ
```

Those look equivalent. They are not. A separation model does not reconstruct a
song perfectly — the separated tracks don't quite add back up to the record.
Summing them throws that difference away; subtracting keeps it, so everything
you didn't touch stays exactly as it was mastered, reverb tails and all.

Measured on a real track: the residue the model can't account for sits about
**23 dB below the mix**, and roughly **three quarters of it is midrange** —
200–2000 Hz, precisely where a mix goes thin and phasey when you gut it.

The property this buys you is checkable: **set every fader to 100% and the file
you get back is bit-for-bit identical to your original.** Zero sample error.

## Install

Requires [Homebrew](https://brew.sh).

```bash
git clone https://github.com/dlrztrk00/guitar-splitter.git
cd guitar-splitter
./setup.sh          # installs ffmpeg, Python 3.11 and the model — about 800 MB
./make_app.sh       # puts GuitarSplit in /Applications
```

Then double-click **GuitarSplit**. It starts the app and opens your browser.

### Why Python 3.11 specifically

Not a preference — a wall. **PyTorch's last macOS x86_64 build is 2.2.2**, which
supports Python ≤ 3.12. A plain `pip install demucs` on an Intel Mac fails,
because pip resolves to a newer torch that has no Intel wheel. `numba` and
`llvmlite` have since dropped Intel builds too, and try to compile LLVM from
source, which also fails. The pins in `requirements.txt` are the point of that
file; don't "upgrade" them.

Of the ~800 MB, **585 MB is PyTorch itself.** That's the price of running a
neural network on your own machine instead of sending your music to a server.
There is deliberately nothing else in it: no web framework — the server is
Python's own `http.server` — and no audio-analysis toolkit.

## How it works

1. **ffmpeg** decodes your file at its own sample rate. The original is never
   resampled.
2. **Demucs `htdemucs_6s`** separates it into six sources. It is the one widely
   available open model that emits **guitar** as its own track, which is the
   entire reason this project exists.
3. Each track is resampled back to the source rate and length-matched, so
   subtraction is sample-exact.
4. The mixer streams the lossless files directly, with HTTP range requests so
   you can seek anywhere in the song.

## Limits, honestly

- **A 3-minute song takes about 3 minutes** on a 2018 quad-core i5. It runs at
  roughly realtime on CPU; there is no GPU path on this hardware.
- **Separation is not magic.** Guitar-forward recordings come out clean; dense
  mixes leak between tracks, and a heavily processed guitar can end up partly in
  `other`.
- **Results are temporary.** Working files live in a temp folder and are deleted
  when you quit, so nothing accumulates on disk. Download what you want before
  closing.
- **YouTube changes its player regularly** and `yt-dlp` needs updating when it
  does. The app tells you when that has happened; the fix is
  `./venv/bin/pip install -U yt-dlp`. Downloading from YouTube is also against
  their terms of service — that's the situation, not an endorsement.

## Layout

| File | |
|---|---|
| `app.py` | local server, job queue, downloads |
| `audio.py` | decoding, separation, mixing |
| `player.py` | the mixer — markup and behaviour |
| `page.py` | the page around it |
| `fetch.py` | pulling audio from a link |
| `icon.py` | draws the app icon |

## Note

Separating music you own, to practise along with, is ordinary personal use.
Publishing separated stems is a different thing.
