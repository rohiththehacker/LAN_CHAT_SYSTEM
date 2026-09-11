"""
System configuration for LAN Chat System.
Contains default network settings, buffer limits, and LAN IP detection.
"""

import socket

DEFAULT_HOST = "0.0.0.0"
DEFAULT_TCP_PORT = 5555
DEFAULT_WEB_PORT = 8080

BUFFER_SIZE = 4096
ENCODING = "utf-8"

# Protocol limits
MAX_USERNAME_LEN = 32
MAX_MESSAGE_LEN = 1024
DELIMITER = "\n"

# Inactivity & Admin settings
DEFAULT_INACTIVITY_TIMEOUT = 900  # 15 minutes in seconds (10-20 mins range)
DEFAULT_ADMIN_KEY = "admin123"

def get_lan_ip() -> str:
    """
    Utility function to discover the local machine's primary LAN IP address.
    Connects a dummy UDP socket to a non-routable address to determine the outward interface.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Dummy connect to determine outgoing LAN interface IP (doesn't send data)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip
