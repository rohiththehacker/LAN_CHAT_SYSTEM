# Computer Networks Viva Preparation Guide

This document contains high-yield technical questions and answers designed to help you explain every major component of this project during a college viva examination.

---

## 1. Socket API & Fundamental Networking

### Q1: What is a Socket?
> **Answer**: A socket is a software abstraction representing an endpoint for communication between two machines across a network. In Python, it acts as an interface between the application layer and the OS network stack. A TCP socket is uniquely identified by a 4-tuple: `(Source IP, Source Port, Destination IP, Destination Port)`.

### Q2: Explain the purpose of each socket system call used in `server.py`.
> **Answer**:
> - `socket()`: Creates a new socket descriptor (`AF_INET` for IPv4, `SOCK_STREAM` for TCP).
> - `bind()`: Associates the socket with a specific network interface IP address and port number (`0.0.0.0:5555`).
> - `listen()`: Configures the socket to act as a passive server listening for incoming connection requests. The backlog parameter (`listen(10)`) specifies how many pending connections can queue before new ones are refused.
> - `accept()`: A blocking call that extracts the first connection request on the queue, creates a **new connected client socket**, and returns `(client_socket, client_address)`.
> - `connect()`: Called by the client to initiate a 3-way TCP handshake with the server.
> - `sendall()`: Transmits data over the TCP socket. Continues sending until all bytes are pushed or an error occurs.
> - `recv()`: Blocks until data is received on the socket. Returns raw bytes. Returns `0 bytes` when the remote peer gracefully closes the connection.

### Q3: Why do we set `SO_REUSEADDR` on the server socket?
> **Answer**:
> ```python
> self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
> ```
> When a TCP server shuts down, the socket enters the `TIME_WAIT` state for up to 2 minutes to allow in-flight packets to clear. Without `SO_REUSEADDR`, restarting the server immediately causes an `OSError: [Errno 98] Address already in use`.

---

## 2. Transport Protocol Selection (TCP vs UDP)

### Q4: Why did we choose TCP instead of UDP for this chat application?
> **Answer**: TCP (Transmission Control Protocol) provides:
> 1. **Reliable Data Delivery**: Automatic packet retransmission and error checking (checksums).
> 2. **Ordered Streaming**: Guarantees that chat messages arrive in the exact order sent (sequence numbers).
> 3. **Connection-Oriented**: Establishes a formal session via a 3-way handshake (`SYN`, `SYN-ACK`, `ACK`).
> UDP is un-reliable and connectionless; packets could drop or arrive out of order, rendering text messages corrupt or missing.

---

## 3. Concurrency & Synchronization

### Q5: Why does every connected client get a dedicated thread?
> **Answer**: `socket.recv()` is a blocking operation. If a server ran on a single thread and called `recv()` on Client A, the server would freeze and be unable to handle Client B or accept new incoming connections until Client A sent data. Spawning a `threading.Thread` per client allows simultaneous, non-blocking communication across multiple clients.

### Q6: What is a Race Condition, and why is `threading.Lock()` necessary?
> **Answer**: A race condition occurs when multiple threads concurrently read and write shared data without synchronization, leading to inconsistent or corrupt state.
> In our project, the shared state is `ClientManager._clients` (a dictionary of active user sockets). If Thread 1 is broadcasting a message by iterating over `_clients` while Thread 2 handles a client disconnect by running `_clients.pop(user)`, a `RuntimeError: dictionary changed size during iteration` or crash occurs. 
> Using `threading.Lock()` ensures that only one thread can modify or read the client registry at any single moment (Mutual Exclusion).

---

## 4. Application Protocol & Byte Stream Framing

### Q7: What does "TCP is a byte stream" mean? Why is newline framing required?
> **Answer**: TCP treats data as a continuous stream of raw bytes, not discrete messages. TCP does **NOT** preserve application message boundaries (`send()` $\neq$ `recv()`).
> If a client executes `send("MSG1\n")` and `send("MSG2\n")` in rapid succession, TCP might combine them into a single packet (`"MSG1\nMSG2\n"`), or split a single message across two packets (`"MS"` and `"G1\n"`).
> Newline framing (`\n`) combined with our `StreamBuffer` accumulates raw chunks from `recv()` and reconstructs complete, individual messages before parsing.

---

## 5. Network Architecture & LAN Binding

### Q8: What is the difference between binding to `127.0.0.1` vs `0.0.0.0`?
> **Answer**:
> - Binding to `127.0.0.1` (loopback) limits connection access **only** to processes running on the exact same local machine.
> - Binding to `0.0.0.0` instructs the operating system to listen on **all available network interfaces** (Ethernet, Wi-Fi, loopback). This enables computers and smartphones on the same Wi-Fi subnet to connect.

### Q9: If the server is bound to `0.0.0.0`, why might remote LAN devices still receive a Connection Timeout?
> **Answer**:
> 1. **Host OS Firewall (UFW/iptables)**: The host OS firewall blocks incoming SYN packets on unprivileged ports (8080 and 5555) by default. The port must be explicitly allowed using `sudo ufw allow 8080/tcp` and `sudo ufw allow 5555/tcp`.
> 2. **Access Point (AP) Isolation**: Campus or enterprise Wi-Fi routers often enable AP Isolation, which drops peer-to-peer traffic between Wi-Fi clients at the link layer.
> 3. **Subnet Mismatch**: Devices connected to different VLANs or subnets without IP routing configured between them.

### Q10: How does the Web Dashboard interact with the TCP Server?
> **Answer**: Web browsers execute client JavaScript inside a security sandbox that prohibits raw TCP socket creation (`socket.socket()`). 
> Our architecture uses a **Web-to-TCP Bridge** (`web_bridge/bridge.py`). The browser communicates with the bridge over standard HTTP. For each connected web session, the bridge instantiates a **genuine Python TCP socket client** connected to port 5555, preserving the pure TCP socket backend architecture.
