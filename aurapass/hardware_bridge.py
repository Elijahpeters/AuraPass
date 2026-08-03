import os
import socket
import subprocess
import sys
import time

from .paths import LOGS_DIR, PROJECT_ROOT, ensure_directories


class HardwareBridge:
    def __init__(self, host=None, port=None):
        self.host = host or os.environ.get("AURAPASS_UDP_HOST", "127.0.0.1")
        self.port = int(port or os.environ.get("AURAPASS_UDP_PORT", "9090"))
        self.process = None
        self.log_file = None
        self.ensure_bridge()

    def ensure_bridge(self):
        if self._udp_port_in_use():
            return True, "Proteus bridge is already listening."

        ensure_directories()
        bridge_script = PROJECT_ROOT / "tools" / "proteus_bridge.py"
        log_path = LOGS_DIR / "proteus_bridge.log"
        python_exe = sys.executable
        self.log_file = open(log_path, "a", encoding="utf-8")
        self.process = subprocess.Popen(
            [python_exe, str(bridge_script)],
            cwd=str(PROJECT_ROOT),
            stdout=self.log_file,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        time.sleep(0.8)
        return self._udp_port_in_use(), f"Started Proteus bridge. Log: {log_path}"

    def _udp_port_in_use(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind((self.host, self.port))
            return False
        except OSError:
            return True
        finally:
            sock.close()

    def send(self, command):
        payload = (command.strip() + "\n").encode("utf-8")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.sendto(payload, (self.host, self.port))
            return True, f"UDP {self.host}:{self.port} <- {command.strip()}"
        except OSError as exc:
            return False, str(exc)
        finally:
            sock.close()

    def send_sequence(self, commands, delay_s=0.65):
        messages = []
        for index, command in enumerate(commands):
            ok, message = self.send(command)
            messages.append(message if ok else f"Hardware offline: {message}")
            if index < len(commands) - 1:
                time.sleep(delay_s)
        return True, " | ".join(messages)

    def stop_owned_bridge(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=3)
        if self.log_file and not self.log_file.closed:
            self.log_file.close()
