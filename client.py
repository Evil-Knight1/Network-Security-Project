import socket
import threading
import datetime
import traceback
from exceptions import *

HOST = "127.0.0.1"
TCP_PORT = 55555
UDP_PORT = 55556
LOG_FILE = "client_log.txt"
running = True
print_lock = threading.Lock()

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
        print(f"⚠️ Failed to write to log: {e}")

def safe_print(msg):
    """Thread-safe printing"""
    with print_lock:
        print(f"\n{msg}")
        print("> ", end="", flush=True)

# ========== TCP ==========
def tcp_receive(sock, nickname):
    """Receive TCP messages with comprehensive error handling"""
    global running
    
    try:
        while running:
            try:
                # ===== STAGE 1: RECEIVE DATA =====
                try:
                    msg_data = sock.recv(1024)
                except socket.timeout:
                    continue
                except socket.error as e:
                    if running:
                        raise handle_socket_error(e, "recv", "TCP message")
                    break
                
                # ===== STAGE 2: CHECK FOR DISCONNECTION =====
                if not msg_data:
                    raise DisconnectionError("Server closed TCP connection")
                
                # ===== STAGE 3: DECODE MESSAGE =====
                try:
                    msg = msg_data.decode("utf-8")
                    safe_print(msg)
                except UnicodeDecodeError as e:
                    raise InvalidMessageFormatError("Received invalid UTF-8 from server", e)
                    
            except socket.timeout:
                continue
                
    except DisconnectionError as e:
        if running:
            safe_print(f"[TCP] {format_error_for_user(e)}")
            log_event(str(e), is_error=True, exception=e)
            running = False
            
    except MessageReceiveError as e:
        if running:
            safe_print(f"[TCP] {format_error_for_user(e)}")
            log_event(str(e), is_error=True, exception=e)
            running = False
            
    except InvalidMessageFormatError as e:
        safe_print(f"[TCP] {format_error_for_user(e)}")
        log_event(str(e), is_error=True, exception=e)
        
    except Exception as e:
        error = ChatException("Unexpected TCP receive error", e)
        safe_print(f"[TCP] {format_error_for_user(error)}")
        log_event(str(error), is_error=True, exception=error)
        running = False

def start_tcp(nickname):
    """Start TCP connection with comprehensive error handling"""
    sock = None
    
    try:
        # ===== STAGE 1: CREATE SOCKET =====
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except OSError as e:
            raise SocketCreationError("Failed to create TCP socket", e)
        
        # ===== STAGE 2: CONNECT WITH TIMEOUT =====
        sock.settimeout(10.0)
        try:
            sock.connect((HOST, TCP_PORT))
        except socket.timeout as e:
            raise ConnectionError(f"TCP connection to {HOST}:{TCP_PORT} timed out", e)
        except socket.error as e:
            raise handle_socket_error(e, "connect", f"to {HOST}:{TCP_PORT}")
        
        sock.settimeout(None)  # Remove timeout
        
        # ===== STAGE 3: SEND NICKNAME =====
        try:
            sock.send(nickname.encode("utf-8"))
        except socket.error as e:
            raise handle_socket_error(e, "send", "nickname")
        
        # ===== STAGE 4: START RECEIVE THREAD =====
        threading.Thread(target=tcp_receive, args=(sock, nickname), daemon=True).start()
        
        safe_print("[TCP] ✅ Connected.")
        log_event(f"Connected to TCP as {nickname}")
        return sock
        
    except SocketCreationError as e:
        safe_print(f"[TCP] {format_error_for_user(e)}")
        log_event(str(e), is_error=True, exception=e)
        if sock:
            try:
                sock.close()
            except:
                pass
        return None
        
    except ConnectionError as e:
        safe_print(f"[TCP] {format_error_for_user(e)}")
        log_event(str(e), is_error=True, exception=e)
        if sock:
            try:
                sock.close()
            except:
                pass
        return None
        
    except MessageSendError as e:
        safe_print(f"[TCP] {format_error_for_user(e)}")
        log_event(str(e), is_error=True, exception=e)
        if sock:
            try:
                sock.close()
            except:
                pass
        return None
        
    except Exception as e:
        error = ChatException("Unexpected TCP connection error", e)
        safe_print(f"[TCP] {format_error_for_user(error)}")
        log_event(str(error), is_error=True, exception=error)
        if sock:
            try:
                sock.close()
            except:
                pass
        return None

