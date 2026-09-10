"""
Custom Application Protocol Parser & TCP Stream Framer.

Protocol Specification:
-----------------------
Commands are string-encoded and delimited by newline '\\n'.

Client -> Server:
  JOIN:<username>
  MSG:<sender>:<text>
  PRIVATE:<sender>:<target>:<text>
  WHO
  LEAVE:<username>

Server -> Client:
  JOIN:<username>                   (Broadcast notification)
  MSG:<sender>:<text>               (Broadcast text message)
  PRIVATE:<sender>:<target>:<text>  (Direct private message)
  WHOREPLY:<user1>,<user2>,...     (Online users list)
  LEAVE:<username>                  (Broadcast notification)
  ERROR:<reason>                    (Error feedback)
  SYSTEM:<message>                  (System broadcast info)
"""

from typing import List, Tuple, Optional
from server.config import DELIMITER, MAX_USERNAME_LEN, MAX_MESSAGE_LEN

class ProtocolError(Exception):
    """Raised when an incoming packet violates protocol specification."""
    pass

class StreamBuffer:
    """
    TCP Message Framing Accumulator.
    Accumulates raw byte chunks received via socket.recv() and extracts
    complete newline-delimited protocol messages.
    """
    def __init__(self):
        self._buffer = ""

    def append(self, data: str):
        """Append decoded string chunk to the internal buffer."""
        self._buffer += data

    def extract_messages(self) -> List[str]:
        """
        Extract all complete messages delimited by '\\n' from buffer.
        Leaves any incomplete trailing fragment in the buffer.
        """
        messages = []
        while DELIMITER in self._buffer:
            msg, self._buffer = self._buffer.split(DELIMITER, 1)
            msg = msg.strip('\r')  # Clean CR if present
            if msg:  # Ignore empty blank lines
                messages.append(msg)
        return messages

    def clear(self):
        """Reset internal buffer."""
        self._buffer = ""


# Message Encoder Helpers
def encode_join(username: str) -> str:
    return f"JOIN:{username}\n"

def encode_msg(sender: str, text: str) -> str:
    return f"MSG:{sender}:{text}\n"

def encode_private(sender: str, target: str, text: str) -> str:
    return f"PRIVATE:{sender}:{target}:{text}\n"

def encode_who() -> str:
    return "WHO\n"

def encode_whoreply(users: List[str]) -> str:
    user_str = ",".join(users)
    return f"WHOREPLY:{user_str}\n"

def encode_leave(username: str) -> str:
    return f"LEAVE:{username}\n"

def encode_error(reason: str) -> str:
    return f"ERROR:{reason}\n"

def encode_system(message: str) -> str:
    return f"SYSTEM:{message}\n"


# Message Parser
def parse_message(raw_msg: str) -> Tuple[str, List[str]]:
    """
    Parses a single newline-stripped protocol string.
    Returns a tuple of (command_type, args_list).
    
    Example:
      "JOIN:alice" -> ("JOIN", ["alice"])
      "MSG:alice:Hello world!" -> ("MSG", ["alice", "Hello world!"])
      "PRIVATE:alice:bob:Secret" -> ("PRIVATE", ["alice", "bob", "Secret"])
      "WHO" -> ("WHO", [])
    """
    if not raw_msg:
        raise ProtocolError("Empty message received")

    parts = raw_msg.split(":", 2)
    cmd = parts[0].upper()

    if cmd == "JOIN":
        raw_parts = raw_msg.split(":")
        if len(raw_parts) != 2 or not raw_parts[1].strip():
            raise ProtocolError("JOIN format invalid. Expected JOIN:<username>")
        username = raw_parts[1].strip()
        if len(username) > MAX_USERNAME_LEN:
            raise ProtocolError(f"Username exceeds maximum length of {MAX_USERNAME_LEN}")
        if "," in username:
            raise ProtocolError("Username cannot contain ','")
        return ("JOIN", [username])

    elif cmd == "MSG":
        if len(parts) < 3:
            raise ProtocolError("MSG format invalid. Expected MSG:sender:text")
        sender = parts[1]
        text = parts[2]
        if len(text) > MAX_MESSAGE_LEN:
            raise ProtocolError(f"Message exceeds maximum length of {MAX_MESSAGE_LEN}")
        return ("MSG", [sender, text])

    elif cmd == "PRIVATE":
        if len(parts) < 3:
            raise ProtocolError("PRIVATE format invalid. Expected PRIVATE:sender:target:text")
        sender = parts[1]
        remainder = parts[2]
        if ":" not in remainder:
            raise ProtocolError("PRIVATE format invalid. Expected PRIVATE:sender:target:text")
        target, text = remainder.split(":", 1)
        return ("PRIVATE", [sender, target, text])

    elif cmd == "WHO":
        return ("WHO", [])

    elif cmd == "LEAVE":
        username = parts[1] if len(parts) > 1 else ""
        return ("LEAVE", [username])

    else:
        raise ProtocolError(f"Unknown command type: '{cmd}'")
