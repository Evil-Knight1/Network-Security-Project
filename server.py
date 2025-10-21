import socket
import threading
import datetime
import traceback
from exceptions import *

# ========== CONFIG ==========
HOST = "127.0.0.1"
TCP_PORT = 55555
UDP_PORT = 55556
LOG_FILE = "server_log.txt"

tcp_clients = {}   # client_socket -> nickname
udp_clients = {}   # addr -> nickname
lock = threading.Lock()
udp_server = None

# ========== LOGGING ==========
def log_event(msg, is_error=False, exception=None):
    """Write info/error logs with exception details"""
    try:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prefix = "ERROR" if is_error else "INFO"
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{now}] {prefix}: {msg}\n")
            if exception:
                if isinstance(exception, ChatException):
                    details = exception.get_details()
                    f.write(f"Exception Type: {details['type']}\n")
                    f.write(f"Message: {details['message']}\n")
                    if details['original_type']:
                        f.write(f"Original Error: {details['original_type']}\n")
                        f.write(f"Original Message: {details['original_error']}\n")
                f.write(traceback.format_exc() + "\n")
    except IOError as e:
        print(f"⚠️ Failed to write to log file: {e}")

# ========== TCP ==========
def broadcast_tcp(message, sender=None):
    """Send TCP message to all connected clients (except sender)"""
    disconnected = []
    
    with lock:
        for client in list(tcp_clients.keys()):
            if client != sender:
                try:
                    # Try to send message
                    try:
                        client.send(message.encode("utf-8"))
                    except socket.error as e:
                        raise handle_socket_error(e, "send", f"to {tcp_clients.get(client, 'unknown')}")
                    
                except (MessageSendError, DisconnectionError) as e:
                    log_event(str(e), is_error=True, exception=e)
                    disconnected.append(client)
                except Exception as e:
                    error = ChatException(f"Unexpected broadcast error", e)
                    log_event(str(error), is_error=True, exception=error)
                    disconnected.append(client)
    
    # Clean up disconnected clients
    for client in disconnected:
        try:
            client.close()
        except:
            pass
        with lock:
            name = tcp_clients.pop(client, None)
            if name:
                print(f"[TCP] ❌ {name} auto-disconnected (send failed)")

def handle_tcp_client(client, addr):
    """Handle TCP client connection with comprehensive error handling"""
    nickname = None
    
    try:
        # ===== STAGE 1: AUTHENTICATION =====
        try:
            client.settimeout(10.0)
            nickname_data = client.recv(1024)
            
            if not nickname_data:
                raise AuthenticationError("Client disconnected before sending nickname")
            
            # Try to decode nickname
            try:
                nickname = nickname_data.decode("utf-8").strip()
            except UnicodeDecodeError as e:
                raise InvalidMessageFormatError("Invalid nickname encoding", e)
            
            # Validate nickname
            if not nickname:
                raise ValidationError("Nickname cannot be empty")
            
            if len(nickname) > 50:
                raise ValidationError("Nickname too long (max 50 characters)")
            
        except socket.timeout as e:
            raise AuthenticationError("Client authentication timeout", e)
        except socket.error as e:
            raise handle_socket_error(e, "recv", "during authentication")
        
        # ===== STAGE 2: REGISTER CLIENT =====
        with lock:
            tcp_clients[client] = nickname
        
        client.settimeout(None)  # Remove timeout
        print(f"[TCP] ✅ {nickname} connected from {addr}")
        log_event(f"TCP {nickname} connected from {addr}")
        
        # ===== STAGE 3: SEND WELCOME MESSAGE =====
        try:
            client.send("✅ Connected to TCP chat server.".encode("utf-8"))
        except socket.error as e:
            raise handle_socket_error(e, "send", "welcome message")
        
        broadcast_tcp(f"📢 {nickname} joined via TCP", sender=client)

        # ===== STAGE 4: MESSAGE LOOP =====
        while True:
            try:
                # Try to receive message
                try:
                    msg_data = client.recv(1024)
                except socket.timeout:
                    continue
                except socket.error as e:
                    raise handle_socket_error(e, "recv", f"from {nickname}")
                
                # Check for disconnection
                if not msg_data:
                    raise DisconnectionError(f"{nickname} disconnected (empty message)")
                
                # Try to decode message
                try:
                    msg = msg_data.decode("utf-8").strip()
                except UnicodeDecodeError as e:
                    raise InvalidMessageFormatError(f"Invalid message encoding from {nickname}", e)
                
                if not msg:
                    continue
                
                print(f"[TCP] 💬 {nickname}: {msg}")
                broadcast_tcp(f"[TCP] {nickname}: {msg}", sender=client)
                broadcast_udp(f"[TCP] {nickname}: {msg}")
                
            except DisconnectionError as e:
                log_event(str(e), is_error=False)
                break
            except (MessageReceiveError, InvalidMessageFormatError) as e:
                log_event(str(e), is_error=True, exception=e)
                break
                
    except AuthenticationError as e:
        print(f"[TCP] ❌ Authentication failed from {addr}")
        log_event(str(e), is_error=True, exception=e)
        try:
            client.send("❌ Authentication failed.".encode("utf-8"))
        except:
            pass
            
    except ValidationError as e:
        print(f"[TCP] ❌ Validation error from {addr}: {e.message}")
        log_event(str(e), is_error=True, exception=e)
        try:
            client.send(f"❌ {e.message}".encode("utf-8"))
        except:
            pass
            
    except InvalidMessageFormatError as e:
        log_event(str(e), is_error=True, exception=e)
        try:
            client.send("❌ Invalid message format.".encode("utf-8"))
        except:
            pass
            
    except (MessageSendError, MessageReceiveError) as e:
        log_event(str(e), is_error=True, exception=e)
        
    except Exception as e:
        error = ChatException(f"Unexpected TCP error for {nickname or 'unknown'}", e)
        log_event(str(error), is_error=True, exception=error)
        
    finally:
        # ===== CLEANUP =====
        with lock:
            name = tcp_clients.pop(client, nickname)
        
        if name:
            print(f"[TCP] ❌ {name} disconnected")
            broadcast_tcp(f"📢 {name} left the chat.")
            log_event(f"TCP {name} disconnected")
        
        try:
            client.close()
        except:
            pass

