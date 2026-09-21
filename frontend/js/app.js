import { assessCamera, assessFile, getBatch, getHealth, listBatches, liveCamera, liveFile, mediaUrl, snapshotUrl, testCamera } from "./api.js?v=live3";
import {
  breakdown,
  confPct,
  countUp,
  cropOnion,
  drawDetections,
  drawOverlayBoxes,
  fmtPct,
  fmtSize,
  mostFrequent,
  renderBars,
  setDonut,
} from "./viz.js?v=live4";

const statusEl = document.getElementById("status");
const msgEl = document.getElementById("assess-msg");
const video = document.getElementById("cam");
const canvas = document.getElementById("overlay");
const recentBody = document.getElementById("recent-body");

let session = { report: null, onions: [], img: null, selected: 0, frameUrl: null, frozen: false };
let sessionGen = 0;
let camStream = null;
let mobileAddress = null;
let mobilePoll = null;
let liveTimer = null;
let liveInFlight = false;
let liveOnions = [];
const mobileFeed = document.getElementById("mobile-feed");

function deriveReport(r) {
  const onions = (r && r.onions) || [];
  const good = onions.filter((o) => o.grade === "GOOD").length;
  const bad = onions.filter((o) => o.grade === "BAD").length;
  const rev = onions.filter((o) => String(o.review_state || "").toUpperCase().includes("REVIEW")).length;
  const tot = onions.length || Number(r && r.total_onions) || 0;
  return {
    ...(r || {}),
    onions,
    total_onions: tot,
    good_count: good,
    bad_count: bad,
    review_count: rev,
    good_pct: tot ? (100 * good) / tot : null,
    bad_pct: tot ? (100 * bad) / tot : null,
    review_pct: tot ? (100 * rev) / tot : null,
  };
}

function setStatus(state, text) {
  statusEl.dataset.state = state;
  statusEl.textContent = text;
}

function showMsg(text, err) {
  msgEl.hidden = !text;
  msgEl.textContent = text || "";
  msgEl.classList.toggle("err", !!err);
}

function clock() {
  const el = document.getElementById("clock");
  const t = new Date();
  el.textContent = t.toLocaleString();
}
setInterval(clock, 1000);
clock();

function closeNavDrawer() {
  document.body.classList.remove("nav-open");
  const bd = document.getElementById("nav-backdrop");
  if (bd) bd.hidden = true;
}
const navToggle = document.getElementById("nav-toggle");
if (navToggle) {
  navToggle.addEventListener("click", () => {
    document.body.classList.toggle("nav-open");
    const open = document.body.classList.contains("nav-open");
    const bd = document.getElementById("nav-backdrop");
    if (bd) bd.hidden = !open;
  });
}
const navBackdrop = document.getElementById("nav-backdrop");
if (navBackdrop) navBackdrop.addEventListener("click", closeNavDrawer);

document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    document.getElementById("view-" + btn.dataset.view).classList.add("active");
    if (btn.dataset.view === "history" || btn.dataset.view === "reports") loadHistory();
    closeNavDrawer();
  });
});

async function bootHealth() {
  try {
    const h = await getHealth();
    if (h.model_loaded && h.status === "ok") setStatus("ok", "System online · Model ready");
    else if (h.backend === "running") setStatus("degraded", "Backend up · Model unavailable");
    else setStatus("degraded", "System degraded");
  } catch {
    setStatus("down", "Backend unreachable");
  }
}

function setCamState(text, ok) {
  document.getElementById("cam-pill").textContent = text;
  const h = document.getElementById("cam-head");
  if (h) {
    h.textContent = text;
    h.dataset.state = ok ? "ok" : "unknown";
  }
  syncEmptyFeed();
}

function hasCurrentResult() {
  return !!(session.frozen && session.report && (session.onions || []).length);
}

function syncEmptyFeed() {
  const empty = document.getElementById("feed-empty");
  if (!empty) return;
  const hasCam = !!(camStream && video.srcObject);
  const hasMob = !!(mobileAddress && mobileFeed && !mobileFeed.hidden);
  const hasImg = !!(session.frozen && session.img);
  empty.hidden = hasCam || hasMob || hasImg || hasCurrentResult();
}

