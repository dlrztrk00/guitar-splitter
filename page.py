"""The page: a cassette you drop a song onto, then the mixer.

The look is lifted from a red translucent tape on black — cream label strips,
marker lettering, a green price sticker. Fonts are ones macOS already ships, so
the app never reaches the network to render itself.
"""

from __future__ import annotations

from player import PLAYER_SCRIPT

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GuitarSplit</title>
<style>
 :root{
   --black:#080807; --panel:#141110; --line:rgba(239,231,216,.10);
   --red:#c9241c; --red-lit:#e8352b; --red-deep:#7a1410;
   --cream:#efe7d8; --dim:#9c8d84; --green:#6fd44f;
   --display:"Futura","Avenir Next Condensed","Helvetica Neue",Impact,sans-serif;
   --hand:"Marker Felt","Bradley Hand","Segoe Script",cursive;
   --mono:ui-monospace,SFMono-Regular,Menlo,monospace;
   --body:ui-sans-serif,-apple-system,"Segoe UI",sans-serif;
 }
 *{box-sizing:border-box}
 body{margin:0;background:var(--black);color:var(--cream);font:15px/1.6 var(--body);
   -webkit-font-smoothing:antialiased}
 .wrap{max-width:880px;margin:0 auto;padding:46px 20px 90px}

 /* ── the cassette ─────────────────────────────────────────────── */
 .tape{position:relative;border-radius:12px;padding:14px;margin-bottom:30px;
   background:linear-gradient(#26211f,#171312);
   border:1px solid rgba(239,231,216,.16);
   box-shadow:0 26px 60px rgba(0,0,0,.85), inset 0 1px 0 rgba(255,255,255,.14)}
 .shell{position:relative;border-radius:7px;padding:20px 22px 16px;
   background:
     radial-gradient(120% 80% at 30% 0%, rgba(255,255,255,.18), transparent 60%),
     linear-gradient(#b81f18, #7c1410 62%, #5d0f0c);
   box-shadow:inset 0 0 40px rgba(0,0,0,.5), inset 0 1px 0 rgba(255,255,255,.3)}
 .screw{position:absolute;width:9px;height:9px;border-radius:50%;
   background:radial-gradient(#3a0d0a,#180402);box-shadow:inset 0 1px 1px rgba(255,255,255,.25)}
 .screw.tl{top:9px;left:10px} .screw.tr{top:9px;right:10px}
 .screw.bl{bottom:9px;left:10px} .screw.br{bottom:9px;right:10px}

 .strip{position:relative;background:linear-gradient(#fdfaf3,#e8e0d0);
   color:#171310;border-radius:2px;padding:12px 16px;
   box-shadow:0 2px 5px rgba(0,0,0,.4)}
 .strip.top{min-height:62px;display:flex;align-items:center;justify-content:center}
 .brandline{font:700 34px/1 var(--display);letter-spacing:.16em;text-transform:uppercase;
   white-space:nowrap}
 .scrawl{position:absolute;left:0;right:0;top:50%;transform:translateY(-58%) rotate(-4deg);
   text-align:center;font:26px/1 var(--hand);color:#c9241c;pointer-events:none;
   opacity:.92;padding:0 20px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

 .reels{display:flex;align-items:center;gap:20px;padding:24px 6px 20px;justify-content:center}
 .reel{width:96px;height:96px;border-radius:50%;flex:none;position:relative;
   background:radial-gradient(circle at 34% 30%, rgba(255,255,255,.28), transparent 45%),
     conic-gradient(#8d1a14 0 8%, #5f0f0c 0 20%, #8d1a14 0 28%, #5f0f0c 0 40%,
                    #8d1a14 0 48%, #5f0f0c 0 60%, #8d1a14 0 68%, #5f0f0c 0 80%,
                    #8d1a14 0 88%, #5f0f0c 0 100%);
   box-shadow:inset 0 0 0 5px rgba(0,0,0,.32), 0 3px 10px rgba(0,0,0,.55);
   animation:spin 3.4s linear infinite;animation-play-state:paused}
 body.gs-playing .reel{animation-play-state:running}
 .reel::after{content:"";position:absolute;inset:31px;border-radius:50%;
   background:radial-gradient(#2a2523,#0d0b0a);box-shadow:inset 0 0 0 3px #efe7d8}
 @keyframes spin{to{transform:rotate(360deg)}}
 .window{flex:1;max-width:190px;height:58px;border-radius:5px;
   background:linear-gradient(#3a0c09,#1d0503);
   box-shadow:inset 0 2px 9px rgba(0,0,0,.85), 0 1px 0 rgba(255,255,255,.14)}

 .strip.foot{display:flex;align-items:center;gap:14px;padding:9px 14px;font:13px/1 var(--body)}
 .side{font:700 15px/1 var(--display);letter-spacing:.1em;border-right:1px solid #cabfae;
   padding-right:12px}
 .foot-brand{margin-left:auto;font:600 15px/1 var(--display);letter-spacing:.06em}
 .foot-brand b{font-weight:800;letter-spacing:.12em}

 .sticker{position:absolute;right:-9px;bottom:52px;background:var(--green);color:#10240a;
   font:800 15px/1 var(--display);letter-spacing:.06em;padding:9px 13px;transform:rotate(-6deg);
   box-shadow:0 4px 10px rgba(0,0,0,.55);border-radius:2px;white-space:nowrap}

 /* ── everything else ──────────────────────────────────────────── */
 .card{background:var(--panel);border:1px solid var(--line);border-radius:10px;
   padding:22px;margin-bottom:18px}
 h2{font:700 15px/1 var(--display);letter-spacing:.14em;text-transform:uppercase;margin:0 0 14px}
 .drop{border:1.5px dashed rgba(239,231,216,.22);border-radius:8px;padding:46px 20px;
   text-align:center;color:var(--dim);cursor:pointer;transition:.15s}
 .drop:hover,.drop.over{border-color:var(--red-lit);color:var(--cream);background:#1b1614}
 .drop b{display:block;font:700 20px/1.2 var(--display);letter-spacing:.1em;
   text-transform:uppercase;color:var(--cream);margin-bottom:7px}
 button{background:var(--red);color:var(--cream);border:0;border-radius:5px;padding:12px 20px;
   font:700 13px/1 var(--display);letter-spacing:.1em;text-transform:uppercase;cursor:pointer}
 button:hover:not(:disabled){background:var(--red-lit)}
 button:disabled{opacity:.4;cursor:default}
 button.tag{background:var(--green);color:#10240a;transform:rotate(-2deg)}
 button.tag:hover:not(:disabled){background:#82e661}
 button.ghost{background:transparent;color:var(--dim);border:1px solid rgba(239,231,216,.22)}
 button.ghost:hover:not(:disabled){color:var(--cream);border-color:var(--cream);background:transparent}
 .row{display:flex;gap:14px;align-items:center;flex-wrap:wrap}
 .muted{color:var(--dim);font-size:13px}
 .err{color:#ff7a6b}
 .barwrap{height:7px;background:#2a1512;border-radius:4px;overflow:hidden;margin:16px 0 8px}
 .barfill{height:100%;background:var(--red-lit);width:0;transition:width .4s linear}
 .chip{display:inline-block;background:#241a18;border:1px solid rgba(239,231,216,.16);
   border-radius:3px;padding:5px 11px;margin:4px 5px 0 0;
   font:700 11px/1 var(--display);letter-spacing:.1em;text-transform:uppercase}
 .chip.off{color:#6a4b46;border-style:dashed;font-weight:400;font-style:italic;
   text-transform:none;letter-spacing:.02em;font-family:var(--body);font-size:12px}
 .hint{font:12px/1.7 var(--body);color:#6a5b54;margin-top:8px}
 kbd{background:#241a18;border:1px solid rgba(239,231,216,.18);border-radius:3px;
   padding:1px 6px;font:11px/1 var(--mono);color:var(--cream)}
</style>
__PLAYER__
</head><body><div class="wrap">

<div class="tape">
  <div class="shell">
    <span class="screw tl"></span><span class="screw tr"></span>
    <span class="screw bl"></span><span class="screw br"></span>

    <div class="strip top">
      <span class="brandline">Guitar&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Split</span>
      <span class="scrawl" id="scrawl">side A</span>
    </div>

    <div class="reels">
      <div class="reel"></div>
      <div class="window"></div>
      <div class="reel"></div>
    </div>

    <div class="strip foot">
      <span class="side">A</span>
      <span class="muted" id="footinfo" style="color:#5c534a">drop a song to begin</span>
      <span class="foot-brand">Stem <b>SPLITTER</b></span>
    </div>

    <div class="sticker" id="sticker">6 TRACKS</div>
  </div>
</div>

<div class="card" id="pick">
  <div class="drop" id="drop">
    <b>Drop a song here</b>
    or click to choose one · mp3, wav, m4a, flac
  </div>
  <input type="file" id="file" accept="audio/*,.mp3,.wav,.m4a,.flac,.aif,.aiff" hidden>
  <p class="hint">Everything happens on this computer. Nothing is uploaded anywhere.</p>
</div>

<div class="card" id="progress" hidden>
  <div class="row" style="justify-content:space-between">
    <h2 style="margin:0" id="ptitle"></h2><span class="muted" id="pstage"></span>
  </div>
  <div class="barwrap"><div class="barfill" id="pbar"></div></div>
  <div class="muted" id="ptime"></div>
</div>

<div id="found"></div>
<div id="mixer"></div>

<div class="card" id="save" hidden>
  <h2>Take it with you</h2>
  <div class="row">
    <button id="dlall" class="tag">Download all instruments</button>
    <span class="muted">A folder with every instrument as its own file.</span>
  </div>
  <div class="row" style="margin-top:14px">
    <button id="dlmix" class="ghost">Download this mix</button>
    <span class="muted">One file of exactly what you are hearing now.</span>
  </div>
  <p class="hint">Or use <b>save</b> on any single lane above. Everything here is
  lossless 24-bit FLAC — including what you are hearing.</p>
  <div class="muted" id="dlnote" style="margin-top:10px"></div>
</div>

</div><script>
const $ = s => document.querySelector(s);
let jobId=null, poll=null, result=null;

$('#drop').onclick = () => $('#file').click();
$('#drop').ondragover = e => { e.preventDefault(); $('#drop').classList.add('over'); };
$('#drop').ondragleave = () => $('#drop').classList.remove('over');
$('#drop').ondrop = e => { e.preventDefault(); $('#drop').classList.remove('over');
  if (e.dataTransfer.files[0]) start(e.dataTransfer.files[0]); };
$('#file').onchange = e => { if (e.target.files[0]) start(e.target.files[0]); };

function scrawl(text){ $('#scrawl').textContent = text; }

async function start(file){
  $('#found').innerHTML=''; $('#mixer').innerHTML=''; $('#save').hidden=true;
  document.body.classList.remove('gs-playing');
  const name = file.name.replace(/\\.[^.]+$/,'');
  scrawl(name);
  $('#sticker').textContent = 'LOADING';
  $('#footinfo').textContent = 'reading…';
  $('#progress').hidden=false; $('#ptitle').textContent=name;
  $('#pstage').textContent='Uploading'; $('#pbar').style.width='2%';
  const res = await fetch('/api/jobs', {method:'PUT',
    headers:{'X-Filename':encodeURIComponent(file.name)}, body:file});
  const job = await res.json();
  if (job.error){ fail(job.error); return; }
  jobId = job.id;
  poll = setInterval(tick, 1000); tick();
}

function fail(msg){
  clearInterval(poll);
  $('#sticker').textContent = 'FAILED';
  $('#pstage').innerHTML = '<span class="err">failed</span>';
  $('#ptime').innerHTML = '<span class="err">'+msg+'</span>';
}

async function tick(){
  const job = await (await fetch('/api/jobs/'+jobId)).json();
  $('#pstage').textContent = job.stage;
  $('#footinfo').textContent = job.stage.toLowerCase();
  // Separation runs at a steady fraction of realtime, so once the song length
  // is known the elapsed time gives an honest estimate.
  const est = Math.max(20, (job.duration||120) * 0.85 + 25);
  if (job.state==='running'){
    $('#pbar').style.width = (Math.min(0.97, job.elapsed/est)*100).toFixed(0)+'%';
    const left = Math.max(0, Math.round(est - job.elapsed));
    $('#ptime').textContent = Math.round(job.elapsed)+'s elapsed'
      + (job.duration ? ' · about '+left+'s left' : '');
  }
  if (job.state==='error'){ fail(job.error); return; }
  if (job.state==='done'){
    clearInterval(poll);
    $('#pbar').style.width='100%';
    $('#ptime').textContent = 'Done in '+Math.round(job.elapsed)+'s';
    $('#pstage').textContent='';
    show(job.result);
  }
}

function show(r){
  result = r;
  scrawl(r.song);
  $('#sticker').textContent = r.played.length + (r.played.length===1?' TRACK':' TRACKS');
  $('#footinfo').textContent = r.duration_str + ' · ' + r.samplerate + ' Hz';
  let h = '<div class="card"><h2>What is in this song</h2><div>';
  r.played.forEach(n => h += '<span class="chip">'+n+'</span>');
  r.absent.forEach(n => h += '<span class="chip off">no '+n.toLowerCase()+'</span>');
  h += '</div></div>';
  $('#found').innerHTML = h;
  $('#mixer').innerHTML = '<div class="card"><h2>Mix</h2>'+r.html
    + '<p class="hint">Click anywhere on a waveform to play from there. '
    + '<kbd>space</kbd> play · <kbd>←</kbd> <kbd>→</kbd> skip 5s · <kbd>home</kbd> start</p></div>';
  $('#save').hidden = false;
  $('#dlnote').textContent = '';
}

function saveAs(url){
  const a = document.createElement('a'); a.href = url; a.download='';
  document.body.appendChild(a); a.click(); a.remove();
}

$('#dlall').onclick = async () => {
  if (!result) return;
  $('#dlall').disabled = true; $('#dlnote').textContent = 'Packing…';
  const res = await fetch('/api/zip', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({session: result.session, song: result.song})});
  const out = await res.json();
  $('#dlall').disabled = false;
  if (out.error){ $('#dlnote').innerHTML = '<span class="err">'+out.error+'</span>'; return; }
  $('#dlnote').textContent = 'Saved. Unzip it for a folder of '+result.played.length+' instruments.';
  saveAs(out.url);
};

$('#dlmix').onclick = async () => {
  if (!result) return;
  const state = window.GS_state ? JSON.parse(window.GS_state()) : null;
  if (!state){ $('#dlnote').textContent='Play something first.'; return; }
  $('#dlmix').disabled = true; $('#dlnote').textContent = 'Rendering…';
  const res = await fetch('/api/mix', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({session: result.session, song: result.song, gains: state.gains})});
  const out = await res.json();
  $('#dlmix').disabled = false;
  if (out.error){ $('#dlnote').innerHTML = '<span class="err">'+out.error+'</span>'; return; }
  $('#dlnote').textContent = 'Saved to your Downloads folder.';
  saveAs(out.url);
};
</script></body></html>
""".replace("__PLAYER__", PLAYER_SCRIPT)