def start_tcp():
    """Run TCP server with comprehensive error handling"""
    tcp_server = None
    
    try:
        # ===== STAGE 1: CREATE SOCKET =====
        try:
            tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except OSError as e:
            raise SocketCreationError("Failed to create TCP socket", e)
        
        # ===== STAGE 2: BIND SOCKET =====
        try:
            tcp_server.bind((HOST, TCP_PORT))
        except OSError as e:
            raise handle_socket_error(e, "bind", f"{HOST}:{TCP_PORT}")
        
        # ===== STAGE 3: LISTEN =====
        try:
            tcp_server.listen(5)
        except OSError as e:
            raise ServerStartupError("Failed to start TCP listening", e)
        
        print(f"[TCP] 🚀 TCP server running on {HOST}:{TCP_PORT}")
        log_event(f"TCP server started on {HOST}:{TCP_PORT}")
        
        # ===== STAGE 4: ACCEPT LOOP =====
        while True:
            try:
                client, addr = tcp_server.accept()
                threading.Thread(target=handle_tcp_client, args=(client, addr), daemon=True).start()
            except socket.error as e:
                error = ConnectionError("Failed to accept TCP connection", e)
                log_event(str(error), is_error=True, exception=error)
                continue
            except Exception as e:
                error = ChatException("Unexpected error accepting TCP connection", e)
                log_event(str(error), is_error=True, exception=error)
                continue
                
    except SocketCreationError as e:
        print(f"❌ {format_error_for_user(e)}")
        log_event(str(e), is_error=True, exception=e)
        
    except SocketBindError as e:
        print(f"❌ {format_error_for_user(e)}")
        log_event(str(e), is_error=True, exception=e)
        
    except ServerStartupError as e:
        print(f"❌ {format_error_for_user(e)}")
        log_event(str(e), is_error=True, exception=e)
        
    except Exception as e:
        error = ChatException("Fatal TCP server error", e)
        print(f"❌ {format_error_for_user(error)}")
        log_event(str(error), is_error=True, exception=error)
        
    finally:
        if tcp_server:
            try:
                tcp_server.close()
            except:
                pass

# ========== UDP ==========
def broadcast_udp(message, sender=None):
    """Send UDP message to all connected UDP clients (except sender)"""
    with lock:
        for addr in list(udp_clients.keys()):
            if addr != sender:
                try:
                    # Try to send UDP message
                    try:
                        udp_server.sendto(message.encode("utf-8"), addr)
                    except socket.error as e:
                        raise UDPError(f"Failed to send to {addr}", e)
                        
                except UDPError as e:
                    log_event(str(e), is_error=True, exception=e)
                except Exception as e:
                    error = ChatException(f"Unexpected UDP broadcast error to {addr}", e)
                    log_event(str(error), is_error=True, exception=error)