let procTimer = null;
function setProcessing(on) {
  const el = document.getElementById("proc-overlay");
  if (!el) return;
  el.hidden = !on;
  document.querySelectorAll(".proc-steps li").forEach((li) => li.classList.remove("active"));
  if (procTimer) {
    clearInterval(procTimer);
    procTimer = null;
  }
  if (!on) return;
  const steps = [...document.querySelectorAll(".proc-steps li")];
  let i = 0;
  const tick = () => {
    steps.forEach((li) => li.classList.remove("active"));
    if (steps[i]) steps[i].classList.add("active");
    i = Math.min(i + 1, steps.length - 2);
  };
  tick();
  procTimer = setInterval(tick, 700);
}

document.getElementById("btn-start-cam").addEventListener("click", async () => {
  stopMobilePreview();
  mobileAddress = null;
  document.getElementById("btn-change-cam").hidden = true;
  try {
    camStream = await navigator.mediaDevices.getUserMedia({ video: true });
    video.srcObject = camStream;
    await video.play();
    document.getElementById("btn-change-cam").hidden = false;
    setCamState("● Camera Active", true);
    startLiveLoop();
  } catch {
    setCamState("Camera unavailable", false);
    showMsg("Camera not available. Use Upload image.", true);
  }
});

document.getElementById("btn-stop-cam").addEventListener("click", () => {
  if (camStream) {
    camStream.getTracks().forEach((t) => t.stop());
    camStream = null;
    video.srcObject = null;
  }
  stopMobilePreview();
  stopLiveLoop();
  liveOnions = [];
  mobileAddress = null;
  document.getElementById("btn-change-cam").hidden = true;
  setCamState("Source idle", false);
  if (!session.frozen) {
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }
});

document.getElementById("btn-capture").addEventListener("click", async () => {
  if (mobileAddress) {
    const gen = ++sessionGen;
    showMsg("Capturing frozen frame from mobile camera…");
    setProcessing(true);
    try {
      const report = await assessCamera(mobileAddress);
      if (gen !== sessionGen) return;
      await applyReport(report);
      if (gen !== sessionGen) return;
      setCamState("Mobile camera connected · " + mobileAddress, true);
    } catch (err) {
      showMsg(err.message || "Unable to connect to mobile camera.", true);
    } finally {
      setProcessing(false);
    }
    return;
  }
  if (!video.srcObject || video.readyState < 2) {
    showMsg("Connect a camera or upload an image.", true);
    return;
  }
  const c = document.createElement("canvas");
  c.width = video.videoWidth;
  c.height = video.videoHeight;
  c.getContext("2d").drawImage(video, 0, 0);
  c.toBlob(async (blob) => {
    if (!blob) return;
    await runAssess(new File([blob], "capture.jpg", { type: "image/jpeg" }));
  }, "image/jpeg", 0.92);
});

document.getElementById("file").addEventListener("change", async (e) => {
  const f = e.target.files && e.target.files[0];
  e.target.value = "";
  if (f) await runAssess(f);
});

function clearFrozenView() {
  sessionGen += 1;
  session.frozen = false;
  session.report = null;
  session.img = null;
  session.frameUrl = null;
  session.onions = [];
  session.selected = 0;
  liveOnions = [];
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  paintStats(deriveReport({ onions: [] }));
  paintSelected();
  paintRecent();
  paintReportCard(null);
  showMsg("");
  syncEmptyFeed();
}

document.getElementById("btn-clear-image").addEventListener("click", () => {
  clearFrozenView();
});

document.getElementById("btn-clear").addEventListener("click", () => {
  sessionGen += 1;
  session = { report: null, onions: [], img: null, selected: 0, frameUrl: null, frozen: false };
  liveOnions = [];
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  paintStats(deriveReport({ onions: [] }));
  document.getElementById("selected").className = "selected empty";
  document.getElementById("selected").textContent = "Select a detection";
  recentBody.innerHTML = `<p class="hint">No inspection data yet. Start an inspection to see results.</p>`;
  paintReportCard(null);
  showMsg("");
  syncEmptyFeed();
});

