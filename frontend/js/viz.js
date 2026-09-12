const CIRC = 2 * Math.PI * 42;
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

export function setDonut(goodPct) {
  const arc = document.getElementById("donut-good");
  if (!arc) return;
  const g = Number(goodPct);
  const frac = Number.isFinite(g) ? Math.max(0, Math.min(100, g)) / 100 : 0;
  arc.style.strokeDasharray = `${frac * CIRC} ${CIRC}`;
}

export function breakdown(onions, apiBreakdown) {
  const b = { HEALTHY: 0, DAMAGED: 0, ROTTEN: 0, SPROUTED: 0 };
  if (apiBreakdown && typeof apiBreakdown === "object") {
    for (const k of ORDER) b[k] = Number(apiBreakdown[k]) || 0;
    return b;
  }
  for (const o of onions || []) {
    const n = String(o.class_name || "").toUpperCase();
    if (n in b) b[n] += 1;
  }
  return b;
}

export function renderBars(el, b) {
  if (!el) return;
  const total = ORDER.reduce((s, k) => s + (b[k] || 0), 0) || 1;
  el.innerHTML = ORDER.map((k) => {
    const n = b[k] || 0;
    const w = Math.round((n / total) * 100);
    return `<div class="bar-row"><span>${k}</span><span><i style="width:${w}%"></i></span><span>${n}</span></div>`;
  }).join("");
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
    const pct = o.confidence == null ? "" : ` ${Math.round(Number(o.confidence) * 100)}%`;
    const label = `${id} | ${o.class_name} ${o.grade}${pct}`;
    ctx.font = "12px Segoe UI";
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
