"""
YouTube Downloader — Railway Hosted Version
============================================
Files are downloaded on the server, then sent to the user's browser.
"""

# gevent monkey-patch must be first — enables async SSE streaming on Railway
try:
    from gevent import monkey
    monkey.patch_all()
except ImportError:
    pass

import os, subprocess, threading, queue, json, uuid, glob
from flask import Flask, request, Response, send_file, jsonify

# ── Embedded HTML ─────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>YT Downloader</title>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet"/>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --brand:#5C3030;--brand-hover:#4a2626;--brand-light:#f9f2f2;
  --gray-50:#f9fafb;--gray-100:#f3f4f6;--gray-200:#e5e7eb;--gray-300:#d1d5db;
  --gray-400:#9ca3af;--gray-500:#6b7280;--gray-600:#4b5563;--gray-700:#374151;
  --gray-800:#1f2937;--gray-900:#111827;
  --green:#16a34a;--green-light:#f0fdf4;--green-border:#bbf7d0;
  --red-light:#fef2f2;--red-border:#fecaca;--red-text:#dc2626;
  --blue:#2563eb;--blue-light:#eff6ff;--blue-border:#bfdbfe;
  --shadow-flat:0 1px 3px rgba(0,0,0,0.02);
  --shadow-card:0 1px 3px rgba(0,0,0,0.04),0 1px 2px rgba(0,0,0,0.03);
  --font-ui:'Sora',sans-serif;--font-data:'Inter',sans-serif;
}
html,body{min-height:100vh;background:var(--gray-50);color:var(--gray-900);font-family:var(--font-ui);font-size:14px;-webkit-font-smoothing:antialiased}
.app{width:100%;max-width:680px;margin:0 auto;padding:24px 16px 80px}
.app-header{display:flex;align-items:center;gap:10px;margin-bottom:24px;padding-bottom:16px;border-bottom:1px solid var(--gray-200)}
.app-logo{width:32px;height:32px;background:var(--brand);border-radius:8px;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.app-logo svg{color:#fff}
.app-title{font-size:16px;font-weight:700;color:var(--gray-900);letter-spacing:-0.3px}
.app-sub{font-size:11px;color:var(--gray-400);font-family:var(--font-data);margin-top:1px}
.card{background:#fff;border:1px solid var(--gray-200);border-radius:10px;padding:16px;margin-bottom:12px;box-shadow:var(--shadow-card)}
.section-label{font-size:10px;font-weight:600;color:var(--gray-500);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:10px}
input[type=text]{width:100%;padding:9px 11px;background:#fff;border:1px solid var(--gray-200);border-radius:6px;font-size:13px;font-family:var(--font-data);color:var(--gray-900);outline:none;transition:border-color .15s,box-shadow .15s;line-height:1.4}
input[type=text]:focus{border-color:var(--brand);box-shadow:0 0 0 3px rgba(92,48,48,0.08)}
input[type=text]::placeholder{color:var(--gray-400)}
.url-list{display:flex;flex-direction:column;gap:8px;margin-bottom:10px}
.url-entry{background:var(--gray-50);border:1px solid var(--gray-200);border-radius:8px;padding:10px 12px}
.url-entry-top{display:flex;align-items:center;gap:6px;min-width:0}
.url-entry-top input{flex:1;background:#fff;min-width:0}
.remove-btn{width:28px;height:28px;background:#fff;border:1px solid var(--gray-200);border-radius:6px;color:var(--gray-400);cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .15s;flex-shrink:0}
.remove-btn:hover{border-color:var(--red-text);color:var(--red-text);background:var(--red-light)}
.ts-row{display:flex;gap:6px;align-items:center;margin-top:7px}
.ts-label{font-size:10px;font-weight:600;color:var(--gray-500);text-transform:uppercase;letter-spacing:0.06em;white-space:nowrap;font-family:var(--font-data)}
.ts-input{flex:1;padding:7px 9px;background:#fff;border:1px solid var(--gray-200);border-radius:6px;font-size:12px;font-family:var(--font-data);color:var(--gray-900);outline:none;transition:border-color .15s;min-width:0}
.ts-input:focus{border-color:var(--brand);box-shadow:0 0 0 3px rgba(92,48,48,0.08)}
.ts-input::placeholder{color:var(--gray-300)}
.ts-sep{color:var(--gray-300);font-size:12px;flex-shrink:0}
.add-url-btn{width:100%;padding:8px 12px;background:#fff;border:1px dashed var(--gray-300);border-radius:6px;color:var(--gray-500);font-size:12px;font-weight:500;cursor:pointer;transition:all .15s;display:flex;align-items:center;justify-content:center;gap:6px}
.add-url-btn:hover{border-color:var(--brand);color:var(--brand);background:var(--brand-light)}
.fmt-tabs{display:flex;gap:6px}
.fmt-tab{flex:1;padding:9px 10px;background:#fff;border:1px solid var(--gray-200);border-radius:6px;color:var(--gray-500);font-size:12px;font-weight:600;cursor:pointer;text-align:center;transition:all .15s;user-select:none;display:flex;align-items:center;justify-content:center;gap:6px}
.fmt-tab:hover{background:var(--gray-50);color:var(--gray-700);border-color:var(--gray-300)}
.fmt-tab.active{background:var(--brand);border-color:var(--brand);color:#fff}
.quality-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}
.q-btn{padding:8px 6px;background:#fff;border:1px solid var(--gray-200);border-radius:6px;color:var(--gray-500);font-size:11px;font-family:var(--font-data);cursor:pointer;text-align:center;transition:all .15s;user-select:none}
.q-btn:hover{color:var(--gray-700);border-color:var(--gray-300);background:var(--gray-50)}
.q-btn.active{border-color:var(--brand);background:var(--brand-light);color:var(--brand)}
.q-btn .qr{display:block;font-size:13px;font-weight:700;color:var(--gray-800);margin-bottom:1px;font-family:var(--font-data)}
.q-btn.active .qr{color:var(--brand)}
#dlBtn{width:100%;padding:11px 16px;background:var(--brand);border:none;border-radius:7px;color:#fff;font-family:var(--font-ui);font-size:13px;font-weight:600;cursor:pointer;transition:background .15s,transform .1s;margin-bottom:12px;display:flex;align-items:center;justify-content:center;gap:7px}
#dlBtn:hover{background:var(--brand-hover)}
#dlBtn:active{transform:scale(.99)}
#dlBtn:disabled{background:var(--gray-300);cursor:not-allowed;color:var(--gray-500)}
#queueSection{display:none}
#queueSection.show{display:block}
.queue-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.queue-label{font-size:10px;font-weight:600;color:var(--gray-500);text-transform:uppercase;letter-spacing:0.08em}
.clear-btn{font-size:11px;font-weight:500;color:var(--gray-400);background:none;border:1px solid var(--gray-200);border-radius:5px;padding:3px 9px;cursor:pointer;font-family:var(--font-ui);transition:all .15s}
.clear-btn:hover{color:var(--gray-700);border-color:var(--gray-300);background:var(--gray-50)}
.dl-item{background:#fff;border:1px solid var(--gray-200);border-radius:8px;overflow:hidden;margin-bottom:8px;transition:border-color .2s;box-shadow:var(--shadow-flat)}
.dl-item.active{border-color:#d4b5b5}
.dl-item.success{border-color:var(--green-border)}
.dl-item.failed{border-color:var(--red-border)}
.dl-item-top{display:flex;align-items:center;gap:10px;padding:11px 14px;min-width:0}
.dl-item-icon{width:30px;height:30px;border-radius:6px;background:var(--gray-100);display:flex;align-items:center;justify-content:center;flex-shrink:0}
.dl-item.active .dl-item-icon{background:var(--brand-light)}
.dl-item.success .dl-item-icon{background:var(--green-light)}
.dl-item.failed .dl-item-icon{background:var(--red-light)}
.dl-item-info{flex:1;min-width:0}
.dl-item-title{font-size:12px;font-weight:600;color:var(--gray-800);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.4}
.dl-item-meta{font-size:11px;color:var(--gray-400);font-family:var(--font-data);margin-top:1px;display:flex;align-items:center;gap:6px}
.dl-badge{font-size:10px;font-weight:600;font-family:var(--font-data);padding:2px 7px;border-radius:4px;white-space:nowrap;flex-shrink:0}
.badge-queue{background:var(--gray-100);color:var(--gray-500)}
.badge-active{background:var(--brand-light);color:var(--brand)}
.badge-done{background:var(--green-light);color:var(--green)}
.badge-failed{background:var(--red-light);color:var(--red-text)}
.badge-merge{background:var(--blue-light);color:var(--blue)}
.dl-item-prog{padding:0 14px 12px}
.dl-bar-track{height:3px;background:var(--gray-100);border-radius:99px;overflow:hidden;margin-bottom:8px}
.dl-bar-fill{height:100%;width:0%;border-radius:99px;background:var(--brand);transition:width .4s ease}
.dl-bar-fill.spin{width:30%!important;animation:barSpin 1.1s ease infinite}
.dl-bar-fill.done{background:var(--green);width:100%!important}
@keyframes barSpin{0%{transform:translateX(-110%)}100%{transform:translateX(450%)}}
.dl-stats-row{display:flex;gap:12px;flex-wrap:wrap}
.dl-stat{font-size:11px;font-family:var(--font-data);color:var(--gray-400);display:flex;align-items:center;gap:3px}
.dl-stat b{color:var(--gray-700);font-weight:600}
.dl-stat.spd b{color:var(--blue)}
.dl-stat.pct b{color:var(--brand)}
/* download file button */
.file-dl-btn{display:inline-flex;align-items:center;gap:6px;padding:6px 12px;background:var(--green-light);border:1px solid var(--green-border);border-radius:6px;color:var(--green);font-size:12px;font-weight:600;font-family:var(--font-ui);cursor:pointer;text-decoration:none;transition:all .15s}
.file-dl-btn:hover{background:#dcfce7}
.file-dl-primary{background:var(--brand)!important;border-color:var(--brand)!important;color:#fff!important}
.file-dl-primary:hover{background:var(--brand-hover)!important}
@media(max-width:480px){.quality-grid{grid-template-columns:repeat(2,1fr)}.app{padding:16px 12px 80px}}
</style>
</head>
<body>
<div class="app">
  <div class="app-header">
    <div class="app-logo">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
    </div>
    <div>
      <div class="app-title">YT Downloader</div>
      <div class="app-sub">Multi-download · Timestamp clip · MP4 / MP3</div>
    </div>
  </div>

  <div class="card">
    <div class="section-label">Video URLs <span id="urlCount" style="color:var(--brand)">1</span></div>
    <div class="url-list" id="urlList">
      <div class="url-entry" id="row-0">
        <div class="url-entry-top">
          <input type="text" placeholder="Paste YouTube URL…"/>
          <button class="remove-btn" onclick="removeRow('row-0')" title="Remove">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg>
          </button>
        </div>
        <div class="ts-row">
          <span class="ts-label">From</span>
          <input class="ts-input" type="text" placeholder="0:00"/>
          <svg class="ts-sep" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
          <span class="ts-label">To</span>
          <input class="ts-input" type="text" placeholder="end"/>
        </div>
      </div>
    </div>
    <button class="add-url-btn" onclick="addRow()">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>
      Add another URL
    </button>
  </div>

  <div class="card">
    <div class="section-label">Format</div>
    <div class="fmt-tabs">
      <div class="fmt-tab active" data-fmt="mp4" onclick="setFmt(this)">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M10 9l5 3-5 3V9z"/></svg>
        MP4 Video
      </div>
      <div class="fmt-tab" data-fmt="mp3" onclick="setFmt(this)">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>
        MP3 Audio
      </div>
    </div>
  </div>

  <div class="card" id="qualityCard">
    <div class="section-label">Quality</div>
    <div class="quality-grid">
      <div class="q-btn active" data-q="bestvideo+bestaudio/best"              onclick="setQ(this)"><span class="qr">Auto</span>best</div>
      <div class="q-btn"        data-q="bestvideo[height<=2160]+bestaudio/best" onclick="setQ(this)"><span class="qr">4K</span>2160p</div>
      <div class="q-btn"        data-q="bestvideo[height<=1080]+bestaudio/best" onclick="setQ(this)"><span class="qr">1080p</span>Full HD</div>
      <div class="q-btn"        data-q="bestvideo[height<=720]+bestaudio/best"  onclick="setQ(this)"><span class="qr">720p</span>HD</div>
      <div class="q-btn"        data-q="bestvideo[height<=480]+bestaudio/best"  onclick="setQ(this)"><span class="qr">480p</span>Medium</div>
      <div class="q-btn"        data-q="bestvideo[height<=144]+bestaudio/best"  onclick="setQ(this)"><span class="qr">144p</span>Smallest</div>
    </div>
  </div>

  <button id="dlBtn" onclick="startAll()">
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
    Download All
  </button>

  <div id="queueSection">
    <div class="queue-header">
      <div class="queue-label">Queue</div>
      <button class="clear-btn" onclick="clearDone()">Clear done</button>
    </div>
    <div id="queueList"></div>
  </div>
</div>

<script>
let fmt = "mp4", quality = "bestvideo+bestaudio/best", rowCount = 1;

function updateCount() {
  document.getElementById("urlCount").textContent = document.querySelectorAll(".url-entry").length;
}
function addRow() {
  const id = "row-" + rowCount++;
  const n  = document.querySelectorAll(".url-entry").length + 1;
  const div = document.createElement("div");
  div.className = "url-entry"; div.id = id;
  div.innerHTML = `
    <div class="url-entry-top">
      <input type="text" placeholder="Paste YouTube URL #${n}…"/>
      <button class="remove-btn" onclick="removeRow('${id}')">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg>
      </button>
    </div>
    <div class="ts-row">
      <span class="ts-label">From</span><input class="ts-input" type="text" placeholder="0:00"/>
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="color:var(--gray-300);flex-shrink:0"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
      <span class="ts-label">To</span><input class="ts-input" type="text" placeholder="end"/>
    </div>`;
  document.getElementById("urlList").appendChild(div);
  div.querySelector("input").focus();
  updateCount();
}
function removeRow(id) {
  const rows = document.querySelectorAll(".url-entry");
  if (rows.length <= 1) { rows[0].querySelector("input").value = ""; return; }
  document.getElementById(id)?.remove(); updateCount();
}
function setFmt(el) {
  document.querySelectorAll(".fmt-tab").forEach(t => t.classList.remove("active"));
  el.classList.add("active"); fmt = el.dataset.fmt;
  document.getElementById("qualityCard").style.display = fmt === "mp3" ? "none" : "block";
}
function setQ(el) {
  document.querySelectorAll(".q-btn").forEach(b => b.classList.remove("active"));
  el.classList.add("active"); quality = el.dataset.q;
}
function clearDone() {
  document.querySelectorAll(".dl-item.success,.dl-item.failed").forEach(el => el.remove());
  if (!document.querySelector(".dl-item")) document.getElementById("queueSection").classList.remove("show");
}

function iconSVG(type) {
  const icons = {
    video:`<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M10 9l5 3-5 3V9z"/></svg>`,
    audio:`<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>`,
    done:`<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--green)" stroke-width="2" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg>`,
    fail:`<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--red-text)" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`
  };
  return icons[type] || "";
}

function createItem(id, url, startTime, endTime) {
  const short = url.length > 52 ? url.slice(0,49)+"…" : url;
  const clip  = (startTime||endTime) ? `${startTime||"0:00"} → ${endTime||"end"}` : "";
  const div   = document.createElement("div");
  div.className = "dl-item"; div.id = "item-"+id;
  div.innerHTML = `
    <div class="dl-item-top">
      <div class="dl-item-icon" id="icon-${id}" style="color:var(--gray-400)">${iconSVG(fmt==="mp3"?"audio":"video")}</div>
      <div class="dl-item-info" style="min-width:0">
        <div class="dl-item-title" id="title-${id}">${short}</div>
        <div class="dl-item-meta">
          <span style="text-transform:uppercase">${fmt}</span>
          ${clip?`<span>·</span><span style="color:var(--brand)">✂ ${clip}</span>`:""}
        </div>
      </div>
      <div class="dl-badge badge-queue" id="badge-${id}">Queued</div>
    </div>
    <div class="dl-item-prog" id="prog-${id}">
      <div class="dl-bar-track"><div class="dl-bar-fill" id="bar-${id}"></div></div>
      <div class="dl-stats-row">
        <div class="dl-stat pct">Progress <b id="pct-${id}">—</b></div>
        <div class="dl-stat spd">Speed <b id="spd-${id}">—</b></div>
        <div class="dl-stat">ETA <b id="eta-${id}">—</b></div>
        <div class="dl-stat">Size <b id="sz-${id}">—</b></div>
      </div>
      <div id="file-${id}"></div>
    </div>`;
  document.getElementById("queueList").appendChild(div);
}

function setBadge(id, cls, text) {
  const b = document.getElementById("badge-"+id);
  b.className = "dl-badge "+cls; b.textContent = text;
}

const RE = /(\d+\.?\d*)%\s+of\s+([\d.]+\s*\S+)\s+at\s+([\d.]+\s*\S+\/s)\s+ETA\s+(\S+)/;

function downloadOne(id, url, startTime, endTime) {
  return new Promise(resolve => {
    const item = document.getElementById("item-"+id);
    item.classList.add("active");
    setBadge(id, "badge-active", "Downloading");
    document.getElementById("bar-"+id).className = "dl-bar-fill spin";
    document.getElementById("icon-"+id).style.color = "var(--brand)";

    const params = new URLSearchParams({ url, format: fmt, quality });
    if (startTime) params.append("start", startTime);
    if (endTime)   params.append("end",   endTime);
    const es = new EventSource(`/download?${params}`);

    es.onmessage = e => {
      const data = JSON.parse(e.data);
      if (data.type === "log") {
        const line = data.line;
        const tm = line.match(/Destination:.+[/\\](.+?)\.\w+$/);
        if (tm) document.getElementById("title-"+id).textContent = tm[1];
        const m = line.match(RE);
        if (m) {
          document.getElementById("bar-"+id).className = "dl-bar-fill";
          document.getElementById("bar-"+id).style.width = m[1]+"%";
          document.getElementById("pct-"+id).textContent = parseFloat(m[1]).toFixed(1)+"%";
          document.getElementById("spd-"+id).textContent = m[3];
          document.getElementById("eta-"+id).textContent = m[4];
          document.getElementById("sz-" +id).textContent = m[2];
        }
        if (line.includes("[Merger]")||line.includes("Merging")) {
          document.getElementById("bar-"+id).className = "dl-bar-fill spin";
          setBadge(id, "badge-merge", "Merging");
        }
      }
      if (data.type === "done") {
        es.close(); item.classList.remove("active");
        if (data.code === 0) {
          item.classList.add("success");
          document.getElementById("bar-"+id).className = "dl-bar-fill done";
          document.getElementById("pct-"+id).textContent = "100%";
          document.getElementById("spd-"+id).textContent = "Done";
          document.getElementById("eta-"+id).textContent = "—";
          document.getElementById("icon-"+id).innerHTML = iconSVG("done");
          document.getElementById("icon-"+id).style.color = "";
          setBadge(id, "badge-done", "Done");
          // ── Show save button ──
          if (data.file_id) {
            document.getElementById("file-"+id).innerHTML = `
              <a class="file-dl-btn file-dl-primary" href="/get-file/${data.file_id}" download>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                Save to device
              </a>`;
          }
        } else {
          item.classList.add("failed");
          document.getElementById("bar-"+id).style.cssText="width:100%;background:var(--red-text)";
          document.getElementById("icon-"+id).innerHTML = iconSVG("fail");
          setBadge(id, "badge-failed", "Failed");
        }
        resolve();
      }
      if (data.type === "error") {
        es.close(); item.classList.remove("active"); item.classList.add("failed");
        document.getElementById("icon-"+id).innerHTML = iconSVG("fail");
        document.getElementById("spd-"+id).textContent = data.message;
        setBadge(id, "badge-failed", "Error");
        resolve();
      }
    };
    es.onerror = () => {
      es.close(); item.classList.remove("active"); item.classList.add("failed");
      document.getElementById("icon-"+id).innerHTML = iconSVG("fail");
      setBadge(id, "badge-failed", "Error");
      resolve();
    };
  });
}

let dlQueue = [], isRunning = false;
function enqueue(url, startTime, endTime) {
  const id = "dl-"+Date.now()+"-"+Math.random().toString(36).slice(2,6);
  dlQueue.push({ id, url, startTime, endTime });
  document.getElementById("queueSection").classList.add("show");
  createItem(id, url, startTime, endTime);
  updateDlBtn(); processQueue();
}
function updateDlBtn() {
  const btn = document.getElementById("dlBtn");
  const w = dlQueue.length;
  btn.disabled = false;
  btn.innerHTML = isRunning
    ? `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>${w>0?"Add to Queue ("+w+" waiting)":"Add to Queue"}`
    : `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>Download All`;
}
async function processQueue() {
  if (isRunning||dlQueue.length===0) return;
  isRunning = true;
  while (dlQueue.length>0) {
    const {id,url,startTime,endTime} = dlQueue.shift();
    updateDlBtn();
    await downloadOne(id, url, startTime, endTime);
  }
  isRunning = false; updateDlBtn();
}
function startAll() {
  const rows = document.querySelectorAll(".url-entry");
  const items = [];
  rows.forEach(row => {
    const inputs = row.querySelectorAll("input");
    const url = inputs[0]?.value.trim();
    const start = inputs[1]?.value.trim()||"";
    const end   = inputs[2]?.value.trim()||"";
    if (url) items.push({url,start,end});
  });
  if (items.length===0) { document.querySelector(".url-entry input").focus(); return; }
  items.forEach(({url,start,end}) => enqueue(url,start,end));
  document.getElementById("urlList").innerHTML = `
    <div class="url-entry" id="row-0">
      <div class="url-entry-top">
        <input type="text" placeholder="Paste YouTube URL…"/>
        <button class="remove-btn" onclick="removeRow('row-0')">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg>
        </button>
      </div>
      <div class="ts-row">
        <span class="ts-label">From</span><input class="ts-input" type="text" placeholder="0:00"/>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="color:var(--gray-300);flex-shrink:0"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
        <span class="ts-label">To</span><input class="ts-input" type="text" placeholder="end"/>
      </div>
    </div>`;
  rowCount=1; updateCount();
}
</script>
</body>
</html>"""

# ── Flask ─────────────────────────────────────────────────────────────────────
app = Flask(__name__)
DOWNLOAD_DIR = "/tmp/ytdown"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Store filename by file_id so we can serve it
file_registry = {}

@app.route("/")
def index():
    return HTML

@app.route("/debug")
def debug():
    import shutil, subprocess as sp
    ffmpeg = shutil.which("ffmpeg") or "NOT FOUND"
    ytdlp  = shutil.which("yt-dlp") or "NOT FOUND"
    # test ffmpeg version
    try:
        ffver = sp.check_output([ffmpeg, "-version"], stderr=sp.STDOUT, text=True).split("\n")[0] if ffmpeg != "NOT FOUND" else "N/A"
    except:
        ffver = "ERROR running ffmpeg"
    return {
        "ffmpeg_path": ffmpeg,
        "ffmpeg_version": ffver,
        "ytdlp_path": ytdlp,
        "tmp_space": str(shutil.disk_usage("/tmp"))
    }

@app.route("/download")
def download():
    url     = request.args.get("url", "").strip()
    fmt     = request.args.get("format", "mp4")
    quality = request.args.get("quality", "bestvideo+bestaudio/best")
    start   = request.args.get("start", "").strip()
    end     = request.args.get("end",   "").strip()

    if not url:
        return ("No URL", 400)

    file_id  = str(uuid.uuid4())
    out_dir  = os.path.join(DOWNLOAD_DIR, file_id)
    os.makedirs(out_dir, exist_ok=True)

    def generate():
        q = queue.Queue()

        def run():
            # Find ffmpeg in nix store path on Railway
            import shutil
            ffmpeg_path = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
            cmd = ["yt-dlp", "--newline", "--progress", "--ffmpeg-location", ffmpeg_path]
            import re as _re
            if fmt == "mp3":
                cmd += ["-f", "bestaudio", "-x", "--audio-format", "mp3", "--audio-quality", "0"]
            else:
                # Extract height limit from quality selector if set
                h = _re.search(r'height<=(\d+)', quality)
                if h:
                    ht = h.group(1)
                    # Try pre-merged first, then merge with ffmpeg
                    fmt_selector = (
                        f"bestvideo[height<={ht}][ext=mp4]+bestaudio[ext=m4a]"
                        f"/bestvideo[height<={ht}]+bestaudio"
                        f"/best[height<={ht}][ext=mp4]"
                        f"/best[height<={ht}]"
                    )
                else:
                    # Auto — best available
                    fmt_selector = (
                        "bestvideo[ext=mp4]+bestaudio[ext=m4a]"
                        "/bestvideo+bestaudio"
                        "/best[ext=mp4]"
                        "/best"
                    )
                cmd += ["-f", fmt_selector, "--merge-output-format", "mp4",
                        "--postprocessor-args", "ffmpeg:-c:a aac -c:v copy"]
            if start or end:
                s = start if start else "0"
                e = end   if end   else "inf"
                cmd += ["--download-sections", f"*{s}-{e}", "--force-keyframes-at-cuts"]

            out_tpl = os.path.join(out_dir, "%(title)s.%(ext)s")
            cmd += ["-o", out_tpl, "--no-playlist", url]

            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True, bufsize=1)
                for line in proc.stdout:
                    q.put(line)
                proc.wait()
                q.put(f"__EXIT__{proc.returncode}")
            except FileNotFoundError:
                q.put("__ERROR__yt-dlp not found")

        threading.Thread(target=run, daemon=True).start()

        while True:
            line = q.get()
            if line.startswith("__EXIT__"):
                code = int(line.replace("__EXIT__", ""))
                # Find the downloaded file
                files = glob.glob(os.path.join(out_dir, "*"))
                filename = ""
                if files and code == 0:
                    filepath = files[0]
                    filename = os.path.basename(filepath)
                    file_registry[file_id] = filepath

                yield f"data: {json.dumps({'type':'done','code':code,'file_id':file_id,'filename':filename})}\n\n"
                break
            elif line.startswith("__ERROR__"):
                yield f"data: {json.dumps({'type':'error','message':line.replace('__ERROR__','')})}\n\n"
                break
            else:
                yield f"data: {json.dumps({'type':'log','line':line.rstrip()})}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.route("/get-file/<file_id>")
def get_file(file_id):
    filepath = file_registry.get(file_id)
    if not filepath or not os.path.exists(filepath):
        return ("File not found", 404)
    return send_file(filepath, as_attachment=True,
                     download_name=os.path.basename(filepath))

@app.route("/stream-file")
def stream_file():
    """Serves already-downloaded file to browser."""
    file_id = request.args.get("file_id", "").strip()
    filepath = file_registry.get(file_id)
    if not filepath or not os.path.exists(filepath):
        return ("File not found or expired", 404)
    return send_file(filepath, as_attachment=True,
                     download_name=os.path.basename(filepath))

# ── Launch ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  Running on http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