# ========== UDP ==========
def udp_receive(sock, nickname):
    """Receive UDP messages with comprehensive error handling"""
    global running
    
    try:
        while running:
            try:
                # ===== STAGE 1: RECEIVE DATA =====
                try:
                    data, _ = sock.recvfrom(1024)
                except socket.timeout:
                    continue
                except socket.error as e:
                    if running:
                        raise UDPError("UDP receive error", e)
                    break
                
                # ===== STAGE 2: DECODE MESSAGE =====
                try:
                    msg = data.decode("utf-8")
                    safe_print(msg)
                except UnicodeDecodeError as e:
                    raise InvalidMessageFormatError("Received invalid UTF-8 via UDP", e)
                    
            except socket.timeout:
                continue
                
    except UDPError as e:
        if running:
            safe_print(f"[UDP] {format_error_for_user(e)}")
            log_event(str(e), is_error=True, exception=e)
            
    except InvalidMessageFormatError as e:
        safe_print(f"[UDP] {format_error_for_user(e)}")
        log_event(str(e), is_error=True, exception=e)
        
    except Exception as e:
        error = ChatException("Unexpected UDP receive error", e)
        safe_print(f"[UDP] {format_error_for_user(error)}")
        log_event(str(error), is_error=True, exception=error)

def start_udp(nickname):
    """Start UDP connection with comprehensive error handling"""
    sock = None
    
    try:
        # ===== STAGE 1: CREATE SOCKET =====
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5.0)
        except OSError as e:
            raise SocketCreationError("Failed to create UDP socket", e)
        
        # ===== STAGE 2: SEND JOIN MESSAGE =====
        try:
            sock.sendto(f"/join:{nickname}".encode(), (HOST, UDP_PORT))
        except socket.error as e:
            raise UDPError(f"Failed to send join to {HOST}:{UDP_PORT}", e)
        
        # ===== STAGE 3: START RECEIVE THREAD =====
        threading.Thread(target=udp_receive, args=(sock, nickname), daemon=True).start()
        
        safe_print("[UDP] ✅ Connected.")
        log_event(f"Connected to UDP as {nickname}")
        return sock
        
    except SocketCreationError as e:
        safe_print(f"[UDP] {format_error_for_user(e)}")
        log_event(str(e), is_error=True, exception=e)
        if sock:
            try:
                sock.close()
            except:
                pass
        return None
        
    except UDPError as e:
        safe_print(f"[UDP] {format_error_for_user(e)}")
        log_event(str(e), is_error=True, exception=e)
        if sock:
            try:
                sock.close()
            except:
                pass
        return None
        
    except Exception as e:
        error = ChatException("Unexpected UDP connection error", e)
        safe_print(f"[UDP] {format_error_for_user(error)}")
        log_event(str(error), is_error=True, exception=error)
        if sock:
            try:
                sock.close()
            except:
                pass
        return None

