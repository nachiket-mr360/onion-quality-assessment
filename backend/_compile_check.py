import py_compile
import sys
from pathlib import Path

files = [
    Path("backend/main.py"),
    Path("backend/__init__.py"),
    Path("cv/demo.py"),
]
ok = True
for p in files:
    try:
        py_compile.compile(p, doraise=True)
        print("compile_ok", p)
    except py_compile.PyCompileError as e:
        ok = False
        print("compile_fail", p, e)
sys.exit(0 if ok else 1)
