import argparse
import os
import socket
import time
from datetime import datetime

import serial


DEFAULT_UDP_HOST = os.environ.get("AURAPASS_UDP_HOST", "127.0.0.1")
DEFAULT_UDP_PORT = int(os.environ.get("AURAPASS_UDP_PORT", "9090"))
DEFAULT_SERIAL_PORT = os.environ.get("AURAPASS_SERIAL_PORT", "COM3")
DEFAULT_BAUD_RATE = int(os.environ.get("AURAPASS_BAUD_RATE", "9600"))


def log(message):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)


def parse_args():
    parser = argparse.ArgumentParser(description="Relay AuraPass UDP commands to a serial port.")
    parser.add_argument("--host", default=DEFAULT_UDP_HOST)
    parser.add_argument("--udp-port", type=int, default=DEFAULT_UDP_PORT)
    parser.add_argument("--serial-port", default=DEFAULT_SERIAL_PORT)
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD_RATE)
    return parser.parse_args()


def main():
    args = parse_args()
    log("AuraPass Proteus bridge starting")
    log(f"UDP {args.host}:{args.udp_port} -> {args.serial_port} @ {args.baud}")

    try:
        ser = serial.Serial(
            args.serial_port,
            args.baud,
            timeout=1,
            write_timeout=1,
            dsrdtr=False,
            rtscts=False,
        )
        time.sleep(1.8)
        log(f"Serial open on {args.serial_port}")
    except Exception as exc:
        log(f"ERROR opening {COM_PORT}: {exc}")
        return 1

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((args.host, args.udp_port))
        log("UDP listener ready")
        while True:
            data, addr = sock.recvfrom(1024)
            raw = data.decode("utf-8", errors="replace").strip()
            if not raw:
                continue
            ser.write((raw + "\n").encode("utf-8"))
            ser.flush()
            log(f"Proteus <- {raw}")
    except KeyboardInterrupt:
        log("Bridge stopped")
    except Exception as exc:
        log(f"ERROR bridge failed: {exc}")
        return 1
    finally:
        try:
            ser.close()
        except Exception:
            pass
        sock.close()
        log("Bridge offline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