async function applyReport(report, file) {
  const gen = sessionGen;
  const normalized = deriveReport(report);
  session.frozen = true;
  session.report = normalized;
  session.onions = normalized.onions;
  session.selected = 0;
  const url = mediaUrl(normalized.saved && normalized.saved.frame);
  await loadFrame(url, file, gen);
  if (gen !== sessionGen) return;
  paintStats(normalized);
  paintSelected();
  paintRecent();
  paintBatchView(normalized);
  paintReportCard(normalized);
  paintCompare(normalized);
  showMsg("Inspection complete");
  syncEmptyFeed();
}

async function runAssess(file) {
  const gen = ++sessionGen;
  showMsg("Assessing frozen frame…");
  setProcessing(true);
  try {
    const report = await assessFile(file);
    if (gen !== sessionGen) return;
    await applyReport(report, file);
    if (gen !== sessionGen) return;
    setCamState("Image ready", true);
  } catch (err) {
    if (gen !== sessionGen) return;
    showMsg(err.message || "Assessment failed", true);
  } finally {
    setProcessing(false);
  }
}

function loadFrame(url, fallbackFile, gen) {
  const expected = gen == null ? sessionGen : gen;
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      if (expected !== sessionGen) return resolve();
      session.img = img;
      session.frameUrl = img.src;
      redraw();
      resolve();
    };
    img.onerror = () => {
      if (fallbackFile) {
        const r = new FileReader();
        r.onload = () => {
          const im = new Image();
          im.onload = () => {
            if (expected !== sessionGen) return resolve();
            session.img = im;
            session.frameUrl = im.src;
            redraw();
            resolve();
          };
          im.src = r.result;
        };
        r.readAsDataURL(fallbackFile);
      } else resolve();
    };
    img.src = url || "";
    if (!url && fallbackFile) img.onerror();
  });
}

function redraw() {
  if (session.frozen && session.img) {
    drawDetections(canvas, session.img, session.onions, session.selected, (i) => {
      session.selected = i;
      paintSelected();
      redraw();
    });
    return;
  }
  const src = !mobileFeed.hidden ? mobileFeed : video;
  drawOverlayBoxes(canvas, src, liveOnions, session.selected);
}

function reviewCount(onions) {
  return (onions || []).filter((o) => String(o.review_state || "").toUpperCase().includes("REVIEW")).length;
}

function paintStats(r) {
  const d = deriveReport(r);
  const tot = d.total_onions;
  const good = d.good_count;
  const bad = d.bad_count;
  const rev = d.review_count;
  const goodPct = d.good_pct;
  const badPct = d.bad_pct;
  const revPct = d.review_pct;
  const setTxt = (id, v) => {
    const el = document.getElementById(id);
    if (el) el.textContent = v;
  };
  const bump = (id, n) => {
    const el = document.getElementById(id);
    if (el) el.textContent = String(n);
  };
  bump("st-total", tot);
  const roll = (id, n) => {
    const el = document.getElementById(id);
    if (el) countUp(el, n);
  };
  roll("st-kpi-total", tot);
  roll("st-good", good);
  roll("st-bad", bad);
  roll("st-rev", rev);
  setTxt("st-good-pct", fmtPct(goodPct));
  setTxt("st-bad-pct", fmtPct(badPct));
  setTxt("st-rev-pct", fmtPct(revPct));
  const confirmedBad = Math.max(0, bad - rev);
  const dGoodPct = tot ? (100 * good) / tot : 0;
  const dRevPct = tot ? (100 * rev) / tot : 0;
  const dBadPct = tot ? (100 * confirmedBad) / tot : 0;
  setTxt("leg-good", String(good));
  setTxt("leg-bad", String(confirmedBad));
  setTxt("leg-rev", String(rev));
  setTxt("leg-good-pct", fmtPct(dGoodPct));
  setTxt("leg-bad-pct", fmtPct(dBadPct));
  setTxt("leg-rev-pct", fmtPct(dRevPct));
  const empty = document.getElementById("donut-empty");
  const legend = document.getElementById("donut-legend");
  if (empty) empty.hidden = tot > 0;
  if (legend) legend.hidden = tot === 0;
  setDonut(dGoodPct, dBadPct, dRevPct);
  renderBars(document.getElementById("bars"), breakdown(d.onions, null), d.onions);
}

