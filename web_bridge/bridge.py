"""
Web-to-TCP Bridge & Local Dashboard HTTP Server.

Hosts the Web Dashboard on 0.0.0.0:8080 and bridges browser HTTP requests to
genuine raw TCP socket connections on the Python Chat Server (0.0.0.0:5555).
Uses standard Python library (http.server, socket, threading, queue).
"""

import os
import sys
import json
import uuid
import queue
import socket
import threading
import logging
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Dict, Any

from server.config import (
    DEFAULT_HOST,
    DEFAULT_TCP_PORT,
    DEFAULT_WEB_PORT,
    BUFFER_SIZE,
    ENCODING,
    get_lan_ip,
)
from server.protocol import StreamBuffer

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [WebBridge] %(levelname)s: %(message)s")
logger = logging.getLogger("WebBridge")

DASHBOARD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dashboard")
UPLOADS_DIR = os.path.join(DASHBOARD_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

# Active Web Sessions Directory: {session_id: SessionObject}
SESSIONS: Dict[str, Dict[str, Any]] = {}
SESSIONS_LOCK = threading.Lock()


class Session:
    """Represents a Web client's dedicated underlying TCP socket client."""
    def __init__(self, username: str, tcp_host: str, tcp_port: int):
        self.session_id = str(uuid.uuid4())
        self.username = username
        self.tcp_host = tcp_host
        self.tcp_port = tcp_port
        self.sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.msg_queue: queue.Queue = queue.Queue()
        self.is_connected = False
        self.buffer = StreamBuffer()
        self.receiver_thread = None

    def connect(self) -> tuple[bool, str]:
        try:
            self.sock.connect((self.tcp_host, self.tcp_port))
            # Send JOIN request over TCP socket
            join_cmd = f"JOIN:{self.username}\n"
            self.sock.sendall(join_cmd.encode(ENCODING))
            self.is_connected = True

            # Start background reader thread for this TCP socket
            self.receiver_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.receiver_thread.start()
            return True, "Connected to TCP server"
        except Exception as e:
            return False, f"Failed to connect to TCP server: {str(e)}"

    def _read_loop(self):
        """Continuously reads bytes from TCP socket and queues incoming protocol messages."""
        try:
            while self.is_connected:
                raw_bytes = self.sock.recv(BUFFER_SIZE)
                if not raw_bytes:
                    break
                self.buffer.append(raw_bytes.decode(ENCODING, errors="replace"))
                msgs = self.buffer.extract_messages()
                for m in msgs:
                    self.msg_queue.put(m)
        except Exception:
            pass
        finally:
            self.is_connected = False
            self.msg_queue.put("SYSTEM:Disconnected from TCP server.")

    def send_command(self, raw_command: str) -> bool:
        if not self.is_connected:
            return False
        try:
            if not raw_command.endswith("\n"):
                raw_command += "\n"
            self.sock.sendall(raw_command.encode(ENCODING))
            return True
        except Exception:
            self.is_connected = False
            return False

    def close(self):
        self.is_connected = False
        try:
            self.send_command(f"LEAVE:{self.username}\n")
            self.sock.close()
        except Exception:
            pass


class BridgeHTTPRequestHandler(SimpleHTTPRequestHandler):
    """HTTP Request Handler serving Dashboard UI files & Web-to-TCP API."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DASHBOARD_DIR, **kwargs)

    def do_GET(self):
        if self.path == "/api/config":
            lan_ip = get_lan_ip()
            self._send_json({
                "status": "ok",
                "lan_ip": lan_ip,
                "tcp_port": DEFAULT_TCP_PORT,
                "web_port": DEFAULT_WEB_PORT,
            })
        elif self.path.startswith("/api/poll"):
            self._handle_poll()
        else:
            # Serve dashboard static files (index.html, style.css, app.js)
            super().do_GET()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length)
        
        try:
            data = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except Exception:
            data = {}

        if self.path == "/api/connect":
            username = data.get("username", "").strip()
            tcp_host = data.get("tcp_host", "127.0.0.1")
            tcp_port = int(data.get("tcp_port", DEFAULT_TCP_PORT))

            if not username:
                self._send_json({"status": "error", "message": "Username is required"}, status=400)
                return

            sess = Session(username, tcp_host, tcp_port)
            success, msg = sess.connect()

            if success:
                with SESSIONS_LOCK:
                    SESSIONS[sess.session_id] = sess
                self._send_json({
                    "status": "ok",
                    "session_id": sess.session_id,
                    "username": username,
                    "message": msg,
                })
            else:
                self._send_json({"status": "error", "message": msg}, status=500)

        elif self.path == "/api/send":
            session_id = data.get("session_id")
            command = data.get("command")

            with SESSIONS_LOCK:
                sess = SESSIONS.get(session_id)

            if not sess or not sess.is_connected:
                self._send_json({"status": "error", "message": "Session inactive or disconnected"}, status=401)
                return

            sent = sess.send_command(command)
            if sent:
                self._send_json({"status": "ok"})
            else:
                self._send_json({"status": "error", "message": "Failed to send over TCP socket"}, status=500)

        elif self.path == "/api/disconnect":
            session_id = data.get("session_id")
            with SESSIONS_LOCK:
                sess = SESSIONS.pop(session_id, None)

            if sess:
                sess.close()
            self._send_json({"status": "ok"})

        elif self.path == "/api/upload":
            session_id = data.get("session_id")
            filename = data.get("filename", "uploaded_file")
            file_data_b64 = data.get("file_data", "")

            with SESSIONS_LOCK:
                sess = SESSIONS.get(session_id)

            if not sess or not sess.is_connected:
                self._send_json({"status": "error", "message": "Session inactive or disconnected"}, status=401)
                return

            if not file_data_b64:
                self._send_json({"status": "error", "message": "No file data provided"}, status=400)
                return

            try:
                import base64
                import time

                file_bytes = base64.b64decode(file_data_b64)
                if len(file_bytes) > 10 * 1024 * 1024:
                    self._send_json({"status": "error", "message": "File size exceeds 10 MB limit"}, status=400)
                    return

                safe_basename = os.path.basename(filename).replace(" ", "_")
                unique_name = f"{int(time.time())}_{safe_basename}"
                file_path = os.path.join(UPLOADS_DIR, unique_name)

                with open(file_path, "wb") as f:
                    f.write(file_bytes)

                file_url = f"/uploads/{unique_name}"
                self._send_json({
                    "status": "ok",
                    "filename": filename,
                    "url": file_url,
                    "size": len(file_bytes)
                })
            except Exception as e:
                self._send_json({"status": "error", "message": f"Upload failed: {str(e)}"}, status=500)

        else:
            self._send_json({"status": "error", "message": "Not found"}, status=404)

    def _handle_poll(self):
        query = self.path.split("?", 1)[-1] if "?" in self.path else ""
        session_id = None
        for q in query.split("&"):
            if q.startswith("session_id="):
                session_id = q.split("=", 1)[1]

        with SESSIONS_LOCK:
            sess = SESSIONS.get(session_id)

        if not sess:
            self._send_json({"status": "error", "message": "Invalid session"}, status=401)
            return

        messages = []
        # Non-blocking collect queued protocol messages
        while not sess.msg_queue.empty():
            try:
                messages.append(sess.msg_queue.get_nowait())
            except queue.Empty:
                break

        self._send_json({
            "status": "ok",
            "is_connected": sess.is_connected,
            "messages": messages,
        })

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Quiet standard HTTP request logs to keep terminal readable
        pass


def run_bridge(web_port: int = DEFAULT_WEB_PORT):
    server_address = (DEFAULT_HOST, web_port)
    httpd = HTTPServer(server_address, BridgeHTTPRequestHandler)
    lan_ip = get_lan_ip()
    
    logger.info("=" * 60)
    logger.info(" WEB DASHBOARD BRIDGE STARTED")
    logger.info(f" Local Browser Access : http://localhost:{web_port}")
    logger.info(f" LAN Network Access   : http://{lan_ip}:{web_port}")
    logger.info("=" * 60)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down Web Dashboard Bridge...")
        httpd.server_close()


if __name__ == "__main__":
    web_port = DEFAULT_WEB_PORT
    if len(sys.argv) > 1:
        try:
            web_port = int(sys.argv[1])
        except ValueError:
            pass
    run_bridge(web_port=web_port)
