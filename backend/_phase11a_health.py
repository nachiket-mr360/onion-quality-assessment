from urllib.request import urlopen
print(urlopen("http://127.0.0.1:8000/health", timeout=10).read().decode())
