"""
Client Registry Manager with Thread Synchronization.

Manages connected clients and active socket mappings.
Uses threading.Lock() to prevent race conditions when multiple client threads
register, disconnect, or broadcast messages concurrently.
"""

import socket
import threading
from typing import Dict, List, Optional, Tuple

class ClientManager:
    """
    Thread-safe client directory manager.
    Stores registered clients as {username: socket_object}.
    """
    def __init__(self):
        self._clients: Dict[str, socket.socket] = {}
        self._lock = threading.Lock()

    def register_client(self, username: str, client_socket: socket.socket) -> Tuple[bool, str]:
        """
        Attempts to register a new user.
        Thread-safe: standard lock ensures atomicity when checking duplicates.
        """
        with self._lock:
            if username in self._clients:
                return False, f"Username '{username}' is already taken."
            self._clients[username] = client_socket
            return True, "Registration successful."

    def unregister_client(self, username: str) -> Optional[socket.socket]:
        """
        Removes a client from registry and returns their socket if existed.
        """
        with self._lock:
            return self._clients.pop(username, None)

    def get_user_list(self) -> List[str]:
        """Returns a list of all currently connected usernames."""
        with self._lock:
            return list(self._clients.keys())

    def get_socket(self, username: str) -> Optional[socket.socket]:
        """Gets socket for a specific username."""
        with self._lock:
            return self._clients.get(username)

    def broadcast(self, raw_message: str, exclude_username: Optional[str] = None):
        """
        Sends raw_message to all connected clients except exclude_username.
        Iterates over a copy of active sockets under lock protection.
        """
        data = raw_message.encode("utf-8")
        targets: List[Tuple[str, socket.socket]] = []

        with self._lock:
            for user, sock in self._clients.items():
                if user != exclude_username:
                    targets.append((user, sock))

        for user, sock in targets:
            try:
                sock.sendall(data)
            except (socket.error, BrokenPipeError, ConnectionResetError):
                # Socket error during broadcast will be handled by client's receiver thread
                pass

    def send_direct(self, username: str, raw_message: str) -> bool:
        """
        Sends raw_message directly to a targeted user.
        Returns True if sent, False if user not found or socket failed.
        """
        target_sock = None
        with self._lock:
            target_sock = self._clients.get(username)

        if not target_sock:
            return False

        try:
            target_sock.sendall(raw_message.encode("utf-8"))
            return True
        except (socket.error, BrokenPipeError, ConnectionResetError):
            return False

    @property
    def client_count(self) -> int:
        """Return total number of active connections."""
        with self._lock:
            return len(self._clients)
