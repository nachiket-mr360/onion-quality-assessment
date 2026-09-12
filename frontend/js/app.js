import { assessCamera, assessFile, getBatch, getHealth, listBatches, mediaUrl, snapshotUrl, testCamera } from "./api.js";
import {
  breakdown,
  confPct,
  countUp,
  cropOnion,
  drawDetections,
  fmtPct,
  fmtSize,
  mostFrequent,
  renderBars,
  setDonut,
} from "./viz.js";

const statusEl = document.getElementById("status");
const msgEl = document.getElementById("assess-msg");
const video = document.getElementById("cam");
const canvas = document.getElementById("overlay");
const recentBody = document.getElementById("recent-body");

let session = { report: null, onions: [], img: null, selected: 0, frameUrl: null };
let camStream = null;
let mobileAddress = null;
let mobilePoll = null;
const mobileFeed = document.getElementById("mobile-feed");

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

document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    document.getElementById("view-" + btn.dataset.view).classList.add("active");
    if (btn.dataset.view === "history" || btn.dataset.view === "reports") loadHistory();
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
}

document.getElementById("btn-start-cam").addEventListener("click", async () => {
  stopMobilePreview();
  mobileAddress = null;
  document.getElementById("btn-change-cam").hidden = true;
  try {
    camStream = await navigator.mediaDevices.getUserMedia({ video: true });
    video.srcObject = camStream;
    await video.play();
    setCamState("Camera connected", true);
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
  mobileAddress = null;
  document.getElementById("btn-change-cam").hidden = true;
  setCamState("Source idle", false);
});

document.getElementById("btn-capture").addEventListener("click", async () => {
  if (mobileAddress) {
    showMsg("Capturing frozen frame from mobile camera…");
    try {
      const report = await assessCamera(mobileAddress);
      await applyReport(report);
      setCamState("Mobile camera connected · " + mobileAddress, true);
    } catch (err) {
      showMsg(err.message || "Unable to connect to mobile camera.", true);
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

document.getElementById("btn-clear").addEventListener("click", () => {
  session = { report: null, onions: [], img: null, selected: 0, frameUrl: null };
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  paintStats({ total_onions: 0, good_count: 0, bad_count: 0, good_pct: null, bad_pct: null, onions: [] });
  document.getElementById("selected").className = "selected empty";
  document.getElementById("selected").textContent = "Select a detection";
  recentBody.innerHTML = `<p class="hint">No assessments yet this session.</p>`;
  paintReportCard(null);
  showMsg("");
});

async function applyReport(report, file) {
  session.report = report;
  session.onions = report.onions || [];
  session.selected = 0;
  const url = mediaUrl(report.saved && report.saved.frame);
  await loadFrame(url, file);
  paintStats(report);
  paintSelected();
  paintRecent();
  paintBatchView(report);
  paintReportCard(report);
  showMsg("Inspection complete");
}

async function runAssess(file) {
  showMsg("Assessing frozen frame…");
  try {
    const report = await assessFile(file);
    await applyReport(report, file);
    setCamState("Image ready", true);
  } catch (err) {
    showMsg(err.message || "Assessment failed", true);
  }
}

function loadFrame(url, fallbackFile) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
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
  if (!session.img) return;
  drawDetections(canvas, session.img, session.onions, session.selected, (i) => {
    session.selected = i;
    paintSelected();
    redraw();
  });
}

function reviewCount(onions) {
  return (onions || []).filter((o) => String(o.review_state || "").toUpperCase().includes("REVIEW")).length;
}

function paintStats(r) {
  const onions = r.onions || [];
  const rev = reviewCount(onions);
  const tot = r.total_onions || 0;
  countUp(document.getElementById("st-total"), tot);
  countUp(document.getElementById("st-good"), r.good_count || 0);
  countUp(document.getElementById("st-bad"), r.bad_count || 0);
  document.getElementById("st-rev").textContent = String(rev);
  document.getElementById("st-good-pct").textContent = fmtPct(r.good_pct);
  document.getElementById("st-bad-pct").textContent = fmtPct(r.bad_pct);
  document.getElementById("st-rev-pct").textContent = tot ? ((rev / tot) * 100).toFixed(1) + "%" : "—";
  setDonut(r.good_pct);
  renderBars(document.getElementById("bars"), breakdown(onions, r.defect_breakdown));
}

function paintSelected() {
  const o = session.onions[session.selected];
  const box = document.getElementById("selected");
  if (!o) {
    box.className = "selected empty";
    box.textContent = "Select a detection";
    document.getElementById("btn-trace").hidden = true;
    document.getElementById("trace-box").hidden = true;
    return;
  }
  const review = String(o.review_state || "").toUpperCase().includes("REVIEW");
  const gclass = review ? "REVIEW" : o.grade === "GOOD" ? "GOOD" : "BAD";
  const gtext = review ? "REVIEW REQUIRED" : o.grade;
  box.className = "selected";
  const id = "ON-" + String(o.onion_number ?? session.selected + 1).padStart(3, "0");
  box.innerHTML = `
    <div class="sel-head">
      <img id="crop" alt="Onion crop"/>
      <div>
        <div>${id}</div>
        <div class="grade ${gclass}">${gtext}</div>
      </div>
    </div>
    <p class="kv"><span>Class</span> ${o.class_name || "—"}</p>
    <p class="kv"><span>Confidence</span> ${confPct(o.confidence)}</p>
    <p class="kv"><span>Detected issue</span> ${o.reason || "—"}</p>
    <p class="kv"><span>Grade</span> ${o.grade || "—"}</p>
    <p class="kv"><span>Size</span> ${fmtSize(o)}</p>
    <p class="kv"><span>Measurement</span> ${o.measurement_status || "—"}</p>`;
  const crop = document.getElementById("crop");
  if (session.img) cropOnion(session.img, o, crop);
  const tb = document.getElementById("trace-box");
  const btn = document.getElementById("btn-trace");
  btn.hidden = false;
  tb.hidden = true;
  tb.innerHTML = `AI detection → ${o.class_name}<br/>${o.reason || ""}<br/>Quality rule: ${o.class_name} → ${o.grade}<br/>Final result: ${gtext}`;
}

function paintRecent() {
  const rows = session.onions;
  if (!rows.length) {
    recentBody.innerHTML = `<p class="hint">No assessments yet this session.</p>`;
    return;
  }
  recentBody.innerHTML = rows
    .map((o, i) => {
      const id = "ON-" + String(o.onion_number ?? i + 1).padStart(3, "0");
      const cls = o.grade === "GOOD" ? "tag-g" : "tag-b";
      return `<button type="button" class="rcard${i === session.selected ? " active" : ""}" data-i="${i}">
        <img alt="" class="rcrop" data-i="${i}"/>
        <div>${id}</div>
        <div class="${cls}">${o.grade}</div>
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
  document.getElementById("bm-id").textContent = r.batch_id || "—";
  document.getElementById("bm-ts").textContent = r.timestamp || "—";
  const cal = r.calibrated ? "ArUco reference detected" : r.size_status || "Reference not detected";
  document.getElementById("bm-cal").textContent = cal;
  document.getElementById("ba-total").textContent = r.total_onions ?? 0;
  document.getElementById("ba-good").textContent = r.good_count ?? 0;
  document.getElementById("ba-bad").textContent = r.bad_count ?? 0;
  document.getElementById("ba-gp").textContent = fmtPct(r.good_pct);
  document.getElementById("ba-bp").textContent = fmtPct(r.bad_pct);
  const b = breakdown(r.onions, r.defect_breakdown);
  renderBars(document.getElementById("ba-bars"), b);
  document.getElementById("ba-top").textContent = mostFrequent(b);
  const rv = document.getElementById("ba-rev");
  if (rv) rv.textContent = String(reviewCount(r.onions));
}

function paintReportCard(r) {
  const id = document.getElementById("rp-id");
  const ts = document.getElementById("rp-ts");
  const tot = document.getElementById("rp-tot");
  const act = document.getElementById("rp-actions");
  if (!id) return;
  if (!r) {
    id.textContent = "No inspection report available yet.";
    ts.textContent = "—";
    tot.textContent = "—";
    act.innerHTML = "";
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

async function loadHistory() {
  const body = document.getElementById("hist-body");
  const list = document.getElementById("report-list");
  try {
    const rows = await listBatches();
    if (!rows.length) {
      body.innerHTML = `<tr><td colspan="6" class="empty-row">No stored inspections.</td></tr>`;
      list.innerHTML = "<li>No reports yet.</li>";
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
  const tick = () => {
    mobileFeed.src = snapshotUrl(address);
  };
  tick();
  mobilePoll = setInterval(tick, 700);
  document.getElementById("btn-change-cam").hidden = false;
  setCamState("Mobile camera connected · " + address, true);
}

function setModalMsg(text, err) {
  modalMsg.hidden = !text;
  modalMsg.textContent = text || "";
  modalMsg.classList.toggle("err", !!err);
}

document.getElementById("btn-mobile").addEventListener("click", openCamModal);
document.getElementById("btn-change-cam").addEventListener("click", openCamModal);
document.getElementById("btn-cam-cancel").addEventListener("click", closeCamModal);

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

window.addEventListener("resize", redraw);
bootHealth();
loadHistory();
