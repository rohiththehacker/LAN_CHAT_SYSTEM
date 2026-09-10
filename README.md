# LAN CHAT SYSTEM
> **A Real-Time Multi-Client Communication System over a Local Area Network (LAN)**  
> *Academic Computer Networks & Cybersecurity Engineering Project*

---

## ⚡ Overview
**LAN Chat System** is a full-featured, fault-tolerant, multi-client chat system designed to demonstrate fundamental Computer Networks concepts: **TCP socket programming**, **multi-threading**, **mutex lock synchronization**, **custom application-layer protocol framing**, and **LAN network routing**.

The project features a **pure Python TCP socket server** backend and a **modern dark technical Web Dashboard** UI accessible from any device connected to the same Wi-Fi/LAN network.

---

## 🚀 Key Demonstration Features
- **TCP Socket Backend**: Built using raw Python `socket` API (`AF_INET`, `SOCK_STREAM`).
- **Multi-Client Concurrency**: Handles multiple simultaneous client connections using `threading.Thread`.
- **Race Condition Prevention**: Synchronizes shared client state via `threading.Lock()` mutex locks.
- **Byte Stream Message Framing**: Resolves TCP stream boundary ambiguity using newline delimiters (`\n`) and stream accumulation buffers.
- **Custom Application Protocol**:
  - `JOIN:<username>` — User registration & duplicate check.
  - `MSG:<sender>:<text>` — Global broadcast messaging.
  - `PRIVATE:<sender>:<target>:<text>` — Direct private messaging (`/pm`).
  - `WHO` — Real-time online user listing (`WHOREPLY`).
  - `LEAVE:<username>` — Graceful disconnect notifications.
- **Fault Tolerance**: Resilient against abrupt client connection drops, malformed packets, empty inputs, and oversized payloads.
- **LAN Web Dashboard**: Locally hosted Web UI (`0.0.0.0:8080`) providing live session statistics, network metrics, user status badges, and interactive chat channels.

---

## 🏗️ Architecture & Network Diagram

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
            +---------------------------+    +----------------------------+
                           |
                           v
            +-------------------------------------------------------------+
            |             ClientManager (Registry & Mutex Lock)           |
            |  - Active Sockets: {"Alice": sock1, "Bob": sock2}           |
            |  - Synchronization: threading.Lock()                        |
            +-------------------------------------------------------------+
```

---

## 📁 Folder Structure

```
LAN_CHAT_SYSTEM/
├── server/
│   ├── __init__.py
│   ├── config.py           # Host, port, buffer settings, LAN IP discovery
│   ├── protocol.py         # Framing, buffer accumulator, message parsing
│   ├── client_manager.py   # Client registry state & threading.Lock mutex
│   └── server.py           # Multi-threaded TCP socket server
├── web_bridge/
│   ├── __init__.py
│   └── bridge.py           # HTTP server & Web-to-TCP socket connector
├── dashboard/
│   ├── index.html          # Modern dark technical UI dashboard
│   ├── style.css           # Glassmorphism design system
│   └── app.js              # Client UI controller & stats tracker
├── tests/
│   ├── __init__.py
│   ├── test_protocol.py    # Protocol framing & parsing unit tests
│   ├── test_multiclient.py # Multi-client concurrency integration tests
│   └── test_fault.py       # Fault tolerance & edge case tests
├── docs/
│   ├── architecture.md    # Architecture breakdown & diagrams
│   ├── protocol.md        # Protocol specification & framing theory
│   ├── testing.md         # Automated test logs & manual test plan
│   ├── setup.md           # Quick setup guide for Localhost & LAN
│   ├── viva_questions.md  # Comprehensive Viva Q&A guide
│   └── limitations.md     # Engineering scope & limitations
├── README.md              # Project overview
└── requirements.txt       # Dependencies (Standard Library only)
```

---

## 🛠️ Quick Start Guide

### 1. Start the TCP Chat Server
```bash
python3 -m server.server
```

### 2. Start the Web Dashboard Bridge
```bash
python3 -m web_bridge.bridge
```

### 3. Connect from Devices
- **Local Computer**: Open browser to `http://localhost:8080`
- **Other LAN Devices (Phone/Laptop on same Wi-Fi)**: Open browser to `http://<SERVER_LAN_IP>:8080` (e.g. `http://192.168.1.15:8080`).

---

## 🧪 Running the Test Suite
Execute all automated unit and fault tolerance tests:
```bash
python3 -m unittest discover -s tests
```

---

## 🎓 Documentation Index
- [Architecture & Concurrency Documentation](docs/architecture.md)
- [Application Protocol Specification](docs/protocol.md)
- [Testing Suite & Test Report](docs/testing.md)
- [Setup & LAN Access Instructions](docs/setup.md)
- [Viva Examination Q&A Preparation](docs/viva_questions.md)
- [Known Limitations & Scope](docs/limitations.md)
