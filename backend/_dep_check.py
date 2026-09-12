import importlib.util
import sys

for name in ("fastapi", "uvicorn"):
    spec = importlib.util.find_spec(name)
    print(f"{name}={'yes' if spec else 'no'}")
print("exe", sys.executable)
