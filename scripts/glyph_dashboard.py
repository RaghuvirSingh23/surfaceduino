#!/usr/bin/env python3
"""SurfaceOS — Glyph C6 IR live dashboard + tap relay.

One process:
  1. reads the Glyph C6 over USB serial (READY / IR:0 / IR:1 / TAP)
  2. serves a live web dashboard at http://127.0.0.1:8100 (Server-Sent Events)
  3. forwards each TAP to the UNO Q at /ingest/tap so the note/drum fires

Run:
  python3 scripts/glyph_dashboard.py --port /dev/cu.usbmodem101
Then open http://127.0.0.1:8100
"""
from __future__ import annotations

import argparse
import http.client
import json
import queue
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

try:
    import serial
except ImportError:
    raise SystemExit("Install pyserial: pip3 install pyserial")


# ---- shared state ----------------------------------------------------------
STATE = {"connected": False, "ir": 0, "taps": 0, "forwarded": 0, "last_tap": None}
SUBSCRIBERS: list["queue.Queue[str]"] = []
SUBS_LOCK = threading.Lock()


def broadcast(event: dict) -> None:
    payload = json.dumps(event)
    with SUBS_LOCK:
        dead = []
        for q in SUBSCRIBERS:
            try:
                q.put_nowait(payload)
            except queue.Full:
                dead.append(q)
        for q in dead:
            SUBSCRIBERS.remove(q)


# ---- serial reader + tap forwarder ----------------------------------------
class Forwarder:
    def __init__(self, url: str | None):
        self.enabled = bool(url)
        self.conn: http.client.HTTPConnection | None = None
        if url:
            p = urlsplit(url)
            self.host, self.port, self.path = p.hostname, (p.port or 80), (p.path or "/")

    def send(self) -> bool:
        if not self.enabled:
            return False
        try:
            if self.conn is None:
                self.conn = http.client.HTTPConnection(self.host, self.port, timeout=1.0)
            self.conn.request("POST", self.path, body=b"{}",
                              headers={"Content-Type": "application/json", "Content-Length": "2"})
            resp = self.conn.getresponse()
            resp.read()
            return resp.status == 202
        except Exception:
            try:
                if self.conn:
                    self.conn.close()
            except Exception:
                pass
            self.conn = None
            return False


def serial_loop(port: str, baud: int, forwarder: Forwarder) -> None:
    while True:
        try:
            ser = serial.Serial(port, baud, timeout=0.5)
            STATE["connected"] = True
            broadcast({"type": "status", "connected": True})
            print(f"Glyph connected on {port}", flush=True)
            while True:
                line = ser.readline().decode("ascii", errors="ignore").strip()
                if not line:
                    continue
                if line == "TAP":
                    STATE["taps"] += 1
                    STATE["last_tap"] = time.strftime("%H:%M:%S")
                    ok = forwarder.send()
                    if ok:
                        STATE["forwarded"] += 1
                    broadcast({"type": "tap", "count": STATE["taps"],
                               "forwarded": ok, "forward_on": forwarder.enabled})
                    print(f"TAP #{STATE['taps']}  forwarded={ok}", flush=True)
                elif line.startswith("IR:"):
                    STATE["ir"] = 1 if line.strip().endswith("1") else 0
                    broadcast({"type": "ir", "value": STATE["ir"]})
                elif line == "READY":
                    broadcast({"type": "log", "msg": "Glyph booted (READY)"})
                elif line.startswith("CAL:"):
                    status = line[4:]
                    broadcast({"type": "cal", "status": status})
                    print(line, flush=True)
                elif line.startswith("ACCEL:"):
                    try:
                        broadcast({"type": "accel", "value": float(line[6:])})
                    except ValueError:
                        pass
                elif line.startswith("ERR:"):
                    broadcast({"type": "log", "msg": "IMU error: " + line[4:]})
                    print(line, flush=True)
        except serial.SerialException as exc:
            STATE["connected"] = False
            broadcast({"type": "status", "connected": False, "error": str(exc)})
            print(f"serial error: {exc}; retrying in 1s", flush=True)
            time.sleep(1.0)


