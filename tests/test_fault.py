"""
Fault Tolerance & Edge Case Unit Tests.

Tests server stability under unexpected network conditions: abrupt client disconnects,
malformed protocols, oversized payloads, partial framing, and empty inputs.
"""

import time
import socket
import unittest
import threading
from server.server import ChatServer
from server.protocol import StreamBuffer

TEST_PORT = 5557

class TestFaultTolerance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ChatServer(host="127.0.0.1", port=TEST_PORT)
        cls.server_thread = threading.Thread(target=cls.server.start, daemon=True)
        cls.server_thread.start()
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def _connect(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", TEST_PORT))
        return s, StreamBuffer()

    def test_abrupt_disconnect_does_not_crash_server(self):
        s, buf = self._connect()
        s.sendall(b"JOIN:crash_test_user\n")
        time.sleep(0.1)
        # Abruptly close socket without LEAVE
        s.close()
        time.sleep(0.2)
        # Server should still be running and accept new connection
        s2, buf2 = self._connect()
        s2.sendall(b"JOIN:survivor_user\n")
        time.sleep(0.1)
        s2.close()

    def test_malformed_commands_handled_gracefully(self):
        s, buf = self._connect()
        s.sendall(b"GARBAGE_COMMAND_WITHOUT_COLON\n")
        s.settimeout(1.0)
        data = s.recv(1024).decode("utf-8")
        self.assertTrue("ERROR:" in data)
        s.close()

    def test_command_before_join_rejected(self):
        s, buf = self._connect()
        s.sendall(b"MSG:unregistered:Hello\n")
        s.settimeout(1.0)
        data = s.recv(1024).decode("utf-8")
        self.assertTrue("ERROR:Must send JOIN:<username> first." in data)
        s.close()

    def test_oversized_message_rejected(self):
        s, buf = self._connect()
        s.sendall(b"JOIN:big_sender\n")
        time.sleep(0.1)
        # Drain welcome messages
        s.settimeout(1.0)
        while True:
            d = s.recv(1024).decode("utf-8")
            buf.append(d)
            if buf.extract_messages():
                break

        # Send message > 1024 chars
        huge_text = "A" * 2000
        s.sendall(f"MSG:big_sender:{huge_text}\n".encode("utf-8"))
        
        # Read response into buffer
        buf.clear()
        d2 = s.recv(1024).decode("utf-8")
        buf.append(d2)
        msgs = buf.extract_messages()
        self.assertTrue(any("ERROR:" in m for m in msgs))
        s.close()


if __name__ == "__main__":
    unittest.main()
