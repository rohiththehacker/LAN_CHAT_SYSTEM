# Known Limitations & Academic Scope

## 1. Educational Scope & Security
- **No TLS/SSL Encryption**: Data sent over TCP port 5555 is transmitted as plaintext (`utf-8`). On an unencrypted LAN or open Wi-Fi network, packets can be inspected using packet sniffers like Wireshark.
- **No Persistent Authentication**: Usernames are validated for session uniqueness only; passwords or cryptographic tokens are not implemented.

## 2. Scalability Boundaries
- **Thread-per-Client Concurrency Limits**: Spawning one OS thread per client works efficiently for tens to hundreds of clients on a LAN. However, scaling to tens of thousands of concurrent connections requires an asynchronous I/O event-loop architecture (e.g. `select`, `epoll`, or Python `asyncio`).

## 3. Potential Extensions & Future Enhancements
- **TLS Socket Wrapper**: Wrap client/server sockets with `ssl.wrap_socket()` to provide end-to-end encryption.
- **File Transfer Subprotocol**: Implement a secondary TCP socket port dedicated to binary chunked file transfer (`SEND_FILE:<filename>:<size>`).