# ========== MESSAGES ==========
def send_messages(tcp_sock, udp_sock):
    """Handle user input and send messages with comprehensive error handling"""
    global running
    print("\n📝 Commands: /tcp <msg> | /udp <msg> | /list | /exit\n")
    
    while running:
        try:
            msg = input("> ").strip()
            
            if not msg:
                continue

            # ===== EXIT COMMAND =====
            if msg.lower() == "/exit":
                running = False
                
                # Send exit via UDP
                if udp_sock:
                    try:
                        udp_sock.sendto("/exit".encode(), (HOST, UDP_PORT))
                    except socket.error as e:
                        error = UDPError("Failed to send exit via UDP", e)
                        log_event(str(error), is_error=True, exception=error)
                
                # Close TCP
                if tcp_sock:
                    try:
                        tcp_sock.close()
                    except socket.error as e:
                        error = ChatException("Error closing TCP", e)
                        log_event(str(error), is_error=True, exception=error)
                
                safe_print("👋 Disconnected.")
                break

            # ===== TCP MESSAGE =====
            elif msg.startswith("/tcp "):
                actual = msg[5:].strip()
                
                # Validate message
                try:
                    if not actual:
                        raise ValidationError("Message cannot be empty")
                    
                    if len(actual) > 1000:
                        raise ValidationError("Message too long (max 1000 characters)")
                except ValidationError as e:
                    safe_print(format_error_for_user(e))
                    continue
                
                if tcp_sock:
                    try:
                        tcp_sock.send(actual.encode())
                        log_event(f"Sent TCP: {actual}")
                    except socket.error as e:
                        error = handle_socket_error(e, "send", "TCP message")
                        safe_print(format_error_for_user(error))
                        log_event(str(error), is_error=True, exception=error)
                else:
                    safe_print("❌ TCP not connected.")

            # ===== UDP MESSAGE =====
            elif msg.startswith("/udp "):
                actual = msg[5:].strip()
                
                # Validate message
                try:
                    if not actual:
                        raise ValidationError("Message cannot be empty")
                    
                    if len(actual) > 1000:
                        raise ValidationError("Message too long (max 1000 characters)")
                except ValidationError as e:
                    safe_print(format_error_for_user(e))
                    continue
                
                if udp_sock:
                    try:
                        udp_sock.sendto(actual.encode(), (HOST, UDP_PORT))
                        log_event(f"Sent UDP: {actual}")
                    except socket.error as e:
                        error = UDPError("Failed to send UDP message", e)
                        safe_print(format_error_for_user(error))
                        log_event(str(error), is_error=True, exception=error)
                else:
                    safe_print("❌ UDP not connected.")

            # ===== LIST COMMAND =====
            elif msg == "/list":
                if udp_sock:
                    try:
                        udp_sock.sendto("/list".encode(), (HOST, UDP_PORT))
                        log_event("Requested user list")
                    except socket.error as e:
                        error = UDPError("Failed to request user list", e)
                        safe_print(format_error_for_user(error))
                        log_event(str(error), is_error=True, exception=error)
                else:
                    safe_print("❌ UDP not connected.")

            # ===== DEFAULT: TCP MESSAGE =====
            else:
                # Validate message
                try:
                    if len(msg) > 1000:
                        raise ValidationError("Message too long (max 1000 characters)")
                except ValidationError as e:
                    safe_print(format_error_for_user(e))
                    continue
                
                if tcp_sock:
                    try:
                        tcp_sock.send(msg.encode())
                        log_event(f"Sent TCP default: {msg}")
                    except socket.error as e:
                        error = handle_socket_error(e, "send", "message")
                        safe_print(format_error_for_user(error))
                        log_event(str(error), is_error=True, exception=error)
                else:
                    safe_print("❌ TCP not connected. Use /udp <msg> for UDP.")

        except KeyboardInterrupt:
            running = False
            safe_print("\n👋 Exiting...")
            break
        except EOFError:
            running = False
            break
        except Exception as e:
            error = ChatException("Unexpected error in message handler", e)
            safe_print(format_error_for_user(error))
            log_event(str(error), is_error=True, exception=error)

# ========== MAIN ==========
if __name__ == "__main__":
    print("="*60)
    print("🌐 COMBINED TCP + UDP CHAT CLIENT")
    print("="*60)
    
    try:
        # ===== STAGE 1: GET NICKNAME =====
        nickname = input("Enter your nickname: ").strip()
        
        # Validate nickname
        try:
            if not nickname:
                raise ValidationError("Nickname cannot be empty")
            
            if len(nickname) > 50:
                raise ValidationError("Nickname too long (max 50 characters)")
        except ValidationError as e:
            print(f"\n{format_error_for_user(e)}")
            log_event(str(e), is_error=True, exception=e)
            exit(1)
        
        print("\n🔌 Connecting to server...\n")
        
        # ===== STAGE 2: CONNECT TO SERVERS =====
        tcp_sock = start_tcp(nickname)
        udp_sock = start_udp(nickname)

        # ===== STAGE 3: CHECK CONNECTIONS =====
        if not tcp_sock and not udp_sock:
            safe_print("❌ Could not connect to any server.")
            log_event("Failed to connect to both TCP and UDP servers", is_error=True)
        else:
            # ===== STAGE 4: START MESSAGING =====
            send_messages(tcp_sock, udp_sock)
            log_event("Client closed normally")
            print("\n✅ Client stopped.")
            
    except ValidationError as e:
        print(f"\n{format_error_for_user(e)}")
        log_event(str(e), is_error=True, exception=e)
        
    except KeyboardInterrupt:
        print("\n👋 Interrupted by user.")
        log_event("Client interrupted by user")
        
    except Exception as e:
        error = ChatException("Fatal client error", e)
        print(f"\n{format_error_for_user(error)}")
        log_event(str(error), is_error=True, exception=error)