function renderCompare(el, current, previous) {
  if (!el) return;
  if (!current) {
    el.innerHTML = `<p class="hint">No saved batches yet.</p>`;
    return;
  }
  if (!previous) {
    el.innerHTML = `<p class="hint">Previous saved batch unavailable.</p>
      <table class="compare-table">
        <thead><tr><th></th><th>Latest saved</th></tr></thead>
        <tbody>
          <tr><th>Batch</th><td>${current.batch_id || "—"}</td></tr>
          <tr><th>Total</th><td>${current.total_onions ?? "—"}</td></tr>
          <tr><th>GOOD</th><td>${current.good_count ?? "—"}</td></tr>
          <tr><th>BAD</th><td>${current.bad_count ?? "—"}</td></tr>
          <tr><th>GOOD %</th><td>${fmtPct(current.good_pct)}</td></tr>
          <tr><th>BAD %</th><td>${fmtPct(current.bad_pct)}</td></tr>
        </tbody>
      </table>`;
    return;
  }
  const row = (label, a, b) =>
    `<tr><th>${label}</th><td>${a}</td><td>${b}</td></tr>`;
  el.innerHTML = `
    <table class="compare-table">
      <thead><tr><th></th><th>Previous saved</th><th>Latest saved</th></tr></thead>
      <tbody>
        ${row("Batch", previous.batch_id || "—", current.batch_id || "—")}
        ${row("Total", previous.total_onions ?? "—", current.total_onions ?? "—")}
        ${row("GOOD", previous.good_count ?? "—", current.good_count ?? "—")}
        ${row("BAD", previous.bad_count ?? "—", current.bad_count ?? "—")}
        ${row("GOOD %", fmtPct(previous.good_pct), fmtPct(current.good_pct))}
        ${row("BAD %", fmtPct(previous.bad_pct), fmtPct(current.bad_pct))}
      </tbody>
    </table>`;
}

async function paintCompare() {
  try {
    const rows = await listBatches();
    const latest = rows[0] || null;
    const previous = rows[1] || null;
    renderCompare(document.getElementById("batch-compare"), latest, previous);
    renderCompare(document.getElementById("ba-compare"), latest, previous);
  } catch {
    renderCompare(document.getElementById("batch-compare"), null, null);
    renderCompare(document.getElementById("ba-compare"), null, null);
  }
}

function paintSelected() {
  const o = session.onions[session.selected];
  const box = document.getElementById("selected");
  if (!o) {
    box.className = "selected empty";
    box.textContent = "Select a detection";
    document.getElementById("btn-trace").hidden = true;
    document.getElementById("trace-box").hidden = true;
    paintLiveList();
    return;
  }
  const review = String(o.review_state || "").toUpperCase().includes("REVIEW");
  const gclass = review ? "REVIEW" : o.grade === "GOOD" ? "GOOD" : "BAD";
  const gtext = review ? "REVIEW REQUIRED" : o.grade;
  box.className = "selected";
  const id = "ONION #" + String(o.onion_number ?? session.selected + 1).padStart(2, "0");
  const bid = session.report && session.report.batch_id ? session.report.batch_id : "—";
  const ts = session.report && session.report.timestamp ? session.report.timestamp : "—";
  const lock = review
    ? `<div class="review-actions">
         <button type="button" id="btn-accept-pred" class="btn ghost">Accept prediction</button>
         <button type="button" id="btn-change-label" class="btn">Change label</button>
       </div>`
    : `<p class="lock-note">✓ Prediction locked<br/><span>Label correction is available only for REVIEW_REQUIRED predictions.</span></p>`;
  box.innerHTML = `
    <div class="sel-head">
      <img id="crop" alt="Onion crop"/>
      <div>
        <div>${id}</div>
        <div class="grade ${gclass}">${review ? "⚠ " : ""}${gtext}</div>
      </div>
    </div>
    <p class="kv"><span>AI prediction</span> ${o.class_name || "—"}</p>
    <p class="kv"><span>Confidence</span> ${confPct(o.confidence)}</p>
    <p class="kv"><span>Reason</span> ${o.reason || "—"}</p>
    <p class="kv"><span>Grade</span> ${o.grade || "—"}</p>
    <p class="kv"><span>Diameter</span> ${fmtSize(o)}</p>
    <p class="kv"><span>Measurement</span> ${o.measurement_status || "—"}</p>
    <p class="kv"><span>Review state</span> ${o.review_state || "—"}</p>
    <p class="kv"><span>Batch ID</span> ${bid}</p>
    <p class="kv"><span>Timestamp</span> ${ts}</p>
    ${lock}`;
  const crop = document.getElementById("crop");
  if (session.img) cropOnion(session.img, o, crop);
  const tb = document.getElementById("trace-box");
  const btn = document.getElementById("btn-trace");
  btn.hidden = false;
  tb.hidden = true;
  tb.innerHTML = `AI detection → ${o.class_name}<br/>${o.reason || ""}<br/>Quality rule: ${o.class_name} → ${o.grade}<br/>Final result: ${gtext}`;
  const acc = document.getElementById("btn-accept-pred");
  if (acc) acc.onclick = () => showMsg("Prediction accepted for this view only. Nothing was saved.");
  const ch = document.getElementById("btn-change-label");
  if (ch) ch.onclick = () => {
    const m = document.getElementById("review-modal");
    if (m) m.hidden = false;
  };
  paintLiveList();
}

