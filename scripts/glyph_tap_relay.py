#!/usr/bin/env python3
"""Reads TAP events from Glyph C6 IR sensor over USB serial and forwards to SurfaceOS."""
from __future__ import annotations

import argparse
import http.client
import signal
import sys
import time
from urllib.parse import urlsplit

try:
    import serial
except ImportError:
    raise SystemExit("Install pyserial: pip install pyserial")

STOP = False


def request_stop(_signum: int, _frame: object) -> None:
    global STOP
    STOP = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Relay Glyph C6 IR tap events to SurfaceOS")
    parser.add_argument(
        "--port",
        default="/dev/tty.usbmodem1101",
        help="Glyph C6 USB serial port (check ls /dev/tty.usbmodem* or /dev/tty.SLAB*)",
    )
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--url", default="http://127.0.0.1:17000/ingest/tap")
    return parser.parse_args()


def make_conn(host: str, port: int) -> http.client.HTTPConnection:
    return http.client.HTTPConnection(host, port, timeout=1.0)


def main() -> int:
    args = parse_args()
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    parsed = urlsplit(args.url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80
    path = parsed.path or "/"

    print(f"Glyph tap relay: {args.port} @{args.baud} -> {args.url}", flush=True)

    while not STOP:
        try:
            conn = make_conn(host, port)
            with serial.Serial(args.port, args.baud, timeout=0.5) as ser:
                print(f"Glyph C6 connected on {args.port}", flush=True)
                while not STOP:
                    line = ser.readline().decode("ascii", errors="ignore").strip()
                    if not line:
                        continue
                    if line == "TAP":
                        try:
                            conn.request(
                                "POST",
                                path,
                                body=b"{}",
                                headers={
                                    "Content-Type": "application/json",
                                    "Content-Length": "2",
                                },
                            )
                            resp = conn.getresponse()
                            resp.read()
                            print("→ TAP forwarded", flush=True)
                        except Exception as exc:
                            print(f"board unreachable: {exc}", file=sys.stderr, flush=True)
                            try:
                                conn.close()
                            except Exception:
                                pass
                            conn = make_conn(host, port)
        except serial.SerialException as exc:
            print(f"serial error: {exc}; retrying in 1s", file=sys.stderr, flush=True)
            time.sleep(1.0)
        except Exception as exc:
            print(f"unexpected error: {exc}; retrying in 2s", file=sys.stderr, flush=True)
            time.sleep(2.0)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
