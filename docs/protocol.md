# Custom Application Protocol Specification

## Application Layer Protocol (LAN-CHAT-v1)

The **LAN Chat System** uses a custom text-based application protocol built on top of TCP byte streams.

---

## 1. Framing Mechanism (Delimiter-Based Framing)

TCP is a **stream-oriented transport protocol**, meaning it guarantees ordered, reliable byte delivery, but does **not preserve message boundaries**. 

For example, if a client sends:
```
JOIN:alice\nMSG:alice:Hello!\n
```
The server's `recv()` might receive:
- The entire string in 1 `recv()` call, OR
- `"JOIN:ali"` in the 1st `recv()` call, and `"ce\nMSG:alice:Hello!\n"` in the 2nd `recv()` call.

To solve this, our protocol uses **newline-delimited framing** (`\n`). 
Each client connection runs a `StreamBuffer` that accumulates incoming string fragments until a `\n` is encountered, ensuring complete messages are dispatched for execution.

---

## 2. Command Set Reference

### Client -> Server Commands

| Command | Syntax | Description | Example |
| :--- | :--- | :--- | :--- |
| **JOIN** | `JOIN:<username>\n` | Registers username on the TCP server | `JOIN:alice\n` |
| **MSG** | `MSG:<sender>:<text>\n` | Broadcasts a message to all connected clients | `MSG:alice:Hello world!\n` |
| **PRIVATE** | `PRIVATE:<sender>:<target>:<text>\n` | Sends a direct private message to a target user | `PRIVATE:alice:bob:Secret\n` |
| **WHO** | `WHO\n` | Requests list of all online usernames | `WHO\n` |
| **LEAVE** | `LEAVE:<username>\n` | Gracefully disconnects client from server | `LEAVE:alice\n` |

### Server -> Client Responses

| Response | Syntax | Description | Example |
| :--- | :--- | :--- | :--- |
| **JOIN** | `JOIN:<username>\n` | Broadcast notification that a new user joined | `JOIN:bob\n` |
| **MSG** | `MSG:<sender>:<text>\n` | Broadcast text message received from a peer | `MSG:alice:Hello!\n` |
| **PRIVATE** | `PRIVATE:<sender>:<target>:<text>\n` | Direct private message delivered to target user | `PRIVATE:alice:bob:Secret\n` |
| **WHOREPLY** | `WHOREPLY:<user1>,<user2>,...\n` | Comma-separated list of currently connected users | `WHOREPLY:alice,bob\n` |
| **LEAVE** | `LEAVE:<username>\n` | Broadcast notification that a user disconnected | `LEAVE:alice\n` |
| **ERROR** | `ERROR:<reason>\n` | Sent when a command fails or violates protocol | `ERROR:Username taken\n` |
| **SYSTEM** | `SYSTEM:<message>\n` | Server system information message | `SYSTEM:Welcome!\n` |

---

## 3. Protocol Rules & Validation Constraints
- Usernames must be between 1 and 32 characters long.
- Usernames cannot contain colons (`:`) or commas (`,`).
- Messages cannot exceed 1024 characters.
- Unregistered clients attempting to send `MSG`, `PRIVATE`, or `WHO` before `JOIN` receive an `ERROR` packet.
