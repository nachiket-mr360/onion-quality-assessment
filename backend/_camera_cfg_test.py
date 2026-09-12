import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError

base = "http://127.0.0.1:8000"

def post(path, body):
    req = Request(base + path, data=json.dumps(body).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode())
    except HTTPError as e:
        return e.code, json.loads(e.read().decode())

print("invalid", post("/camera/test", {"address": "not-an-ip"}))
print("empty", post("/camera/test", {"address": "   "}))
print("unreachable", post("/camera/test", {"address": "192.0.2.1:8080"}))
