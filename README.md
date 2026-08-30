# GuitarSplit

Upload a song, get every instrument as its own track, **mute the guitar and play
it yourself.** Like Logic's Stem Splitter — except it runs on an Intel Mac,
which Logic's version does not.

Everything happens on your own computer. Nothing is uploaded anywhere.

## What you see

Drop a song in and you get a mixer: one lane per instrument, with a waveform,
mute, solo, and a fader.

- **Guitar · Vocals · Drums · Bass · Piano · Other**
- Instruments that aren't played are labelled *not played in this song*, instead
  of handing you a silent file to wonder about.
- **`save`** on any lane downloads that instrument on its own.
- **Download this mix** saves exactly what you're hearing — guitar muted, or
  whatever balance you dialled in.

**Playback is always lossless** — the player streams the same 24-bit FLAC files
it separated, straight off your disk. There are no compressed previews.

Downloads are your choice: **FLAC** (lossless) or **MP3** at 320 kbps, which is
roughly a fifth the size. The MP3 is made the first time you ask for one and
then kept, so nothing is encoded that you never wanted. On a 3-minute song a
full set of stems is about 158 MB as FLAC and 36 MB as MP3.

## Setup (once)

```bash
./setup.sh
```

It installs ffmpeg and Python 3.11 through Homebrew, then the separation model.
**About 800 MB.** That's PyTorch and the model itself — it has to be on the
machine for the separation to happen here rather than on someone's server.
There's nothing else in it: no web framework, no plotting library, no audio
analysis toolkit.

Python 3.11 is not optional. PyTorch's **last Intel-Mac build is 2.2.2**, which
needs Python ≤ 3.12, so a plain `pip install demucs` fails on this machine.

## Use

```bash
./make_app.sh
```

Puts **GuitarSplit** in your Applications folder. Double-click it — that's the
whole interface. If it's already running it just reopens the tab instead of
starting a second copy.

`GuitarSplit.command` in this folder does the same thing without the icon.

## Why the backing track sounds like the record

A mix here is not built by adding up the tracks you left on. It's built by
**subtracting the ones you turned down from the original master**:

```
mix = original − Σ (1 − faderᵢ) × trackᵢ
```

Those look equivalent. They aren't. The separated tracks don't quite add back up
to the record — the model can't account for everything. Summing throws that
difference away; subtracting keeps it, so everything you didn't touch stays
exactly as it was mastered, reverb tails and all.

Measured on a real track: the leftover sits about 23 dB below the mix, and about
three quarters of it is midrange. That's the difference between a backing track
that sounds like the record and one that sounds thin.

With every fader at 100%, this returns the original bit-for-bit.

## Files

| | |
|---|---|
| `app.py` | the local server and job queue |
| `audio.py` | loading, separation, mixing |
| `player.py` | the mixer — markup and behaviour |
| `page.py` | the page around it |

Working files live in a temp folder and are deleted when you quit. Songs you
download go wherever your browser puts downloads.

## Note

Separating music you own for your own practice is ordinary personal use.
Publishing separated stems is a different thing.
