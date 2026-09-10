"""
Multi-Threaded TCP Chat Server.

Listens on 0.0.0.0:5555 for incoming TCP client connections.
Spawns a dedicated thread per client and handles state synchronization via ClientManager.
"""

import sys
import socket
import threading
import logging
from typing import Optional

from server.config import (
    DEFAULT_HOST,
    DEFAULT_TCP_PORT,
    BUFFER_SIZE,
    ENCODING,
    get_lan_ip,
)
from server.protocol import (
    StreamBuffer,
    parse_message,
    ProtocolError,
    encode_join,
    encode_msg,
    encode_private,
    encode_whoreply,
    encode_leave,
    encode_error,
    encode_system,
)
from server.client_manager import ClientManager

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(threadName)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("TCPServer")


class ChatServer:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_TCP_PORT):
        self.host = host
        self.port = port
        self.server_socket: Optional[socket.socket] = None
        self.client_manager = ClientManager()
        self.is_running = False

    def start(self):
        """Initializes server socket, binds, listens, and enters main accept loop."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Enable SO_REUSEADDR to reuse socket port immediately after server restart
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(10)
            self.is_running = True

            lan_ip = get_lan_ip()
            logger.info("=" * 60)
            logger.info(f" TCP CHAT SERVER STARTED SUCCESSFULLY")
            logger.info(f" Listening on Interface : {self.host}:{self.port}")
            logger.info(f" Local Access           : localhost:{self.port}")
            logger.info(f" LAN Network Access     : {lan_ip}:{self.port}")
            logger.info("=" * 60)

            while self.is_running:
                try:
                    client_socket, client_address = self.server_socket.accept()
                    logger.info(f"New TCP connection accepted from {client_address[0]}:{client_address[1]}")
                    
                    # Spawn a dedicated handler thread for each accepted client
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, client_address),
                        daemon=True,
                    )
                    client_thread.start()
                except socket.error:
                    if not self.is_running:
                        break  # Server stopped
                    logger.error("Error accepting connection")

        except Exception as e:
            logger.critical(f"Server execution error: {e}")
        finally:
            self.stop()

    def _handle_client(self, client_socket: socket.socket, client_address):
        """
        Client Thread Execution Loop.
        Reads byte stream from socket, frames newline messages, and dispatches commands.
        """
        buffer = StreamBuffer()
        username: Optional[str] = None
        thread_name = threading.current_thread().name

        try:
            while self.is_running:
                raw_bytes = client_socket.recv(BUFFER_SIZE)
                
                # 0 bytes read indicates client closed connection (EOF)
                if not raw_bytes:
                    logger.info(f"Client at {client_address} closed connection.")
                    break

                # Decode byte stream into text accumulator buffer
                decoded_str = raw_bytes.decode(ENCODING, errors="replace")
                buffer.append(decoded_str)

                # Extract all newline-terminated complete messages
                messages = buffer.extract_messages()

                for raw_msg in messages:
                    try:
                        cmd, args = parse_message(raw_msg)
                        
                        # --- Command Dispatcher ---
                        if cmd == "JOIN":
                            new_user = args[0]
                            if username is not None:
                                client_socket.sendall(encode_error("Already joined.").encode(ENCODING))
                                continue

                            success, msg = self.client_manager.register_client(new_user, client_socket)
                            if not success:
                                client_socket.sendall(encode_error(msg).encode(ENCODING))
                                logger.warning(f"Registration failed for '{new_user}' from {client_address}: {msg}")
                            else:
                                username = new_user
                                logger.info(f"User '{username}' registered successfully from {client_address}")
                                
                                # Send welcome system message & initial WHO user list
                                client_socket.sendall(encode_system(f"Welcome to LAN Chat, {username}!").encode(ENCODING))
                                active_users = self.client_manager.get_user_list()
                                client_socket.sendall(encode_whoreply(active_users).encode(ENCODING))
                                
                                # Broadcast JOIN notification to all other connected clients
                                self.client_manager.broadcast(encode_join(username), exclude_username=username)

                        else:
                            # All other commands require a registered username
                            if username is None:
                                client_socket.sendall(encode_error("Must send JOIN:<username> first.").encode(ENCODING))
                                continue

                            if cmd == "MSG":
                                text = args[1]
                                logger.info(f"[BROADCAST] <{username}> {text}")
                                broadcast_pkt = encode_msg(username, text)
                                self.client_manager.broadcast(broadcast_pkt)

                            elif cmd == "PRIVATE":
                                target, text = args[1], args[2]
                                logger.info(f"[PRIVATE] <{username} -> {target}> {text}")
                                pm_pkt = encode_private(username, target, text)
                                
                                # Send to target
                                sent = self.client_manager.send_direct(target, pm_pkt)
                                if not sent:
                                    client_socket.sendall(encode_error(f"User '{target}' is offline or not found.").encode(ENCODING))
                                else:
                                    # Echo back to sender so sender UI displays PM confirmation
                                    client_socket.sendall(pm_pkt.encode(ENCODING))

                            elif cmd == "WHO":
                                active_users = self.client_manager.get_user_list()
                                client_socket.sendall(encode_whoreply(active_users).encode(ENCODING))

                            elif cmd == "LEAVE":
                                logger.info(f"User '{username}' sent LEAVE request.")
                                return  # Triggers cleanup in finally block

                    except ProtocolError as pe:
                        logger.warning(f"Protocol error from {client_address}: {pe}")
                        client_socket.sendall(encode_error(str(pe)).encode(ENCODING))

        except (ConnectionResetError, BrokenPipeError):
            logger.warning(f"Abrupt disconnect from user '{username}' at {client_address}")
        except Exception as e:
            logger.error(f"Unexpected error in client thread for '{username}': {e}")
        finally:
            # Clean disconnect & resource cleanup
            if username:
                self.client_manager.unregister_client(username)
                logger.info(f"Unregistered user '{username}'. Active users remaining: {self.client_manager.client_count}")
                self.client_manager.broadcast(encode_leave(username))

            try:
                client_socket.close()
            except Exception:
                pass

    def stop(self):
        """Stops the server socket gracefully."""
        self.is_running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
        logger.info("Server stopped.")


if __name__ == "__main__":
    port = DEFAULT_TCP_PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port: {sys.argv[1]}")
            sys.exit(1)

    server = ChatServer(port=port)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nShutdown requested by user. Terminating server...")
        server.stop()