function paintLiveList() {
  const el = document.getElementById("live-list");
  if (!el) return;
  const rows = session.onions || [];
  if (!rows.length) {
    el.innerHTML = `<p class="hint">No inspection data yet.</p>`;
    return;
  }
  el.innerHTML = rows
    .map((o, i) => {
      const review = String(o.review_state || "").toUpperCase().includes("REVIEW");
      const g = review ? "REVIEW" : o.grade;
      return `<button type="button" class="live-item${i === session.selected ? " active" : ""}" data-i="${i}">
        <span>ONION #${String(o.onion_number ?? i + 1).padStart(2, "0")}</span>
        <span>${o.class_name || "—"} · ${confPct(o.confidence)}</span>
        <span class="${review ? "tag-b" : o.grade === "GOOD" ? "tag-g" : "tag-b"}">${g}</span>
      </button>`;
    })
    .join("");
  el.querySelectorAll(".live-item").forEach((btn) => {
    btn.onclick = () => {
      session.selected = Number(btn.dataset.i);
      paintSelected();
      paintRecent();
      redraw();
    };
  });
}

function paintRecent() {
  const rows = session.onions;
  if (!rows.length) {
    recentBody.innerHTML = `<p class="hint">No inspection data yet. Start an inspection to see results.</p>`;
    paintLiveList();
    return;
  }
  recentBody.innerHTML = rows
    .map((o, i) => {
      const id = "ON-" + String(o.onion_number ?? i + 1).padStart(3, "0");
      const review = String(o.review_state || "").toUpperCase().includes("REVIEW");
      const cls = review ? "tag-b" : o.grade === "GOOD" ? "tag-g" : "tag-b";
      const decision = review ? "REVIEW" : o.grade;
      return `<button type="button" class="rcard${i === session.selected ? " active" : ""}" data-i="${i}">
        <img alt="" class="rcrop" data-i="${i}"/>
        <div>${id}</div>
        <div class="${cls}">${decision}</div>
        <div>${o.class_name}</div>
        <div>${confPct(o.confidence)}</div>
        <div>${fmtSize(o)}</div>
      </button>`;
    })
    .join("");
  recentBody.querySelectorAll(".rcard").forEach((el) => {
    el.onclick = () => {
      session.selected = Number(el.dataset.i);
      paintSelected();
      paintRecent();
      redraw();
    };
  });
  if (session.img) {
    recentBody.querySelectorAll(".rcrop").forEach((im) => {
      const o = rows[Number(im.dataset.i)];
      cropOnion(session.img, o, im);
    });
  }
}

