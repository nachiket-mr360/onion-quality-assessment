from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import json
import mimetypes

base = "http://127.0.0.1:8000"
root = Path(__file__).resolve().parent.parent

def get(path):
    with urlopen(base + path, timeout=60) as r:
        return r.status, r.headers.get_content_type(), r.read()

for p in ["/", "/css/app.css", "/js/app.js", "/js/api.js", "/js/viz.js", "/health", "/docs",
          "/assets/ex_healthy.jpg"]:
    try:
        st, ct, body = get(p)
        print("GET", st, p, ct, len(body))
    except HTTPError as e:
        print("GET FAIL", p, e.code)

img = root / "captures" / "reports" / "phaseI_healthy_frame.jpg"
boundary = "----bound"
payload = (
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="file"; filename="t.jpg"\r\n'
    f"Content-Type: image/jpeg\r\n\r\n"
).encode() + img.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
req = Request(base + "/assess", data=payload, method="POST")
req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
with urlopen(req, timeout=120) as r:
    data = json.loads(r.read().decode())
print("POST /assess", r.status, data.get("batch_id"), data.get("total_onions"),
      data.get("good_count"), data.get("bad_count"), data.get("good_pct"))
print("classes", [o.get("class_name") for o in data.get("onions") or []])
print("saved frame", data.get("saved", {}).get("frame"))
print("GET /batches", get("/batches")[0], len(json.loads(get("/batches")[2])))
