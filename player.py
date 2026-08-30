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
  const TICK_MS = 500;      // drift check interval
  const DRIFT_S = 0.08;     // resync anything further off than this
  const NUDGE_S = 5;        // arrow-key jump

  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

  function fmt(t) {
    if (!isFinite(t)) t = 0;
    const m = Math.floor(t / 60), s = Math.floor(t % 60);
    return m + ':' + String(s).padStart(2, '0');
  }

  function drawWave(canvas, peaks, progress, dim) {
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
      g.fillStyle = dim ? '#3b2320' : (played ? '#e8352b' : '#5c2f2a');
      const amp = Math.max(1, peaks[i] * (h * 0.46));
      g.fillRect(i * step, mid - amp, Math.max(1, step - 0.5), amp * 2);
    }
    g.fillStyle = '#efe7d8';
    g.fillRect(clamp(progress * w, 0, w - 1.5), 0, 1.5, h);
  }

  function init(root) {
    if (root.dataset.ready) return;
    root.dataset.ready = '1';
    const data = JSON.parse(root.dataset.payload);
    if (!data.tracks.some(t => t.used)) return;

    let ctx = null, playing = false, raf = null, timer = null;
    let ghost = null;   // where the pointer is during a drag, as a 0..1 fraction
    const state = {};

    data.tracks.forEach(t => {
      const lane = root.querySelector('[data-key="' + t.key + '"]');
      if (!lane || !t.used) return;
      const audio = new Audio(t.preview);
      audio.preload = 'auto';
      state[t.key] = { audio, gain: null, vol: 1, muted: false, solo: false,
                       canvas: lane.querySelector('canvas'), peaks: t.peaks };

      // Gain changes must never move the playhead.
      lane.querySelector('.gs-mute').onclick = function (e) {
        e.preventDefault();
        state[t.key].muted = !state[t.key].muted;
        this.classList.toggle('on', state[t.key].muted);
        applyGains(); draw();
      };
      lane.querySelector('.gs-solo').onclick = function (e) {
        e.preventDefault();
        state[t.key].solo = !state[t.key].solo;
        this.classList.toggle('on', state[t.key].solo);
        applyGains(); draw();
      };
      const fader = lane.querySelector('.gs-fader');
      fader.oninput = function () {
        state[t.key].vol = this.value / 100;
        lane.querySelector('.gs-vol').textContent = this.value + '%';
        applyGains();
      };
      scrub(state[t.key].canvas);
    });

    const keys = Object.keys(state);
    const master = () => state[keys[0]].audio;
    const duration = () => data.duration || master().duration || 0;

    // --- moving around -----------------------------------------------------
    // Click a spot and it plays from there. Dragging only moves a marker; the
    // audio is moved once, on release. Seeking five media elements on every
    // mouse-move makes them stall instead of playing, which is exactly the
    // "stuck where I clicked" behaviour this replaces.
    function scrub(el) {
      const frac = e => {
        const r = el.getBoundingClientRect();
        return clamp((e.clientX - r.left) / r.width, 0, 1);
      };
      el.addEventListener('pointerdown', e => {
        e.preventDefault();
        ghost = frac(e);
        draw();
        const move = ev => { ghost = frac(ev); draw(); };
        // Listening on the document, not the element, so releasing the mouse
        // anywhere still ends the drag. A drag that never ends is a player
        // that never plays.
        const up = ev => {
          document.removeEventListener('pointermove', move);
          document.removeEventListener('pointerup', up);
          const target = (ghost === null ? frac(ev) : ghost) * duration();
          ghost = null;
          seek(target);
          if (!playing) play(); else draw();
        };
        document.addEventListener('pointermove', move);
        document.addEventListener('pointerup', up);
      });
    }

    function seek(t) {
      t = clamp(t, 0, Math.max(0, duration() - 0.05));
      keys.forEach(k => { try { state[k].audio.currentTime = t; } catch (err) {} });
      draw();
    }

    function applyGains() {
      const soloing = keys.some(k => state[k].solo);
      keys.forEach(k => {
        const s = state[k];
        const level = (s.muted || (soloing && !s.solo)) ? 0 : s.vol;
        if (s.gain) s.gain.gain.value = level;
        else s.audio.volume = Math.min(1, level);
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

    // draw() paints one frame. tick() is the only thing that schedules more,
    // so there is never a second animation loop running against the first.
    function draw() {
      const t = master().currentTime, d = duration();
      const pos = ghost === null ? (d ? t / d : 0) : ghost;
      root.querySelector('.gs-time').textContent =
        fmt(ghost === null ? t : ghost * d) + ' / ' + fmt(d);
      root.querySelector('.gs-played').style.width = (pos * 100) + '%';
      const soloing = keys.some(x => state[x].solo);
      keys.forEach(k => {
        const s = state[k];
        drawWave(s.canvas, s.peaks, pos, s.muted || (soloing && !s.solo));
      });
    }

    function tick() {
      draw();
      if (playing) raf = requestAnimationFrame(tick);
    }

    function play() {
      if (playing) return;
      ensureCtx();
      if (ctx.state === 'suspended') ctx.resume();
      const at = master().currentTime >= duration() - 0.1 ? 0 : master().currentTime;
      keys.forEach(k => { try { state[k].audio.currentTime = at; } catch (err) {} });
      Promise.all(keys.map(k => state[k].audio.play())).catch(() => {});
      playing = true;
      document.body.classList.add('gs-playing');
      root.querySelector('.gs-play').textContent = '❚❚';
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(tick);
      clearInterval(timer);
      // Independent <audio> elements drift apart over minutes. Nudge them back,
      // but never while the user is dragging.
      timer = setInterval(() => {
        if (!playing || ghost !== null) return;
        const ref = master().currentTime;
        keys.slice(1).forEach(k => {
          if (Math.abs(state[k].audio.currentTime - ref) > DRIFT_S) {
            state[k].audio.currentTime = ref;
          }
        });
      }, TICK_MS);
    }

    function pause() {
      if (!playing) return;
      keys.forEach(k => state[k].audio.pause());
      playing = false;
      document.body.classList.remove('gs-playing');
      root.querySelector('.gs-play').textContent = '▶';
      cancelAnimationFrame(raf); clearInterval(timer);
      draw();
    }

    const toggle = () => (playing ? pause() : play());
    root.querySelector('.gs-play').onclick = toggle;
    scrub(root.querySelector('.gs-bar'));
    master().addEventListener('ended', pause);

    // Keyboard, so you can keep your hands on the guitar.
    document.addEventListener('keydown', e => {
      if (!document.body.contains(root)) return;
      const tag = (e.target.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'button') return;
      if (e.code === 'Space') { e.preventDefault(); toggle(); }
      else if (e.code === 'ArrowLeft') { e.preventDefault(); seek(master().currentTime - NUDGE_S); }
      else if (e.code === 'ArrowRight') { e.preventDefault(); seek(master().currentTime + NUDGE_S); }
      else if (e.code === 'Home') { e.preventDefault(); seek(0); }
    });

    window.GS_state = () => JSON.stringify({
      session: data.session,
      gains: Object.fromEntries(keys.map(k => {
        const s = state[k], soloing = keys.some(x => state[x].solo);
        return [k, (s.muted || (soloing && !s.solo)) ? 0 : s.vol];
      })),
    });

    applyGains();
    draw();
    // The first draw can land before the browser has laid the canvases out, at
    // which point they measure zero and nothing is painted. Draw again after
    // layout, and again whenever a canvas actually changes size.
    requestAnimationFrame(draw);
    if (window.ResizeObserver) {
      const ro = new ResizeObserver(() => { if (!playing) draw(); });
      keys.forEach(k => ro.observe(state[k].canvas));
    }
    window.addEventListener('resize', () => { if (!playing) draw(); });
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
  #gs-player { font: 14px/1.5 var(--body); color: var(--cream); }
  #gs-player .gs-transport { display: flex; align-items: center; gap: 16px; margin-bottom: 14px; }
  #gs-player .gs-play { width: 50px; height: 50px; border-radius: 50%; border: 0; cursor: pointer;
    background: var(--red); color: var(--cream); font-size: 16px; flex: none;
    box-shadow: 0 0 0 4px rgba(232,53,43,.14), inset 0 2px 6px rgba(255,255,255,.28);
    transition: transform .1s; }
  #gs-player .gs-play:active { transform: scale(.94); }
  #gs-player .gs-bar { flex: 1; height: 20px; display: flex; align-items: center; cursor: pointer;
    touch-action: none; }
  #gs-player .gs-bartrack { width: 100%; height: 7px; border-radius: 4px; background: #2a1512;
    pointer-events: none; box-shadow: inset 0 1px 3px rgba(0,0,0,.7); }
  #gs-player .gs-played { height: 100%; border-radius: 4px; background: var(--red-lit); width: 0; }
  #gs-player .gs-time { font: 13px/1 var(--mono); letter-spacing: .04em;
    color: var(--dim); min-width: 104px; text-align: right; }

  #gs-player .gs-lane { display: flex; align-items: center; gap: 12px; padding: 10px 0;
    border-top: 1px solid rgba(239,231,216,.09); }
  #gs-player .gs-name { width: 86px; flex: none; font: 600 15px/1 var(--display);
    letter-spacing: .09em; text-transform: uppercase; }
  #gs-player .gs-btns { display: flex; gap: 5px; flex: none; }
  #gs-player .gs-btns button { width: 28px; height: 28px; border-radius: 4px; cursor: pointer;
    border: 1px solid rgba(239,231,216,.22); background: transparent; color: var(--dim);
    font: 700 11px/1 var(--display); letter-spacing: .06em; }
  #gs-player .gs-btns button:hover { border-color: var(--cream); color: var(--cream); }
  #gs-player .gs-mute.on { background: var(--red); border-color: var(--red); color: #fff; }
  #gs-player .gs-solo.on { background: var(--green); border-color: var(--green); color: #10240a; }
  #gs-player canvas { flex: 1; height: 48px; min-width: 90px; cursor: pointer; touch-action: none; }
  #gs-player .gs-fader { width: 92px; flex: none; accent-color: var(--red-lit); }
  #gs-player .gs-vol { width: 44px; flex: none; text-align: right; color: var(--dim);
    font: 12px/1 var(--mono); }
  #gs-player .gs-unused { color: #6a4b46; font-style: italic; flex: 1; }
  #gs-player a.gs-dl { color: var(--dim); text-decoration: none; flex: none;
    font: 700 10px/1 var(--display); letter-spacing: .1em; text-transform: uppercase;
    border: 1px solid rgba(239,231,216,.22); border-radius: 4px; padding: 7px 10px; }
  #gs-player a.gs-dl:hover { color: var(--cream); border-color: var(--cream); }
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
            f'<a class="gs-dl" href="{t["stem"]}.flac" data-stem="{t["stem"]}" '
            f'data-filename="{html.escape(t["filename"], quote=True)}" download>save</a>'
            f"</div>"
        )

    return (
        f'<div id="gs-player" data-payload="{payload}">'
        f'<div class="gs-transport">'
        f'<button class="gs-play" title="Play / pause (space)">▶</button>'
        f'<div class="gs-bar"><div class="gs-bartrack"><div class="gs-played"></div></div></div>'
        f'<div class="gs-time">0:00 / 0:00</div>'
        f"</div>"
        + "".join(lanes)
        + "</div>"
    )
