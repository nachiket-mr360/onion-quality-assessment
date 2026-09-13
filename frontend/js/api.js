export async function getHealth() {
  const res = await fetch("/health");
  if (!res.ok) throw new Error("Health check failed");
  return res.json();
}

export async function assessFile(file) {
  const fd = new FormData();
  fd.append("file", file, file.name || "frame.jpg");
  const res = await fetch("/assess", { method: "POST", body: fd });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    const msg = typeof d === "string" ? d : (d && d.error) || "Assessment failed";
    throw new Error(msg);
  }
  return data;
}

export async function listBatches() {
  const res = await fetch("/batches");
  if (!res.ok) throw new Error("Could not load history");
  return res.json();
}

export async function getBatch(id) {
  const res = await fetch("/batches/" + encodeURIComponent(id));
  if (!res.ok) throw new Error("Batch not found");
  return res.json();
}

export async function testCamera(address) {
  const res = await fetch("/camera/test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ address }),
  });
  const data = await res.json().catch(() => ({}));
  if (res.status === 400) {
    return { ok: false, state: "INVALID ADDRESS", message: data.detail || "Invalid address" };
  }
  if (!res.ok) {
    const d = data.detail;
    return { ok: false, state: "CAMERA UNREACHABLE", message: typeof d === "string" ? d : "Unable to connect to mobile camera." };
  }
  return data;
}

export async function liveCamera(address) {
  const res = await fetch("/camera/live", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ address }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    throw new Error(typeof d === "string" ? d : (d && d.error) || "Live detection failed");
  }
  return data;
}

export async function liveFile(file) {
  const fd = new FormData();
  fd.append("file", file, file.name || "live.jpg");
  const res = await fetch("/live", { method: "POST", body: fd });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    throw new Error(typeof d === "string" ? d : (d && d.error) || "Live detection failed");
  }
  return data;
}

export async function assessCamera(address) {
  const res = await fetch("/camera/assess", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ address }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    throw new Error(typeof d === "string" ? d : (d && d.error) || "Assessment failed");
  }
  return data;
}

export function snapshotUrl(address) {
  return "/camera/snapshot?address=" + encodeURIComponent(address) + "&t=" + Date.now();
}

export function mediaUrl(path) {
  if (!path) return null;
  const name = String(path).split(/[/\\]/).pop();
  if (!name) return null;
  return "/media/reports/" + encodeURIComponent(name);
}
