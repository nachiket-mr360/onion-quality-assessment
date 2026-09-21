const ORDER = ["HEALTHY", "DAMAGED", "ROTTEN", "SPROUTED"];

export function countUp(el, to, dur = 500) {
  const start = performance.now();
  const from = Number(el.textContent) || 0;
  const tick = (t) => {
    const p = Math.min(1, (t - start) / dur);
    el.textContent = String(Math.round(from + (to - from) * p));
    if (p < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

export function setDonut(goodPct, badPct, revPct) {
  const g = Number.isFinite(Number(goodPct)) ? Math.max(0, Number(goodPct)) : 0;
  const b = Number.isFinite(Number(badPct)) ? Math.max(0, Number(badPct)) : 0;
  const r = Number.isFinite(Number(revPct)) ? Math.max(0, Number(revPct)) : 0;
  const apply = (el, len, off) => {
    if (!el) return;
    el.style.strokeDasharray = `${len} 100`;
    el.style.strokeDashoffset = String(-off);
  };
  apply(document.getElementById("donut-good"), g, 0);
  apply(document.getElementById("donut-bad"), b, g);
  apply(document.getElementById("donut-rev"), r, g + b);
}

export function breakdown(onions, apiBreakdown) {
  const b = { HEALTHY: 0, DAMAGED: 0, ROTTEN: 0, SPROUTED: 0 };
  const list = onions || [];
  if (list.length) {
    for (const o of list) {
      const n = String(o.class_name || o.class || "").toUpperCase();
      if (n in b) b[n] += 1;
    }
    return b;
  }
  if (apiBreakdown && typeof apiBreakdown === "object") {
    for (const k of ORDER) b[k] = Number(apiBreakdown[k]) || 0;
  }
  return b;
}

export function renderBars(el, b, hasInspection) {
  if (!el) return;
  const counts = b || { HEALTHY: 0, DAMAGED: 0, ROTTEN: 0, SPROUTED: 0 };
  const listLen = Array.isArray(hasInspection) ? hasInspection.length : null;
  const showRows = listLen != null ? listLen > 0 : !!hasInspection;
  if (!showRows) {
    el.innerHTML = `<p class="hint bars-empty">No inspection data yet.</p>`;
    return;
  }
  const max = Math.max(0, ...ORDER.map((k) => counts[k] || 0));
  el.innerHTML = ORDER.map((k) => {
    const n = counts[k] || 0;
    return `<div class="bar-row bar-${k.toLowerCase()}"><span>${k}</span><span class="bar-track"><i data-w="${max ? (n / max) * 100 : 0}"></i></span><span>${n}</span></div>`;
  }).join("");
  requestAnimationFrame(() => {
    el.querySelectorAll(".bar-row i").forEach((i) => {
      i.style.width = `${Number(i.dataset.w) || 0}%`;
    });
  });
}

export function drawOverlayBoxes(canvas, source, onions, selectedIdx) {
  const ctx = canvas.getContext("2d");
  const wrap = canvas.parentElement;
  const w = wrap.clientWidth;
  const h = wrap.clientHeight;
  canvas.width = w;
  canvas.height = h;
  ctx.clearRect(0, 0, w, h);
  const iw = source.videoWidth || source.naturalWidth || source.width;
  const ih = source.videoHeight || source.naturalHeight || source.height;
  if (!iw || !ih) return;
  const scale = Math.min(w / iw, h / ih);
  const dw = iw * scale;
  const dh = ih * scale;
  const ox = (w - dw) / 2;
  const oy = (h - dh) / 2;
  (onions || []).forEach((o, i) => {
    const box = o.xyxy;
    if (!box || box.length < 4) return;
    const [x1, y1, x2, y2] = box;
    const x = ox + x1 * scale;
    const y = oy + y1 * scale;
    const bw = (x2 - x1) * scale;
    const bh = (y2 - y1) * scale;
    const review = String(o.review_state || "").toUpperCase().includes("REVIEW");
    ctx.strokeStyle = review ? "#c98912" : o.grade === "GOOD" ? "#1f9d5b" : "#d64545";
    ctx.lineWidth = i === selectedIdx ? 4 : 2;
    ctx.strokeRect(x, y, bw, bh);
    const id = "ON-" + String(o.onion_number ?? i + 1).padStart(3, "0");
    const pct = o.confidence == null ? "" : `${Math.round(Number(o.confidence) * 100)}%`;
    const decision = review ? "REVIEW REQUIRED" : o.grade || "";
    const label = `${o.class_name || ""} ${pct}  ${decision}`;
    ctx.font = "11px Segoe UI";
    const tw = ctx.measureText(label).width + 8;
    ctx.fillStyle = ctx.strokeStyle;
    ctx.fillRect(x, Math.max(0, y - 18), tw, 18);
    ctx.fillStyle = "#fff";
    ctx.fillText(label, x + 4, Math.max(12, y - 5));
  });
}

export function drawDetections(canvas, img, onions, selectedIdx, onSelect) {
  const ctx = canvas.getContext("2d");
  const wrap = canvas.parentElement;
  const w = wrap.clientWidth;
  const h = wrap.clientHeight;
  canvas.width = w;
  canvas.height = h;
  const iw = img.naturalWidth || img.width;
  const ih = img.naturalHeight || img.height;
  const scale = Math.min(w / iw, h / ih);
  const dw = iw * scale;
  const dh = ih * scale;
  const ox = (w - dw) / 2;
  const oy = (h - dh) / 2;
  ctx.clearRect(0, 0, w, h);
  ctx.drawImage(img, ox, oy, dw, dh);
  (onions || []).forEach((o, i) => {
    const box = o.xyxy;
    if (!box || box.length < 4) return;
    const [x1, y1, x2, y2] = box;
    const x = ox + x1 * scale;
    const y = oy + y1 * scale;
    const bw = (x2 - x1) * scale;
    const bh = (y2 - y1) * scale;
    const review = String(o.review_state || "").toUpperCase().includes("REVIEW");
    ctx.strokeStyle = review ? "#c98912" : o.grade === "GOOD" ? "#1f9d5b" : "#d64545";
    ctx.lineWidth = i === selectedIdx ? 4 : 2;
    ctx.globalAlpha = 0.95;
    ctx.strokeRect(x, y, bw, bh);
    const id = "ON-" + String(o.onion_number ?? i + 1).padStart(3, "0");
    const pct = o.confidence == null ? "" : `${Math.round(Number(o.confidence) * 100)}%`;
    const decision = review ? "REVIEW REQUIRED" : o.grade || "";
    const label = `${o.class_name || ""} ${pct}  ${decision}`;
    ctx.font = "11px Segoe UI";
    const tw = ctx.measureText(label).width + 8;
    ctx.fillStyle = ctx.strokeStyle;
    ctx.fillRect(x, Math.max(0, y - 18), tw, 18);
    ctx.fillStyle = "#fff";
    ctx.fillText(label, x + 4, Math.max(12, y - 5));
  });
  canvas.onclick = (ev) => {
    const r = canvas.getBoundingClientRect();
    const px = ev.clientX - r.left;
    const py = ev.clientY - r.top;
    let hit = -1;
    (onions || []).forEach((o, i) => {
      const box = o.xyxy;
      if (!box) return;
      const x = ox + box[0] * scale;
      const y = oy + box[1] * scale;
      const bw = (box[2] - box[0]) * scale;
      const bh = (box[3] - box[1]) * scale;
      if (px >= x && px <= x + bw && py >= y && py <= y + bh) hit = i;
    });
    if (hit >= 0 && onSelect) onSelect(hit);
  };
}

export function cropOnion(img, onion, dest) {
  if (!dest || !onion || !onion.xyxy) return;
  const [x1, y1, x2, y2] = onion.xyxy;
  const c = document.createElement("canvas");
  const w = Math.max(1, x2 - x1);
  const h = Math.max(1, y2 - y1);
  c.width = w;
  c.height = h;
  c.getContext("2d").drawImage(img, x1, y1, w, h, 0, 0, w, h);
  dest.src = c.toDataURL("image/jpeg", 0.85);
}

export function fmtSize(o) {
  if (o && o.diameter_mm != null && Number.isFinite(Number(o.diameter_mm))) {
    return Number(o.diameter_mm).toFixed(1) + " mm";
  }
  return "Not calibrated";
}

export function fmtPct(v) {
  return v == null ? "—" : Number(v).toFixed(1) + "%";
}

export function confPct(v) {
  if (v == null) return "—";
  return (Number(v) * 100).toFixed(1) + "%";
}

export function mostFrequent(b) {
  let top = "—";
  let n = -1;
  for (const k of ORDER) {
    if ((b[k] || 0) > n) {
      n = b[k] || 0;
      top = k;
    }
  }
  return n > 0 ? top : "—";
}