function paintBatchView(r) {
  r = deriveReport(r);
  document.getElementById("bm-id").textContent = r.batch_id || "—";
  document.getElementById("bm-ts").textContent = r.timestamp || "—";
  const cal = r.calibrated ? "ArUco reference detected" : r.size_status || "Reference not detected";
  document.getElementById("bm-cal").textContent = cal;
  document.getElementById("ba-total").textContent = r.total_onions ?? 0;
  document.getElementById("ba-good").textContent = r.good_count ?? 0;
  document.getElementById("ba-bad").textContent = r.bad_count ?? 0;
  document.getElementById("ba-gp").textContent = fmtPct(r.good_pct);
  document.getElementById("ba-bp").textContent = fmtPct(r.bad_pct);
  const empty = document.getElementById("batch-empty");
  if (empty) empty.hidden = !!(r.total_onions || (r.onions && r.onions.length));
  const b = breakdown(r.onions, r.defect_breakdown);
  renderBars(document.getElementById("ba-bars"), b);
  document.getElementById("ba-top").textContent = mostFrequent(b);
  const rv = document.getElementById("ba-rev");
  const revN = reviewCount(r.onions);
  if (rv) rv.textContent = String(revN);
  const rp = document.getElementById("ba-rp");
  if (rp) {
    const tot = r.total_onions || 0;
    rp.textContent = tot ? ((revN / tot) * 100).toFixed(1) + "%" : "—";
  }
}

function paintReportCard(r) {
  const id = document.getElementById("rp-id");
  const ts = document.getElementById("rp-ts");
  const tot = document.getElementById("rp-tot");
  const act = document.getElementById("rp-actions");
  const dash = document.getElementById("rp-dash-status");
  const dl = document.getElementById("btn-dl-report");
  const htmlHref = r && mediaUrl(r.saved && r.saved.html);
  if (dash) dash.textContent = htmlHref ? "Current inspection report is ready." : "No report available yet";
  if (dl) {
    if (htmlHref) {
      dl.hidden = false;
      dl.href = htmlHref;
      dl.setAttribute("download", "");
    } else {
      dl.hidden = true;
      dl.removeAttribute("href");
    }
  }
  if (!id) return;
  if (!r) {
    id.textContent = "No inspection report available yet.";
    ts.textContent = "—";
    tot.textContent = "—";
    if (act) act.innerHTML = "";
    return;
  }
  id.textContent = r.batch_id || "—";
  ts.textContent = r.timestamp || "—";
  tot.textContent = `Total ${r.total_onions ?? "—"} · GOOD ${r.good_count ?? "—"} · BAD ${r.bad_count ?? "—"}`;
  const html = mediaUrl(r.saved && r.saved.html);
  const js = mediaUrl(r.saved && r.saved.json);
  act.innerHTML =
    (html ? `<a class="btn primary" href="${html}" target="_blank" rel="noopener">View report</a>
      <a class="btn" href="${html}" download>Download report</a>` : "") +
    (js ? `<a class="btn" href="${js}" download>Download JSON</a>` : "");
}

let histRows = [];

function renderHistRows(rows) {
  const body = document.getElementById("hist-body");
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="6" class="empty-row">No stored inspections.</td></tr>`;
    return;
  }
  body.innerHTML = rows
    .map(
      (b) => `<tr data-id="${b.batch_id}">
        <td>${b.batch_id}</td>
        <td>${b.timestamp || "—"}</td>
        <td>${b.total_onions ?? "—"}</td>
        <td>${b.good_count ?? "—"}</td>
        <td>${b.bad_count ?? "—"}</td>
        <td>${fmtPct(b.good_pct)}</td>
      </tr>`
    )
    .join("");
  body.querySelectorAll("tr[data-id]").forEach((tr) => {
    tr.style.cursor = "pointer";
    tr.onclick = () => showHistDetail(tr.dataset.id);
  });
}

async function loadHistory() {
  const body = document.getElementById("hist-body");
  const list = document.getElementById("report-list");
  try {
    const rows = await listBatches();
    histRows = rows;
    if (!rows.length) {
      body.innerHTML = `<tr><td colspan="6" class="empty-row">No stored inspections.</td></tr>`;
      list.innerHTML = "<li>No reports yet.</li>";
      return;
    }
    renderHistRows(rows);
    list.innerHTML = rows
      .map((b) => {
        const href = mediaUrl(b.html_path);
        const link = href
          ? `<a class="btn" href="${href}" target="_blank" rel="noopener">View digital report</a>`
          : "<span>No HTML file</span>";
        return `<li><span>${b.batch_id}</span>${link}</li>`;
      })
      .join("");
  } catch (e) {
    body.innerHTML = `<tr><td colspan="6" class="empty-row">${e.message}</td></tr>`;
  }
}

async function showHistDetail(id) {
  const el = document.getElementById("hist-detail");
  try {
    const b = await getBatch(id);
    const onions = b.onions || [];
    el.innerHTML =
      `<h3>${b.batch_id}</h3>` +
      onions
        .map(
          (o) =>
            `<p>#${o.onion_number} ${o.class_name} ${o.grade} · ${confPct(o.confidence)} · ${fmtSize(o)} · ${o.reason || ""}</p>`
        )
        .join("") || "<p>No onion rows.</p>";
  } catch (e) {
    el.textContent = e.message;
  }
}

