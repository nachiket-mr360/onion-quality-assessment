import py_compile
from pathlib import Path
from urllib.request import urlopen

root = Path(__file__).resolve().parent.parent
for p in [root / "backend" / "main.py"]:
    py_compile.compile(p, doraise=True)
    print("compile_ok", p.name)

base = "http://127.0.0.1:8000"
checks = ["/", "/css/app.css", "/js/app.js", "/js/api.js", "/health", "/docs"]
for path in checks:
    with urlopen(base + path, timeout=30) as r:
        body = r.read(200)
        print(r.status, path, r.headers.get_content_type(), "len", r.headers.get("content-length"), body[:40])
