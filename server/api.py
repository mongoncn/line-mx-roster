#!/usr/bin/env python3
"""排班表同步 API —— Python 标准库，零依赖。

端点：
  POST /api/login  {code}           -> {ok, token}   访问码换 token
  GET  /api/data    Bearer token    -> {shifts, updated}
  POST /api/data    Bearer token    -> 保存 {shifts}
  GET  /api/ping                    -> 健康检查
数据存本目录 data.json / tokens.json，原子写入。
"""
import json
import os
import time
import uuid
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE, "data.json")
TOKEN_FILE = os.path.join(BASE, "tokens.json")
ACCESS_CODE = os.environ.get("SHIFT_ACCESS_CODE", "")  # 查看口令 -> 只读 token
EDIT_CODE = os.environ.get("SHIFT_EDIT_CODE", "")      # 编辑口令 -> 可写 token
LOCK = threading.Lock()


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_atomic(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)


class Handler(BaseHTTPRequestHandler):
    server_version = "ShiftAPI/1.0"

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _tok_entry(self):
        h = self.headers.get("Authorization", "")
        if not h.startswith("Bearer "):
            return None
        t = h[7:]
        with LOCK:
            for x in load(TOKEN_FILE, []):
                if isinstance(x, dict) and x.get("t") == t:
                    return x
                if isinstance(x, str) and x == t:  # 旧版 token 视为可写
                    return {"t": t, "rw": True}
        return None

    def _auth(self):
        return self._tok_entry() is not None

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._json(400, {"error": "bad json"})

        if self.path == "/api/login":
            code = payload.get("code")
            if code == EDIT_CODE:
                rw = True
            elif code == ACCESS_CODE:
                rw = False
            else:
                return self._json(403, {"error": "口令错误"})
            tok = uuid.uuid4().hex
            with LOCK:
                toks = load(TOKEN_FILE, [])
                toks.append({"t": tok, "rw": rw})
                save_atomic(TOKEN_FILE, toks)
            return self._json(200, {"ok": True, "token": tok, "rw": rw})

        if self.path == "/api/data":
            ent = self._tok_entry()
            if not ent:
                return self._json(401, {"error": "未登录"})
            if not ent.get("rw"):
                return self._json(403, {"error": "只读口令，不能修改数据"})
            if not isinstance(payload.get("shifts"), dict):
                return self._json(400, {"error": "bad shifts"})
            rec = {
                "shifts": payload["shifts"],
                "updated": int(time.time()),
            }
            defs = payload.get("defs")  # 班次定义（可选）：[{key,color,hours}]
            if isinstance(defs, list) and defs:
                rec["defs"] = defs
            with LOCK:
                save_atomic(DATA_FILE, rec)
            return self._json(200, {"ok": True})

        return self._json(404, {"error": "not found"})

    def do_GET(self):
        if self.path == "/api/data":
            if not self._auth():
                return self._json(401, {"error": "未登录"})
            with LOCK:
                d = load(DATA_FILE, None)
            return self._json(200, d if d else {"shifts": {}, "updated": 0})
        if self.path == "/api/ping":
            return self._json(200, {"ok": True})
        return self._json(404, {"error": "not found"})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    if not ACCESS_CODE:
        raise SystemExit("SHIFT_ACCESS_CODE 未设置")
    print("shift-api listening on 127.0.0.1:8023")
    ThreadingHTTPServer(("127.0.0.1", 8023), Handler).serve_forever()
