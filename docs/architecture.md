# LAN Chat System - Architecture Documentation

## Overview
The **LAN Chat System** is designed as a classic multi-client TCP/IP client-server network application. The architecture strictly separates the **TCP Networking Core** (Python standard socket API) from the **Web Dashboard Presentation Layer**, linked together via a lightweight **Web-to-TCP Bridge**.

---

## High-Level Architecture Diagram

```
                    +---------------------------------------------+
                    |             SAME LOCAL AREA NETWORK         |
                    +---------------------------------------------+
                                   |               |
                   (TCP Connection :5555)    (HTTP/WS Dashboard :8080)
                                   |               |
                                   v               v
            +---------------------------+    +----------------------------+
            |    Python TCP Chat Server |    |  Web Bridge HTTP Server    |
            |     (0.0.0.0:5555)        |    |    (0.0.0.0:8080)          |
            +---------------------------+    +----------------------------+
                           |                               |
              Main Thread: accept()                        | Opens TCP Socket Client
                           |                               | per browser session
                           v                               v
            +---------------------------+    +----------------------------+
            | Client Thread 1   (Alice) |<---|  Web Client 1 (Laptop A)   |
            | Client Thread 2   (Bob)   |<---|  Web Client 2 (Phone B)    |
            | Client Thread 3   (Eve)   |<---|  CLI Client 3 (Localhost)  |
            +---------------------------+    +----------------------------+
                           |
                           v
            +-------------------------------------------------------------+
            |             ClientManager (Registry & Mutex Lock)           |
            |  - Active Sockets: {"Alice": sock1, "Bob": sock2, ...}      |
            |  - Synchronization: threading.Lock()                        |
            +-------------------------------------------------------------+
```

---

## Key Components

### 1. Standalone Python TCP Server (`server/server.py`)
- **Transport Protocol**: Transmission Control Protocol (TCP) (`socket.AF_INET`, `socket.SOCK_STREAM`).
- **Interface Binding**: `0.0.0.0:5555`. Binding to `0.0.0.0` allows the server socket to listen on all IPv4 addresses assigned to local network interface cards (NICs), enabling access from `localhost` and remote devices on the same Wi-Fi subnet.
- **Concurrency Architecture**: Dedicated thread per client (`threading.Thread`). The main thread runs a blocking `accept()` loop and offloads incoming client socket read loops to worker threads.

### 2. Client Manager & Concurrency Synchronization (`server/client_manager.py`)
- **Shared State**: Dictionary mapping `username -> socket_object`.
- **Race Condition Prevention**: All operations (joining, leaving, reading online list, iterating sockets during broadcast) are protected using Python's `threading.Lock()` mutex.
- **Atomicity**: Prevents race conditions where one thread deletes a client while another thread iterates over the socket registry during a broadcast.

### 3. Application Protocol & TCP Framing (`server/protocol.py`)
- **Byte Stream Challenge**: TCP provides a continuous stream of bytes without message boundaries. One `send()` call on the client does not necessarily correspond to one `recv()` call on the server.
- **Framing Solution**: All application commands end with a newline character (`\n`). Each client thread maintains a string buffer (`StreamBuffer`) that accumulates raw chunks from `recv()` and extracts complete commands separated by `\n`.

### 4. Local Web Dashboard & Web-to-TCP Bridge (`web_bridge/bridge.py` & `dashboard/`)
- **Browser Sandboxing Rationale**: Client-side JavaScript running in web browsers cannot execute raw TCP socket calls (`socket.socket()`).
- **Bridge Solution**: The Web Bridge serves static HTML/CSS/JS files on port `8080` and translates HTTP requests into **real TCP socket client connections** to port `5555`.
- Each browser tab gets its own dedicated underlying Python TCP client socket.