function sim() {
  const kg = Number(document.getElementById("sim-kg").value);
  const man = Number(document.getElementById("sim-man").value);
  const ai = Number(document.getElementById("sim-ai").value);
  document.getElementById("sim-kg-o").textContent = kg;
  document.getElementById("sim-man-o").textContent = man;
  document.getElementById("sim-ai-o").textContent = ai;
  const manKg = (kg * man) / 100;
  const aiKg = (kg * ai) / 100;
  document.getElementById("sim-man-kg").textContent = manKg.toFixed(1) + " kg";
  document.getElementById("sim-ai-kg").textContent = aiKg.toFixed(1) + " kg";
  document.getElementById("bar-man").style.width = man + "%";
  document.getElementById("bar-ai").style.width = ai + "%";
  const diff = manKg - aiKg;
  document.getElementById("sim-diff").textContent =
    (diff >= 0 ? "+" : "") + diff.toFixed(1) + " kg (assumption)";
}
["sim-kg", "sim-man", "sim-ai"].forEach((id) => {
  document.getElementById(id).addEventListener("input", sim);
});
sim();

document.getElementById("btn-trace").addEventListener("click", () => {
  const tb = document.getElementById("trace-box");
  tb.hidden = !tb.hidden;
});

const modal = document.getElementById("cam-modal");
const addrInput = document.getElementById("cam-addr");
const modalMsg = document.getElementById("cam-modal-msg");

function openCamModal() {
  modal.hidden = false;
  modalMsg.hidden = true;
  addrInput.value = mobileAddress || "";
  addrInput.focus();
}

function closeCamModal() {
  modal.hidden = true;
}

function stopMobilePreview() {
  if (mobilePoll) {
    clearInterval(mobilePoll);
    mobilePoll = null;
  }
  mobileFeed.hidden = true;
}

function startMobilePreview(address) {
  stopMobilePreview();
  if (camStream) {
    camStream.getTracks().forEach((t) => t.stop());
    camStream = null;
    video.srcObject = null;
  }
  mobileAddress = address;
  mobileFeed.hidden = false;
  startLiveLoop();
  let snapBusy = false;
  const tickSnap = () => {
    if (session.frozen || snapBusy || !mobileAddress) return;
    snapBusy = true;
    mobileFeed.onload = () => {
      snapBusy = false;
      if (!session.frozen) redraw();
    };
    mobileFeed.onerror = () => {
      snapBusy = false;
    };
    mobileFeed.src = snapshotUrl(address);
  };
  tickSnap();
  mobilePoll = setInterval(tickSnap, 250);
  document.getElementById("btn-change-cam").hidden = false;
  setCamState("Mobile camera connected · " + address, true);
}

function setModalMsg(text, err) {
  modalMsg.hidden = !text;
  modalMsg.textContent = text || "";
  modalMsg.classList.toggle("err", !!err);
}

const sourceModal = document.getElementById("source-modal");
function openSourceModal() {
  if (sourceModal) sourceModal.hidden = false;
}
function closeSourceModal() {
  if (sourceModal) sourceModal.hidden = true;
}
document.getElementById("btn-mobile").addEventListener("click", openCamModal);
document.getElementById("btn-change-cam").addEventListener("click", openSourceModal);
const srcCancel = document.getElementById("btn-src-cancel");
if (srcCancel) srcCancel.addEventListener("click", closeSourceModal);
const srcLaptop = document.getElementById("btn-src-laptop");
if (srcLaptop) {
  srcLaptop.addEventListener("click", () => {
    closeSourceModal();
    document.getElementById("btn-start-cam").click();
  });
}
const srcMobile = document.getElementById("btn-src-mobile");
if (srcMobile) {
  srcMobile.addEventListener("click", () => {
    closeSourceModal();
    openCamModal();
  });
}
const btnViewReport = document.getElementById("btn-view-report");
if (btnViewReport) {
  btnViewReport.addEventListener("click", () => {
    document.getElementById("btn-gen-report").click();
  });
}
document.getElementById("btn-cam-cancel").addEventListener("click", closeCamModal);
const reviewClose = document.getElementById("btn-review-close");
if (reviewClose) {
  reviewClose.addEventListener("click", () => {
    document.getElementById("review-modal").hidden = true;
  });
}

