"""
Client Registry Manager with Thread Synchronization & Activity Tracker.

Manages connected clients, active socket mappings, activity timestamps, and inactivity timeouts.
Uses threading.Lock() to prevent race conditions when multiple client threads
register, disconnect, or broadcast messages concurrently.
"""

import time
import socket
import threading
from typing import Dict, List, Optional, Tuple, Any

class ClientManager:
    """
    Thread-safe client directory manager with activity monitoring.
    Stores registered clients as:
    {
       username: {
          "socket": socket_obj,
          "address": (ip, port),
          "connected_at": timestamp,
          "last_activity": timestamp,
          "sent_count": int,
          "recv_count": int
       }
    }
    """
    def __init__(self):
        self._clients: Dict[str, Dict[str, Any]] = {}
        self._total_messages_routed = 0
        self._lock = threading.Lock()

    def register_client(self, username: str, client_socket: socket.socket, client_address: Tuple[str, int] = ("127.0.0.1", 0)) -> Tuple[bool, str]:
        """
        Attempts to register a new user with metadata tracking.
        """
        now = time.time()
        with self._lock:
            if username in self._clients:
                return False, f"Username '{username}' is already taken."
            self._clients[username] = {
                "socket": client_socket,
                "address": client_address,
                "connected_at": now,
                "last_activity": now,
                "sent_count": 0,
                "recv_count": 0
            }
            return True, "Registration successful."

    def update_activity(self, username: str):
        """Refreshes last_activity timestamp for the given client."""
        with self._lock:
            if username in self._clients:
                self._clients[username]["last_activity"] = time.time()

    def unregister_client(self, username: str) -> Optional[socket.socket]:
        """
        Removes a client from registry and returns their socket if existed.
        """
        with self._lock:
            info = self._clients.pop(username, None)
            return info["socket"] if info else None

    def kick_client(self, username: str) -> Optional[socket.socket]:
        """
        Kicks a client by username, unregistering them and returning their socket.
        """
        return self.unregister_client(username)

    def cleanup_inactive_clients(self, timeout_seconds: float) -> List[Tuple[str, socket.socket]]:
        """
        Scans all registered clients and identifies any with last_activity older than timeout_seconds.
        Removes them from registry and returns list of (username, socket) tuples for graceful closing.
        """
        now = time.time()
        expired: List[Tuple[str, socket.socket]] = []

        with self._lock:
            usernames = list(self._clients.keys())
            for u in usernames:
                info = self._clients[u]
                idle_time = now - info["last_activity"]
                if idle_time > timeout_seconds:
                    sock = info["socket"]
                    expired.append((u, sock))
                    del self._clients[u]

        return expired

    def get_user_list(self) -> List[str]:
        """Returns a list of all currently connected usernames."""
        with self._lock:
            return list(self._clients.keys())

    def get_socket(self, username: str) -> Optional[socket.socket]:
        """Gets socket for a specific username."""
        with self._lock:
            info = self._clients.get(username)
            return info["socket"] if info else None

    def broadcast(self, raw_message: str, exclude_username: Optional[str] = None):
        """
        Sends raw_message to all connected clients except exclude_username.
        Iterates over a copy of active sockets under lock protection.
        """
        data = raw_message.encode("utf-8")
        targets: List[Tuple[str, socket.socket]] = []

        with self._lock:
            self._total_messages_routed += 1
            for user, info in self._clients.items():
                if user != exclude_username:
                    targets.append((user, info["socket"]))

        for user, sock in targets:
            try:
                sock.sendall(data)
                with self._lock:
                    if user in self._clients:
                        self._clients[user]["recv_count"] += 1
            except (socket.error, BrokenPipeError, ConnectionResetError):
                pass

    def send_direct(self, username: str, raw_message: str) -> bool:
        """
        Sends raw_message directly to a targeted user.
        Returns True if sent, False if user not found or socket failed.
        """
        target_sock = None
        with self._lock:
            self._total_messages_routed += 1
            info = self._clients.get(username)
            if info:
                target_sock = info["socket"]

        if not target_sock:
            return False

        try:
            target_sock.sendall(raw_message.encode("utf-8"))
            with self._lock:
                if username in self._clients:
                    self._clients[username]["recv_count"] += 1
            return True
        except (socket.error, BrokenPipeError, ConnectionResetError):
            return False

    def get_admin_stats(self) -> Dict[str, Any]:
        """
        Returns rich system stats for Admin Portal.
        """
        now = time.time()
        clients_info = []

        with self._lock:
            for user, info in self._clients.items():
                addr = info["address"]
                ip_str = f"{addr[0]}:{addr[1]}" if isinstance(addr, (list, tuple)) and len(addr) >= 2 else str(addr)
                clients_info.append({
                    "username": user,
                    "address": ip_str,
                    "connected_seconds": int(now - info["connected_at"]),
                    "idle_seconds": int(now - info["last_activity"]),
                    "sent_count": info["sent_count"],
                    "recv_count": info["recv_count"],
                })

            return {
                "active_client_count": len(self._clients),
                "total_messages_routed": self._total_messages_routed,
                "clients": clients_info
            }

    @property
    def client_count(self) -> int:
        """Return total number of active connections."""
        with self._lock:
            return len(self._clients)