# ---- web server ------------------------------------------------------------
PAGE = """<!doctype html><html><head><meta charset=utf-8>
<title>SurfaceOS · IR monitor</title><meta name=viewport content="width=device-width,initial-scale=1">
<style>
:root{color-scheme:dark}
*{box-sizing:border-box;margin:0;padding:0}
body{font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;background:#0d1117;color:#e6edf3;padding:24px}
.wrap{max-width:760px;margin:0 auto}
h1{font-size:20px;font-weight:600;margin-bottom:4px}
.sub{color:#8b949e;font-size:13px;margin-bottom:20px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}
.card{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:18px}
.card h2{font-size:12px;font-weight:500;color:#8b949e;text-transform:uppercase;letter-spacing:.05em;margin-bottom:12px}
.beam{height:120px;border-radius:10px;display:flex;align-items:center;justify-content:center;
 font-size:22px;font-weight:600;transition:background .08s,color .08s;background:#21262d;color:#8b949e}
.beam.present{background:#1f6feb;color:#fff}
.tap{height:120px;border-radius:10px;display:flex;flex-direction:column;align-items:center;justify-content:center;
 background:#21262d;transition:background .1s}
.tap.flash{background:#238636}
.tap .big{font-size:40px;font-weight:700;line-height:1}
.tap .lbl{font-size:12px;color:#8b949e;margin-top:6px}
.stats{display:flex;gap:24px;flex-wrap:wrap}
.stat{font-size:13px;color:#8b949e}.stat b{display:block;font-size:22px;color:#e6edf3;font-weight:600}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:#f85149;margin-right:6px;vertical-align:middle}
.dot.on{background:#3fb950}
#log{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:14px;height:220px;overflow:auto;
 font:12px/1.6 ui-monospace,Menlo,monospace}
#log div{white-space:pre}
.tag{display:inline-block;min-width:44px;text-align:center;border-radius:4px;padding:0 6px;margin-right:8px;font-weight:600}
.t-tap{background:#238636;color:#fff}.t-acc{background:#1f6feb33;color:#58a6ff}.t-sys{background:#30363d;color:#8b949e}
.bar-wrap{height:120px;background:#21262d;border-radius:10px;position:relative;overflow:hidden}
.bar-fill{position:absolute;bottom:0;left:0;right:0;background:#1f6feb;transition:height .08s;height:0%}
.bar-val{position:absolute;top:50%;left:0;right:0;transform:translateY(-50%);text-align:center;font-size:22px;font-weight:700;color:#e6edf3}
.bar-lbl{position:absolute;bottom:8px;left:0;right:0;text-align:center;font-size:11px;color:#8b949e}
.imu-status{display:inline-block;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:600;background:#21262d;color:#8b949e;margin-left:10px}
.imu-status.ok{background:#0d3320;color:#3fb950}.imu-status.fail{background:#3d1212;color:#f85149}
</style></head><body><div class=wrap>
<h1>SurfaceOS · IMU tap monitor</h1>
<div class=sub><span id=conn class=dot></span><span id=connText>connecting…</span>
 <span id=calBadge class=imu-status>IMU —</span>
 &nbsp;·&nbsp; Modulino Movement → Qwiic → Glyph C6 → USB → dashboard → UNO Q</div>

<div class=grid>
 <div class=card><h2>Accelerometer (motion above 1g)</h2>
  <div class=bar-wrap><div id=barFill class=bar-fill></div>
   <div id=barVal class=bar-val>0.000</div>
   <div class=bar-lbl>g (tap spike ≈ 0.5–2.0)</div></div></div>
 <div class=card><h2>Tap → action</h2><div id=tap class=tap><div class=big id=tapCount>0</div>
   <div class=lbl id=fwd>waiting for taps</div></div></div>
</div>

<div class=card style="margin-bottom:14px"><div class=stats>
 <div class=stat><b id=sTaps>0</b>taps</div>
 <div class=stat><b id=sFwd>0</b>forwarded to UNO Q</div>
 <div class=stat><b id=sLast>—</b>last tap</div>
</div></div>

<div class=card><h2>Event log</h2><div id=log></div></div>
</div>
<script>
const $=id=>document.getElementById(id);
function log(tag,cls,msg){const l=$('log');const d=document.createElement('div');
 const t=new Date().toLocaleTimeString();
 d.innerHTML='<span class="tag '+cls+'">'+tag+'</span>'+t+'  '+msg;
 l.insertBefore(d,l.firstChild); while(l.children.length>200)l.removeChild(l.lastChild);}
function setConn(on){$('conn').className='dot'+(on?' on':'');$('connText').textContent=on?'Glyph connected':'Glyph disconnected';}
const MAX_G = 2.0;
const es=new EventSource('/events');
es.onmessage=e=>{const m=JSON.parse(e.data);
 if(m.type==='accel'){
   const v=Math.min(m.value, MAX_G);
   const pct=Math.round(v/MAX_G*100);
   $('barFill').style.height=pct+'%';
   $('barFill').style.background=pct>40?'#e24b4a':pct>15?'#ba7517':'#1f6feb';
   $('barVal').textContent=m.value.toFixed(3);}
 else if(m.type==='cal'){
   const b=$('calBadge');
   b.className='imu-status '+(m.status==='ok'?'ok':'fail');
   b.textContent='IMU '+(m.status==='ok'?'✓ ready':'✗ not found');
   log('SYS','t-sys','IMU calibration: '+m.status);}
 else if(m.type==='tap'){$('tapCount').textContent=m.count;$('sTaps').textContent=m.count;
   const tp=$('tap');tp.classList.add('flash');setTimeout(()=>tp.classList.remove('flash'),150);
   let f=m.forward_on?(m.forwarded?'✓ forwarded to UNO Q':'✗ UNO Q unreachable'):'forwarding off';
   $('fwd').textContent=f;$('sLast').textContent=new Date().toLocaleTimeString();
   if(m.forwarded){$('sFwd').textContent=(+$('sFwd').textContent+1);}
   log('TAP','t-tap','tap #'+m.count+'  '+f);}
 else if(m.type==='status'){setConn(m.connected);log('SYS','t-sys',m.connected?'serial connected':'serial lost'+(m.error?': '+m.error:''));}
 else if(m.type==='log'){log('SYS','t-sys',m.msg);}
};
es.onerror=()=>setConn(false);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):  # silence default logging
        pass

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"):
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            q: "queue.Queue[str]" = queue.Queue(maxsize=200)
            with SUBS_LOCK:
                SUBSCRIBERS.append(q)
            # push current state on connect
            q.put_nowait(json.dumps({"type": "status", "connected": STATE["connected"]}))
            q.put_nowait(json.dumps({"type": "ir", "value": STATE["ir"]}))
            try:
                while True:
                    try:
                        data = q.get(timeout=15)
                        self.wfile.write(f"data: {data}\n\n".encode())
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")  # keep-alive comment
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                with SUBS_LOCK:
                    if q in SUBSCRIBERS:
                        SUBSCRIBERS.remove(q)
        else:
            self.send_error(404)


def main() -> int:
    ap = argparse.ArgumentParser(description="Glyph C6 IR live dashboard + tap relay")
    ap.add_argument("--port", default="/dev/cu.usbmodem101", help="Glyph USB serial port")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--http-port", type=int, default=8100, help="dashboard port")
    ap.add_argument("--forward-url", default="http://127.0.0.1:17000/ingest/tap",
                    help="UNO Q tap endpoint; pass '' to disable forwarding")
    args = ap.parse_args()

    forwarder = Forwarder(args.forward_url or None)
    threading.Thread(target=serial_loop, args=(args.port, args.baud, forwarder), daemon=True).start()

    srv = ThreadingHTTPServer(("127.0.0.1", args.http_port), Handler)
    url = f"http://127.0.0.1:{args.http_port}"
    print(f"Dashboard: {url}   (serial {args.port}, forward -> {args.forward_url or 'OFF'})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