document.getElementById("btn-cam-test").addEventListener("click", async () => {
  const address = addrInput.value.trim();
  if (!address) {
    setModalMsg("INVALID ADDRESS", true);
    return;
  }
  setModalMsg("CONNECTING…");
  const r = await testCamera(address);
  setModalMsg((r.state || "") + (r.message ? " — " + r.message : ""), !r.ok);
});

document.getElementById("btn-cam-connect").addEventListener("click", async () => {
  const address = addrInput.value.trim();
  if (!address) {
    setModalMsg("INVALID ADDRESS", true);
    return;
  }
  setModalMsg("CONNECTING…");
  const r = await testCamera(address);
  if (!r.ok) {
    setModalMsg((r.state || "CAMERA UNREACHABLE") + " — " + (r.message || ""), true);
    return;
  }
  startMobilePreview(address);
  closeCamModal();
});

document.getElementById("btn-gen-report").addEventListener("click", () => {
  const r = session.report;
  const href = r && mediaUrl(r.saved && r.saved.html);
  if (!href) {
    showMsg("No report yet. Capture or upload an image first.", true);
    return;
  }
  window.open(href, "_blank", "noopener");
});

function paintLiveHud() {
  if (session.frozen) return;
  session.onions = liveOnions;
  const tot = liveOnions.length;
  const good = liveOnions.filter((o) => o.grade === "GOOD").length;
  const bad = liveOnions.filter((o) => o.grade === "BAD").length;
  paintStats({
    total_onions: tot,
    good_count: good,
    bad_count: bad,
    good_pct: tot ? (100 * good) / tot : null,
    bad_pct: tot ? (100 * bad) / tot : null,
    onions: liveOnions,
  });
  paintSelected();
  paintRecent();
  redraw();
}

function stopLiveLoop() {
  if (liveTimer) {
    clearInterval(liveTimer);
    liveTimer = null;
  }
}

function startLiveLoop() {
  stopLiveLoop();
  liveInFlight = false;
  liveTimer = setInterval(() => {
    tickLive();
  }, 1800);
  tickLive();
}

async function tickLive() {
  if (session.frozen || liveInFlight) return;
  const gen = sessionGen;
  if (mobileAddress) {
    liveInFlight = true;
    try {
      const data = await liveCamera(mobileAddress);
      if (session.frozen || gen !== sessionGen) return;
      if (data.busy) {
        redraw();
        return;
      }
      liveOnions = data.onions || [];
      paintLiveHud();
    } catch (err) {
      console.warn("[oqa] /camera/live", err);
      if (!session.frozen) redraw();
    } finally {
      liveInFlight = false;
    }
    return;
  }
  if (!(video.srcObject && video.readyState >= 2)) return;
  liveInFlight = true;
  try {
    const c = document.createElement("canvas");
    c.width = video.videoWidth;
    c.height = video.videoHeight;
    c.getContext("2d").drawImage(video, 0, 0);
    const blob = await new Promise((resolve) => c.toBlob(resolve, "image/jpeg", 0.7));
    if (!blob) return;
    const data = await liveFile(new File([blob], "live.jpg", { type: "image/jpeg" }));
    if (session.frozen || gen !== sessionGen) return;
    if (data.busy) {
      redraw();
      return;
    }
    liveOnions = data.onions || [];
    paintLiveHud();
  } catch {
    if (!session.frozen) redraw();
  } finally {
    liveInFlight = false;
  }
}

const histFilter = document.getElementById("hist-filter");
if (histFilter) {
  histFilter.addEventListener("input", () => {
    const q = histFilter.value.trim().toLowerCase();
    renderHistRows(q ? histRows.filter((b) => String(b.batch_id || "").toLowerCase().includes(q)) : histRows);
  });
}

window.addEventListener("resize", redraw);
syncEmptyFeed();
bootHealth();
loadHistory();
paintCompare(null);
