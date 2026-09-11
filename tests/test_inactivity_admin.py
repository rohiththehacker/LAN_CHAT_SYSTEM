"""
Unit tests for Inactivity Timeout Monitoring and Admin Portal REST APIs.
"""

import time
import json
import unittest
import threading
import urllib.request
from http.server import HTTPServer

from server.server import ChatServer
from server.client_manager import ClientManager
from web_bridge.bridge import BridgeHTTPRequestHandler, SESSIONS, ADMIN_SETTINGS, Session, SESSIONS_LOCK, UPLOADS_DIR, ReusableHTTPServer

TEST_TCP_PORT = 5570
TEST_WEB_PORT = 8099

class TestInactivityAndAdmin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 1. Start TCP Chat Server
        cls.tcp_server = ChatServer(host="127.0.0.1", port=TEST_TCP_PORT)
        cls.tcp_server.inactivity_timeout = 2  # 2 seconds timeout for fast test execution
        cls.tcp_thread = threading.Thread(target=cls.tcp_server.start, daemon=True)
        cls.tcp_thread.start()
        time.sleep(0.3)

        # 2. Start Web Bridge HTTP Server
        cls.web_server = ReusableHTTPServer(("127.0.0.1", TEST_WEB_PORT), BridgeHTTPRequestHandler)
        cls.web_thread = threading.Thread(target=cls.web_server.serve_forever, daemon=True)
        cls.web_thread.start()
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.web_server.shutdown()
        cls.tcp_server.stop()

    def test_client_manager_activity_and_cleanup(self):
        cm = ClientManager()
        dummy_sock = None
        cm.register_client("idle_user", dummy_sock)
        
        # Initially not expired with 10s timeout
        expired = cm.cleanup_inactive_clients(10.0)
        self.assertEqual(len(expired), 0)

        # Force last_activity to 20 seconds ago
        with cm._lock:
            cm._clients["idle_user"]["last_activity"] = time.time() - 20.0

        # Now cleanup with 10s timeout should catch idle_user
        expired = cm.cleanup_inactive_clients(10.0)
        self.assertEqual(len(expired), 1)
        self.assertEqual(expired[0][0], "idle_user")

    def test_admin_api_flow(self):
        # 1. Admin Login Verification
        login_req = urllib.request.Request(
            f"http://127.0.0.1:{TEST_WEB_PORT}/api/admin/login",
            data=json.dumps({"admin_key": "admin123"}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(login_req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["status"], "ok")

        # 2. Connect a client session
        conn_req = urllib.request.Request(
            f"http://127.0.0.1:{TEST_WEB_PORT}/api/connect",
            data=json.dumps({
                "username": "admin_target_user",
                "tcp_host": "127.0.0.1",
                "tcp_port": TEST_TCP_PORT
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(conn_req) as resp:
            conn_data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(conn_data["status"], "ok")

        # 3. Fetch Admin Stats
        stats_req = urllib.request.Request(
            f"http://127.0.0.1:{TEST_WEB_PORT}/api/admin/stats?admin_key=admin123"
        )
        with urllib.request.urlopen(stats_req) as resp:
            stats_data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(stats_data["status"], "ok")
            self.assertGreaterEqual(stats_data["active_sessions"], 1)

        # 4. Admin Broadcast Announcement
        bc_req = urllib.request.Request(
            f"http://127.0.0.1:{TEST_WEB_PORT}/api/admin/broadcast",
            data=json.dumps({
                "admin_key": "admin123",
                "message": "System Maintenance Notice"
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(bc_req) as resp:
            bc_data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(bc_data["status"], "ok")

        # 5. Admin Kick User
        kick_req = urllib.request.Request(
            f"http://127.0.0.1:{TEST_WEB_PORT}/api/admin/kick",
            data=json.dumps({
                "admin_key": "admin123",
                "username": "admin_target_user"
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(kick_req) as resp:
            kick_data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(kick_data["status"], "ok")

        # 6. Admin Update Timeout Setting
        cfg_req = urllib.request.Request(
            f"http://127.0.0.1:{TEST_WEB_PORT}/api/admin/config",
            data=json.dumps({
                "admin_key": "admin123",
                "timeout_seconds": 600
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(cfg_req) as resp:
            cfg_data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(cfg_data["status"], "ok")
            self.assertEqual(cfg_data["timeout_seconds"], 600)


if __name__ == "__main__":
    unittest.main()
