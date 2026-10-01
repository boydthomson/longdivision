#!/usr/bin/env python3
"""Long Division Lab - tiny server.

Serves the game (index.html) and proxies "hint" requests to an LLM using a key
from .env (ANTHROPIC_API_KEY or OPENAI_API_KEY). No third-party packages needed.

Run:  python3 server.py            (then open http://localhost:8765); static files live in public/
"""
import json
import os
import sys
import urllib.request
import urllib.error
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
PUBLIC = os.path.join(HERE, "public")
PORT = int(os.environ.get("PORT", "8765"))


def load_env():
    path = os.path.join(HERE, ".env")
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            os.environ.setdefault(k, v)


load_env()

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

SYSTEM = (
    "You are a warm, playful math coach helping a Grade 6 student (age 11-12) "
    "with long division. Give ONE short hint (max 2 sentences, under 40 words) "
    "for the exact step they are on. Never give the final answer to the whole "
    "problem. If they typed a wrong answer, gently point at what to re-check. "
    "Use plain words, no LaTeX, no markdown. You may use one emoji."
)


def describe(state):
    d = state.get("divisor")
    n = state.get("dividend")
    phase = state.get("phase")
    cur = state.get("current")
    q = state.get("qdigit")
    typed = state.get("typed")
    wrong = state.get("wrongAttempts", 0)
    lines = [f"Problem: {n} divided by {d}.",
             f"The number the student is working with right now is {cur}."]
    if phase == "q":
        lines.append(f"Step: DIVIDE. They need to figure out how many times {d} goes into {cur} (a single digit).")
    elif phase == "mul":
        lines.append(f"Step: MULTIPLY. The quotient digit they just found is {q}. They need {q} times {d}.")
    elif phase == "sub":
        lines.append(f"Step: SUBTRACT. They need {cur} minus {q * d if q is not None and d else '?'}.")
    elif phase == "bring":
        lines.append("Step: BRING DOWN the next digit of the dividend.")
    elif phase == "done":
        lines.append("They finished the problem. Congratulate them briefly.")
    if state.get("lang") == "fr":
        lines.append("IMPORTANT: Reply in French (Canadian French, tutoiement).")
    if typed:
        lines.append(f"They typed '{typed}', which was wrong. Wrong attempts so far: {wrong}.")
    return "\n".join(lines)


def ask_anthropic(prompt):
    body = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": 120,
        "system": SYSTEM,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body, method="POST",
        headers={"content-type": "application/json",
                 "x-api-key": ANTHROPIC_KEY,
                 "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()


def ask_openai(prompt):
    body = json.dumps({
        "model": OPENAI_MODEL,
        "max_tokens": 120,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions", data=body, method="POST",
        headers={"content-type": "application/json",
                 "authorization": f"Bearer {OPENAI_KEY}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    return data["choices"][0]["message"]["content"].strip()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=PUBLIC, **kw)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _json(self, code, obj):
        payload = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/api/status":
            provider = "anthropic" if ANTHROPIC_KEY else ("openai" if OPENAI_KEY else None)
            return self._json(200, {"ai": bool(provider), "provider": provider,
                                    "model": ANTHROPIC_MODEL if provider == "anthropic" else OPENAI_MODEL})
        if self.path in ("/", ""):
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        if self.path != "/api/hint":
            return self._json(404, {"error": "not found"})
        length = int(self.headers.get("content-length", "0"))
        try:
            state = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._json(400, {"error": "bad json"})
        prompt = describe(state)
        try:
            if ANTHROPIC_KEY:
                text = ask_anthropic(prompt)
            elif OPENAI_KEY:
                text = ask_openai(prompt)
            else:
                return self._json(200, {"hint": None, "reason": "no-key"})
            return self._json(200, {"hint": text})
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            sys.stderr.write(f"LLM error {e.code}: {detail}\n")
            return self._json(200, {"hint": None, "reason": f"http {e.code}"})
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"LLM error: {e}\n")
            return self._json(200, {"hint": None, "reason": str(e)})


if __name__ == "__main__":
    prov = "Anthropic" if ANTHROPIC_KEY else ("OpenAI" if OPENAI_KEY else "none (built-in hints only)")
    print(f"Long Division Lab  ->  http://localhost:{PORT}   AI hints: {prov}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
