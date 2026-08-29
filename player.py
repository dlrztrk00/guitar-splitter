"""The multitrack mixer: markup, and the script that drives it.

Gradio does not execute <script> inside an HTML block, so the whole player lives
in the page <head> and watches for its own markup to appear. Track data rides in
on a data- attribute.
"""

from __future__ import annotations

import html
import json

PLAYER_SCRIPT = r"""
<script>
(function () {
  const TICK_MS = 400;      // how often we check tracks for drift
  const DRIFT_S = 0.08;     // resync anything further off than this

  function fmt(t) {
    if (!isFinite(t)) t = 0;
    const m = Math.floor(t / 60), s = Math.floor(t % 60);
    return m + ':' + String(s).padStart(2, '0');
  }

  function drawWave(canvas, peaks, progress, colour, dim) {
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
      canvas.width = w * dpr; canvas.height = h * dpr;
    }
    const g = canvas.getContext('2d');
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);
    const n = peaks.length, mid = h / 2, step = w / n;
    for (let i = 0; i < n; i++) {
      const played = (i / n) <= progress;
      g.fillStyle = dim ? '#3a3330' : (played ? colour : '#4e4642');
      const amp = Math.max(1, peaks[i] * (h * 0.46));
      g.fillRect(i * step, mid - amp, Math.max(1, step - 0.5), amp * 2);
    }
  }

  function init(root) {
    if (root.dataset.ready) return;
    root.dataset.ready = '1';
    const data = JSON.parse(root.dataset.payload);
    const tracks = data.tracks.filter(t => t.used);
    if (!tracks.length) return;

    let ctx = null, playing = false, raf = null, timer = null;
    const state = {};

    // Wire each lane: gain node, mute/solo, fader, waveform.
    data.tracks.forEach(t => {
      const lane = root.querySelector('[data-key="' + t.key + '"]');
      if (!lane || !t.used) return;
      const audio = new Audio(t.preview);
      audio.preload = 'auto';
      state[t.key] = { audio, gain: null, vol: 1, muted: false, solo: false,
                       canvas: lane.querySelector('canvas'), peaks: t.peaks };

      lane.querySelector('.gs-mute').onclick = function () {
        state[t.key].muted = !state[t.key].muted;
        this.classList.toggle('on', state[t.key].muted);
        applyGains();
      };
      lane.querySelector('.gs-solo').onclick = function () {
        state[t.key].solo = !state[t.key].solo;
        this.classList.toggle('on', state[t.key].solo);
        applyGains();
      };
      const fader = lane.querySelector('.gs-fader');
      fader.oninput = function () {
        state[t.key].vol = this.value / 100;
        lane.querySelector('.gs-vol').textContent = this.value + '%';
        applyGains();
      };
      state[t.key].canvas.onclick = e => {
        const r = state[t.key].canvas.getBoundingClientRect();
        seek(((e.clientX - r.left) / r.width) * duration());
      };
    });

    const keys = Object.keys(state);
    const master = () => state[keys[0]].audio;
    const duration = () => data.duration || master().duration || 0;

    function applyGains() {
      const soloing = keys.some(k => state[k].solo);
      keys.forEach(k => {
        const s = state[k];
        const level = (s.muted || (soloing && !s.solo)) ? 0 : s.vol;
        if (s.gain) s.gain.gain.value = level;
        else s.audio.volume = Math.min(1, level);   // before Web Audio wakes up
      });
    }

    // Built on first play: browsers refuse to start an AudioContext without a
    // user gesture, and createMediaElementSource can only be called once.
    function ensureCtx() {
      if (ctx) return;
      ctx = new (window.AudioContext || window.webkitAudioContext)();
      keys.forEach(k => {
        const s = state[k];
        s.gain = ctx.createGain();
        ctx.createMediaElementSource(s.audio).connect(s.gain).connect(ctx.destination);
        s.audio.volume = 1;
      });
      applyGains();
    }

    function frame() {
      const t = master().currentTime, d = duration();
      root.querySelector('.gs-time').textContent = fmt(t) + ' / ' + fmt(d);
      root.querySelector('.gs-played').style.width = (d ? (t / d) * 100 : 0) + '%';
      keys.forEach(k => {
        const s = state[k];
        drawWave(s.canvas, s.peaks, d ? t / d : 0, '#e0813f',
                 s.muted || (keys.some(x => state[x].solo) && !s.solo));
      });
      if (playing) raf = requestAnimationFrame(frame);
    }

    function play() {
      ensureCtx();
      if (ctx.state === 'suspended') ctx.resume();
      const at = master().currentTime;
      keys.forEach(k => { state[k].audio.currentTime = at; });
      Promise.all(keys.map(k => state[k].audio.play())).catch(() => {});
      playing = true;
      root.querySelector('.gs-play').textContent = '❚❚';
      raf = requestAnimationFrame(frame);
      // Independent <audio> elements drift apart over minutes. Nudge them back.
      timer = setInterval(() => {
        const ref = master().currentTime;
        keys.slice(1).forEach(k => {
          if (Math.abs(state[k].audio.currentTime - ref) > DRIFT_S) {
            state[k].audio.currentTime = ref;
          }
        });
      }, TICK_MS);
    }

    function pause() {
      keys.forEach(k => state[k].audio.pause());
      playing = false;
      root.querySelector('.gs-play').textContent = '▶';
      cancelAnimationFrame(raf); clearInterval(timer);
      frame();
    }

    function seek(t) {
      t = Math.max(0, Math.min(duration(), t));
      keys.forEach(k => { state[k].audio.currentTime = t; });
      frame();
    }

    root.querySelector('.gs-play').onclick = () => (playing ? pause() : play());
    root.querySelector('.gs-bar').onclick = e => {
      const r = e.currentTarget.getBoundingClientRect();
      seek(((e.clientX - r.left) / r.width) * duration());
    };
    master().addEventListener('ended', pause);

    // Read by the "Download this mix" button, which sends it to the server.
    window.GS_state = () => JSON.stringify({
      session: data.session,
      gains: Object.fromEntries(keys.map(k => {
        const s = state[k], soloing = keys.some(x => state[x].solo);
        return [k, (s.muted || (soloing && !s.solo)) ? 0 : s.vol];
      })),
    });

    applyGains();
    frame();
    window.addEventListener('resize', () => { if (!playing) frame(); });
  }

  function scan() {
    document.querySelectorAll('#gs-player[data-payload]').forEach(init);
  }
  new MutationObserver(scan).observe(document.documentElement, {childList: true, subtree: true});
  document.addEventListener('DOMContentLoaded', scan);
  scan();
})();
</script>
<style>
  #gs-player { font: 14px/1.5 ui-sans-serif, -apple-system, "Segoe UI", sans-serif; color: #efe9e4; }
  #gs-player .gs-transport { display: flex; align-items: center; gap: 14px; margin-bottom: 16px; }
  #gs-player .gs-play { width: 46px; height: 46px; border-radius: 50%; border: 0; cursor: pointer;
    background: #e0813f; color: #1a0f07; font-size: 16px; flex: none; }
  #gs-player .gs-bar { flex: 1; height: 6px; border-radius: 3px; background: #342e2b; cursor: pointer; }
  #gs-player .gs-played { height: 100%; border-radius: 3px; background: #e0813f; width: 0; }
  #gs-player .gs-time { font-variant-numeric: tabular-nums; color: #a2968d; min-width: 96px; text-align: right; }
  #gs-player .gs-lane { display: flex; align-items: center; gap: 12px; padding: 9px 0;
    border-top: 1px solid #2f2a28; }
  #gs-player .gs-name { width: 74px; flex: none; font-weight: 600; }
  #gs-player .gs-btns { display: flex; gap: 5px; flex: none; }
  #gs-player .gs-btns button { width: 27px; height: 27px; border-radius: 7px; cursor: pointer;
    border: 1px solid #3f3936; background: transparent; color: #a2968d; font-size: 12px; font-weight: 700; }
  #gs-player .gs-mute.on { background: #c2503f; border-color: #c2503f; color: #fff; }
  #gs-player .gs-solo.on { background: #e0813f; border-color: #e0813f; color: #1a0f07; }
  #gs-player canvas { flex: 1; height: 46px; min-width: 90px; cursor: pointer; }
  #gs-player .gs-fader { width: 96px; flex: none; accent-color: #e0813f; }
  #gs-player .gs-vol { width: 42px; flex: none; text-align: right; color: #a2968d;
    font-variant-numeric: tabular-nums; font-size: 12px; }
  #gs-player .gs-unused { color: #6b615c; font-style: italic; flex: 1; }
  #gs-player a.gs-dl { color: #a2968d; text-decoration: none; font-size: 12px; flex: none;
    border: 1px solid #3f3936; border-radius: 7px; padding: 5px 9px; }
  #gs-player a.gs-dl:hover { color: #e0813f; border-color: #e0813f; }
</style>
"""


