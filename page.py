"""The page: upload, progress, then the mixer."""

from __future__ import annotations

from player import PLAYER_SCRIPT

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GuitarSplit</title>
__PLAYER__
<style>
 :root{--bg:#12100f;--panel:#1b1817;--line:#2f2a28;--ink:#efe9e4;--dim:#a2968d;--hot:#e0813f}
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--ink);
   font:15px/1.55 ui-sans-serif,-apple-system,"Segoe UI",sans-serif}
 .wrap{max-width:900px;margin:0 auto;padding:44px 20px 80px}
 h1{font-size:23px;margin:0 0 6px;letter-spacing:-.01em}
 .sub{color:var(--dim);margin:0 0 28px;font-size:14px}
 .card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:22px;margin-bottom:18px}
 .drop{border:1.5px dashed var(--line);border-radius:12px;padding:44px 20px;text-align:center;
   color:var(--dim);cursor:pointer;transition:.15s}
 .drop:hover,.drop.over{border-color:var(--hot);color:var(--ink);background:#1f1b19}
 .drop strong{color:var(--ink);display:block;font-size:16px;margin-bottom:5px}
 button{background:var(--hot);color:#1a0f07;border:0;border-radius:9px;padding:11px 20px;
   font:600 14px/1 inherit;cursor:pointer}
 button:disabled{opacity:.4;cursor:default}
 button.ghost{background:transparent;color:var(--dim);border:1px solid var(--line)}
 button.ghost:hover:not(:disabled){color:var(--hot);border-color:var(--hot)}
 .row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
 .muted{color:var(--dim);font-size:13px}
 .err{color:#e06c5f}
 .barwrap{height:6px;background:#342e2b;border-radius:3px;overflow:hidden;margin:14px 0 8px}
 .barfill{height:100%;background:var(--hot);width:0;transition:width .4s linear}
 .chip{display:inline-block;background:#241f1e;border:1px solid var(--line);border-radius:999px;
   padding:4px 12px;margin:4px 5px 0 0;font-size:13px}
 .chip.off{color:#6b615c;font-style:italic}
</style></head><body><div class="wrap">

<h1>🎸 GuitarSplit</h1>
<p class="sub">Upload a song. Get every instrument as its own track — mute the guitar and play it yourself.
Everything happens on this computer; nothing is uploaded anywhere.</p>

<div class="card" id="pick">
  <div class="drop" id="drop">
    <strong>Drop a song here</strong>
    or click to choose one · mp3, wav, m4a, flac
  </div>
  <input type="file" id="file" accept="audio/*,.mp3,.wav,.m4a,.flac,.aif,.aiff" hidden>
</div>

<div class="card" id="progress" hidden>
  <div class="row" style="justify-content:space-between">
    <strong id="ptitle"></strong><span class="muted" id="pstage"></span>
  </div>
  <div class="barwrap"><div class="barfill" id="pbar"></div></div>
  <div class="muted" id="ptime"></div>
</div>

<div id="found"></div>
<div id="mixer"></div>

<div class="card" id="save" hidden>
  <div class="row" style="justify-content:space-between">
    <div>
      <strong>Download</strong>
      <div class="muted" style="margin-top:4px">Each track has its own <em>save</em> button above.
      This one saves exactly what you are hearing right now.</div>
    </div>
    <button id="dlmix">Download this mix</button>
  </div>
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

async function start(file){
  $('#found').innerHTML=''; $('#mixer').innerHTML=''; $('#save').hidden=true;
  $('#progress').hidden=false; $('#ptitle').textContent=file.name;
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
  $('#pstage').innerHTML = '<span class="err">failed</span>';
  $('#ptime').innerHTML = '<span class="err">'+msg+'</span>';
}

async function tick(){
  const job = await (await fetch('/api/jobs/'+jobId)).json();
  $('#pstage').textContent = job.stage;
  // Separation runs at a steady fraction of realtime, so once the song length
  // is known the elapsed time gives an honest estimate.
  const est = Math.max(20, (job.duration||120) * 0.85 + 25);
  const frac = Math.min(0.97, job.elapsed / est);
  if (job.state==='running'){
    $('#pbar').style.width = (frac*100).toFixed(0)+'%';
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
  let h = '<div class="card"><strong>Instruments in this song</strong><div style="margin-top:10px">';
  r.played.forEach(n => h += '<span class="chip">'+n+'</span>');
  r.absent.forEach(n => h += '<span class="chip off">'+n+' — not played</span>');
  h += '</div><div class="muted" style="margin-top:14px">'
     + r.samplerate+' Hz · '+r.channels+' ch · '+r.duration_str+'</div></div>';
  $('#found').innerHTML = h;
  $('#mixer').innerHTML = '<div class="card">'+r.html+'</div>';
  $('#save').hidden = false;
  $('#dlnote').textContent = '';
}

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
  const a = document.createElement('a'); a.href = out.url; a.download=''; document.body.appendChild(a);
  a.click(); a.remove();
};
</script></body></html>
""".replace("__PLAYER__", PLAYER_SCRIPT)
