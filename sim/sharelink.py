"""
Mission Lab share links: https://<site>/#m=<data>, where <data> is base64url(raw-deflate(JSON)).
JSON: {"n": name, "f": "jr" | "real", "c": code}. Same format as lab/lab.js pack()/unpack().
"""
import base64
import json
import re
import zlib


def decode(link):
    m = re.search(r"#m=([\w-]+)", link.strip())
    if not m:
        raise ValueError("not a Mission Lab share link (no #m=...)")
    data = m.group(1)
    raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
    obj = json.loads(zlib.decompress(raw, -15).decode("utf-8"))
    return {"name": str(obj.get("n") or "pilot"), "field": obj.get("f") or "jr", "code": str(obj.get("c") or "")}


def encode(site, name, code, field="jr"):
    co = zlib.compressobj(9, zlib.DEFLATED, -15)
    raw = co.compress(json.dumps({"n": name, "f": field, "c": code}).encode("utf-8")) + co.flush()
    return f"{site.rstrip('/')}/#m={base64.urlsafe_b64encode(raw).decode().rstrip('=')}"