def build_html(session: str, tracks: list[dict], duration: float) -> str:
    """Markup for one song's mixer. Behaviour comes from PLAYER_SCRIPT."""
    payload = html.escape(json.dumps({"session": session, "duration": duration, "tracks": tracks}), quote=True)

    lanes = []
    for t in tracks:
        if not t["used"]:
            lanes.append(
                f'<div class="gs-lane" data-key="{t["key"]}">'
                f'<div class="gs-name" style="color:#6b615c">{html.escape(t["label"])}</div>'
                f'<div class="gs-unused">not played in this song</div></div>'
            )
            continue
        lanes.append(
            f'<div class="gs-lane" data-key="{t["key"]}">'
            f'<div class="gs-name">{html.escape(t["label"])}</div>'
            f'<div class="gs-btns">'
            f'<button class="gs-mute" title="Mute">M</button>'
            f'<button class="gs-solo" title="Solo">S</button></div>'
            f'<canvas></canvas>'
            f'<input class="gs-fader" type="range" min="0" max="100" value="100">'
            f'<span class="gs-vol">100%</span>'
            f'<a class="gs-dl" href="{t["download"]}" download>save</a>'
            f"</div>"
        )

    return (
        f'<div id="gs-player" data-payload="{payload}">'
        f'<div class="gs-transport">'
        f'<button class="gs-play">▶</button>'
        f'<div class="gs-bar"><div class="gs-played"></div></div>'
        f'<div class="gs-time">0:00 / 0:00</div>'
        f"</div>"
        + "".join(lanes)
        + "</div>"
    )
