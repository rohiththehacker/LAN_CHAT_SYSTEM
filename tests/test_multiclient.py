"""
Multi-Client Concurrency Integration Tests.

Launches a live ChatServer instance on a temporary test port, connects multiple
concurrent TCP socket clients, tests broadcast, private messaging, WHO listing,
and duplicate user rejection.
"""

import time
import socket
import unittest
import threading
from server.server import ChatServer
from server.protocol import StreamBuffer

TEST_PORT = 5556

class TestMultiClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ChatServer(host="127.0.0.1", port=TEST_PORT)
        cls.server_thread = threading.Thread(target=cls.server.start, daemon=True)
        cls.server_thread.start()
        time.sleep(0.3)  # Allow server socket to bind & listen

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def _connect_client(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", TEST_PORT))
        return s, StreamBuffer()

    def _read_all(self, sock: socket.socket, buffer: StreamBuffer, min_count: int = 1, timeout: float = 1.0):
        sock.settimeout(timeout)
        all_msgs = []
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                data = sock.recv(1024)
                if not data:
                    break
                buffer.append(data.decode("utf-8"))
                msgs = buffer.extract_messages()
                all_msgs.extend(msgs)
                if len(all_msgs) >= min_count:
                    break
            except socket.timeout:
                break
        return all_msgs

    def test_single_client_join(self):
        sock, buf = self._connect_client()
        sock.sendall(b"JOIN:alice\n")
        msgs = self._read_all(sock, buf, min_count=2)
        self.assertTrue(any("SYSTEM:Welcome to LAN Chat" in m for m in msgs))
        self.assertTrue(any("WHOREPLY:alice" in m for m in msgs))
        sock.close()

    def test_duplicate_username_rejected(self):
        sock1, buf1 = self._connect_client()
        sock1.sendall(b"JOIN:bob\n")
        self._read_all(sock1, buf1)

        sock2, buf2 = self._connect_client()
        sock2.sendall(b"JOIN:bob\n")
        msgs2 = self._read_all(sock2, buf2)
        self.assertTrue(any("ERROR:Username 'bob' is already taken." in m for m in msgs2))
        
        sock1.close()
        sock2.close()

    def test_broadcast_and_private_messaging(self):
        # Connect Client 1 (charlie)
        s1, b1 = self._connect_client()
        s1.sendall(b"JOIN:charlie\n")
        self._read_all(s1, b1)

        # Connect Client 2 (david)
        s2, b2 = self._connect_client()
        s2.sendall(b"JOIN:david\n")
        self._read_all(s2, b2)

        # Connect Client 3 (eve)
        s3, b3 = self._connect_client()
        s3.sendall(b"JOIN:eve\n")
        self._read_all(s3, b3)

        # Test Broadcast: charlie sends broadcast
        s1.sendall(b"MSG:charlie:Hello everyone!\n")
        time.sleep(0.1)

        msgs2 = self._read_all(s2, b2)
        msgs3 = self._read_all(s3, b3)
        self.assertTrue(any("MSG:charlie:Hello everyone!" in m for m in msgs2))
        self.assertTrue(any("MSG:charlie:Hello everyone!" in m for m in msgs3))

        # Test Private Message: charlie PMs david
        s1.sendall(b"PRIVATE:charlie:david:Secret message for David only\n")
        time.sleep(0.1)

        msgs_d = self._read_all(s2, b2)
        msgs_e = self._read_all(s3, b3)

        # David should receive the private message
        self.assertTrue(any("PRIVATE:charlie:david:Secret message for David only" in m for m in msgs_d))
        # Eve should NOT receive the private message
        self.assertFalse(any("Secret message" in m for m in msgs_e))

        s1.close()
        s2.close()
        s3.close()


if __name__ == "__main__":
    unittest.main()
