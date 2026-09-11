"""
Unit tests for Web Bridge HTTP upload endpoint (/api/upload).
"""

import os
import json
import base64
import time
import unittest
import threading
import urllib.request
from http.server import HTTPServer
from web_bridge.bridge import BridgeHTTPRequestHandler, Session, SESSIONS, SESSIONS_LOCK, UPLOADS_DIR, ReusableHTTPServer
from server.server import ChatServer

TEST_TCP_PORT = 5568
TEST_WEB_PORT = 8098

class TestWebBridgeUpload(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start TCP Chat server
        cls.tcp_server = ChatServer(host="127.0.0.1", port=TEST_TCP_PORT)
        cls.tcp_thread = threading.Thread(target=cls.tcp_server.start, daemon=True)
        cls.tcp_thread.start()
        time.sleep(0.3)

        # Start Web Bridge HTTP server
        cls.web_server = ReusableHTTPServer(("127.0.0.1", TEST_WEB_PORT), BridgeHTTPRequestHandler)
        cls.web_thread = threading.Thread(target=cls.web_server.serve_forever, daemon=True)
        cls.web_thread.start()
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.web_server.shutdown()
        cls.tcp_server.stop()

    def test_file_upload_and_serve(self):
        # 1. Connect a web session via API
        connect_req = urllib.request.Request(
            f"http://127.0.0.1:{TEST_WEB_PORT}/api/connect",
            data=json.dumps({
                "username": "upload_test_user",
                "tcp_host": "127.0.0.1",
                "tcp_port": TEST_TCP_PORT
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(connect_req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["status"], "ok")
            session_id = data["session_id"]

        # 2. Upload file via /api/upload
        test_content = b"Hello, this is a test upload file content."
        b64_content = base64.b64encode(test_content).decode("utf-8")

        upload_req = urllib.request.Request(
            f"http://127.0.0.1:{TEST_WEB_PORT}/api/upload",
            data=json.dumps({
                "session_id": session_id,
                "filename": "test_document.txt",
                "file_data": b64_content
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(upload_req) as resp:
            up_data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(up_data["status"], "ok")
            self.assertEqual(up_data["filename"], "test_document.txt")
            self.assertEqual(up_data["size"], len(test_content))
            file_url = up_data["url"]

        # 3. Retrieve uploaded file over HTTP GET
        with urllib.request.urlopen(f"http://127.0.0.1:{TEST_WEB_PORT}{file_url}") as get_resp:
            retrieved_content = get_resp.read()
            self.assertEqual(retrieved_content, test_content)

        # 4. Disconnect session
        disc_req = urllib.request.Request(
            f"http://127.0.0.1:{TEST_WEB_PORT}/api/disconnect",
            data=json.dumps({"session_id": session_id}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(disc_req) as resp:
            disc_data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(disc_data["status"], "ok")


if __name__ == "__main__":
    unittest.main()
