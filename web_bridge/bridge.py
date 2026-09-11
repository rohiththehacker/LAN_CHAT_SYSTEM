"""
Web-to-TCP Bridge & Local Dashboard HTTP Server with Inactivity Monitoring & Admin Portal.

Hosts the Web Dashboard on 0.0.0.0:8080 and bridges browser HTTP requests to
genuine raw TCP socket connections on the Python Chat Server (0.0.0.0:5555).
Includes inactivity timeout auto-pruning and admin management REST APIs.
"""

import os
import sys
import time
import json
import uuid
import queue
import socket
import threading
import logging
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Dict, Any, List

from server.config import (
    DEFAULT_HOST,
    DEFAULT_TCP_PORT,
    DEFAULT_WEB_PORT,
    DEFAULT_INACTIVITY_TIMEOUT,
    DEFAULT_ADMIN_KEY,
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

# Global Admin State
ADMIN_SETTINGS = {
    "key": DEFAULT_ADMIN_KEY,
    "timeout_seconds": DEFAULT_INACTIVITY_TIMEOUT,
    "start_time": time.time(),
    "messages_routed": 0
}


class Session:
    """Represents a Web client's dedicated underlying TCP socket client with activity monitoring."""
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
        self.connected_at = time.time()
        self.last_activity = time.time()

    def connect(self) -> tuple[bool, str]:
        try:
            self.sock.connect((self.tcp_host, self.tcp_port))
            join_cmd = f"JOIN:{self.username}\n"
            self.sock.sendall(join_cmd.encode(ENCODING))
            self.is_connected = True
            self.last_activity = time.time()

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
            self.last_activity = time.time()
            with SESSIONS_LOCK:
                ADMIN_SETTINGS["messages_routed"] += 1
            return True
        except Exception:
            self.is_connected = False
            return False

    def close(self, reason: str = "LEAVE"):
        self.is_connected = False
        try:
            if reason == "KICK":
                self.send_command(f"SYSTEM:You were kicked by server administrator.\n")
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
                "inactivity_timeout": ADMIN_SETTINGS["timeout_seconds"],
            })
        elif self.path.startswith("/api/poll"):
            self._handle_poll()
        elif self.path.startswith("/api/admin/stats"):
            self._handle_admin_stats()
        else:
            # Serve dashboard static files (index.html, style.css, app.js, admin.html, admin.js)
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

        # --- ADMIN PORTAL API ENDPOINTS ---
        elif self.path == "/api/admin/login":
            key = data.get("admin_key", "")
            if key == ADMIN_SETTINGS["key"]:
                self._send_json({"status": "ok", "message": "Authenticated"})
            else:
                self._send_json({"status": "error", "message": "Invalid Admin Access Key"}, status=401)

        elif self.path == "/api/admin/kick":
            if not self._check_admin_auth(data):
                return
            target_username = data.get("username")
            kicked = False

            with SESSIONS_LOCK:
                matching_ids = [sid for sid, s in SESSIONS.items() if s.username == target_username]
                for sid in matching_ids:
                    s = SESSIONS.pop(sid)
                    s.close(reason="KICK")
                    kicked = True

            if kicked:
                logger.info(f"Admin kicked client '{target_username}'")
                self._send_json({"status": "ok", "message": f"User '{target_username}' kicked"})
            else:
                self._send_json({"status": "error", "message": f"User '{target_username}' not found"}, status=444)

        elif self.path == "/api/admin/broadcast":
            if not self._check_admin_auth(data):
                return
            announcement = data.get("message", "").strip()
            if not announcement:
                self._send_json({"status": "error", "message": "Message empty"}, status=400)
                return

            broadcast_msg = f"SYSTEM:📢 Admin Announcement: {announcement}"
            count = 0
            with SESSIONS_LOCK:
                for sess in SESSIONS.values():
                    if sess.is_connected:
                        sess.msg_queue.put(broadcast_msg)
                        count += 1

            self._send_json({"status": "ok", "message": f"Broadcast sent to {count} sessions"})

        elif self.path == "/api/admin/config":
            if not self._check_admin_auth(data):
                return
            new_timeout = int(data.get("timeout_seconds", 900))
            ADMIN_SETTINGS["timeout_seconds"] = new_timeout
            logger.info(f"Admin updated inactivity timeout threshold to {new_timeout}s")
            self._send_json({"status": "ok", "timeout_seconds": new_timeout})

        else:
            self._send_json({"status": "error", "message": "Not found"}, status=404)

    def _check_admin_auth(self, data: dict) -> bool:
        key = data.get("admin_key", "")
        if key != ADMIN_SETTINGS["key"]:
            self._send_json({"status": "error", "message": "Unauthorized Admin Request"}, status=401)
            return False
        return True

    def _handle_admin_stats(self):
        query = self.path.split("?", 1)[-1] if "?" in self.path else ""
        key = ""
        for q in query.split("&"):
            if q.startswith("admin_key="):
                key = q.split("=", 1)[1]

        if key != ADMIN_SETTINGS["key"]:
            self._send_json({"status": "error", "message": "Unauthorized Admin Request"}, status=401)
            return

        now = time.time()
        clients = []

        with SESSIONS_LOCK:
            for sid, sess in SESSIONS.items():
                clients.append({
                    "session_id": sid,
                    "username": sess.username,
                    "tcp_address": f"{sess.tcp_host}:{sess.tcp_port}",
                    "connected_seconds": int(now - sess.connected_at),
                    "idle_seconds": int(now - sess.last_activity),
                    "is_connected": sess.is_connected
                })

            self._send_json({
                "status": "ok",
                "active_sessions": len(SESSIONS),
                "messages_routed": ADMIN_SETTINGS["messages_routed"],
                "uptime_seconds": int(now - ADMIN_SETTINGS["start_time"]),
                "inactivity_timeout": ADMIN_SETTINGS["timeout_seconds"],
                "clients": clients
            })

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

        now = time.time()
        # Inactivity auto-pruning check
        timeout = ADMIN_SETTINGS["timeout_seconds"]
        if timeout > 0 and (now - sess.last_activity) > timeout:
            sess.msg_queue.put(f"SYSTEM:Disconnected due to inactivity ({int(timeout/60)} mins idle).")
            sess.close()
            with SESSIONS_LOCK:
                SESSIONS.pop(session_id, None)
            self._send_json({"status": "ok", "is_connected": False, "messages": ["SYSTEM:Disconnected due to inactivity."]})
            return

        sess.last_activity = now

        messages = []
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
        pass


class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True


def run_bridge(web_port: int = DEFAULT_WEB_PORT):
    server_address = (DEFAULT_HOST, web_port)
    httpd = ReusableHTTPServer(server_address, BridgeHTTPRequestHandler)
    lan_ip = get_lan_ip()
    
    logger.info("=" * 60)
    logger.info(" WEB DASHBOARD BRIDGE STARTED")
    logger.info(f" Local Browser Access : http://localhost:{web_port}")
    logger.info(f" LAN Network Access   : http://{lan_ip}:{web_port}")
    logger.info(f" Admin Portal Access  : http://localhost:{web_port}/admin.html")
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