def handle_udp(data, addr):
    """Handle each UDP message with comprehensive error handling"""
    try:
        # ===== STAGE 1: DECODE MESSAGE =====
        try:
            message = data.decode("utf-8").strip()
        except UnicodeDecodeError as e:
            raise InvalidMessageFormatError("Invalid UTF-8 in UDP message", e)
        
        # ===== STAGE 2: PROCESS COMMANDS =====
        if message.startswith("/join:"):
            # JOIN COMMAND
            try:
                nickname = message.split(":", 1)[1].strip()
            except IndexError:
                raise InvalidMessageFormatError("Invalid /join command format")
            
            # Validate nickname
            if not nickname:
                raise ValidationError("Nickname cannot be empty")
            
            if len(nickname) > 50:
                raise ValidationError("Nickname too long (max 50 characters)")
            
            with lock:
                udp_clients[addr] = nickname
            
            print(f"[UDP] ✅ {nickname} joined from {addr}")
            log_event(f"UDP {nickname} joined from {addr}")
            
            try:
                udp_server.sendto(f"✅ Welcome {nickname} (UDP connected)".encode(), addr)
                broadcast_udp(f"📢 {nickname} joined via UDP", sender=addr)
            except socket.error as e:
                raise handle_socket_error(e, "send", f"welcome to {nickname}")

        elif message == "/list":
            # LIST COMMAND
            with lock:
                tcp_users = ", ".join(tcp_clients.values()) or "None"
                udp_users = ", ".join(udp_clients.values()) or "None"
            reply = f"👥 Online:\nTCP: {tcp_users}\nUDP: {udp_users}"
            
            try:
                udp_server.sendto(reply.encode(), addr)
            except socket.error as e:
                raise handle_socket_error(e, "send", f"user list to {addr}")

        elif message == "/exit":
            # EXIT COMMAND
            with lock:
                if addr in udp_clients:
                    name = udp_clients.pop(addr)
                    print(f"[UDP] ❌ {name} left")
                    broadcast_udp(f"📢 {name} left the UDP chat.")
                    log_event(f"UDP {name} disconnected")

        else:
            # REGULAR MESSAGE
            if addr in udp_clients:
                name = udp_clients[addr]
                print(f"[UDP] 💬 {name}: {message}")
                broadcast_udp(f"[UDP] {name}: {message}", sender=addr)
                broadcast_tcp(f"[UDP] {name}: {message}")
            else:
                try:
                    udp_server.sendto("⚠️ Please join first using /join:<yourname>".encode(), addr)
                except socket.error as e:
                    raise handle_socket_error(e, "send", f"error message to {addr}")
                    
    except InvalidMessageFormatError as e:
        log_event(str(e), is_error=True, exception=e)
        try:
            udp_server.sendto(f"❌ {e.message}".encode(), addr)
        except:
            pass
            
    except ValidationError as e:
        log_event(str(e), is_error=True, exception=e)
        try:
            udp_server.sendto(f"❌ {e.message}".encode(), addr)
        except:
            pass
            
    except (MessageSendError, UDPError) as e:
        log_event(str(e), is_error=True, exception=e)
        
    except Exception as e:
        error = ChatException(f"Unexpected UDP error from {addr}", e)
        log_event(str(error), is_error=True, exception=error)

def start_udp():
    """Run UDP server with comprehensive error handling"""
    global udp_server
    
    try:
        # ===== STAGE 1: CREATE SOCKET =====
        try:
            udp_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except OSError as e:
            raise SocketCreationError("Failed to create UDP socket", e)
        
        # ===== STAGE 2: BIND SOCKET =====
        try:
            udp_server.bind((HOST, UDP_PORT))
        except OSError as e:
            raise handle_socket_error(e, "bind", f"{HOST}:{UDP_PORT}")
        
        print(f"[UDP] 🚀 UDP server running on {HOST}:{UDP_PORT}")
        log_event(f"UDP server started on {HOST}:{UDP_PORT}")
        
        # ===== STAGE 3: RECEIVE LOOP =====
        while True:
            try:
                data, addr = udp_server.recvfrom(1024)
                threading.Thread(target=handle_udp, args=(data, addr), daemon=True).start()
            except socket.error as e:
                error = MessageReceiveError("UDP receive error", e)
                log_event(str(error), is_error=True, exception=error)
                continue
            except Exception as e:
                error = ChatException("Unexpected UDP receive error", e)
                log_event(str(error), is_error=True, exception=error)
                continue
                
    except SocketCreationError as e:
        print(f"❌ {format_error_for_user(e)}")
        log_event(str(e), is_error=True, exception=e)
        
    except SocketBindError as e:
        print(f"❌ {format_error_for_user(e)}")
        log_event(str(e), is_error=True, exception=e)
        
    except Exception as e:
        error = ChatException("Fatal UDP server error", e)
        print(f"❌ {format_error_for_user(error)}")
        log_event(str(error), is_error=True, exception=error)
        
    finally:
        if udp_server:
            try:
                udp_server.close()
            except:
                pass

# ========== MAIN ==========
if __name__ == "__main__":
    print("="*60)
    print("🌐 COMBINED TCP + UDP CHAT SERVER")
    print("="*60)
    
    try:
        tcp_thread = threading.Thread(target=start_tcp, daemon=True)
        udp_thread = threading.Thread(target=start_udp, daemon=True)
        
        tcp_thread.start()
        udp_thread.start()
        
        print("✅ Server running! Press Ctrl+C to stop.\n")
        log_event("Server started successfully")

        while True:
            pass
            
    except KeyboardInterrupt:
        print("\n🛑 Server shutting down...")
        log_event("Server shutdown requested")
        
        # Notify all clients
        try:
            broadcast_tcp("🛑 Server is shutting down...")
            broadcast_udp("🛑 Server is shutting down...")
        except Exception as e:
            error = ServerShutdownError("Error notifying clients during shutdown", e)
            log_event(str(error), is_error=True, exception=error)
        
    except Exception as e:
        error = ServerShutdownError("Unexpected error during server operation", e)
        print(f"\n❌ {format_error_for_user(error)}")
        log_event(str(error), is_error=True, exception=error)
        
    finally:
        print("👋 Server stopped.")
        log_event("Server stopped")