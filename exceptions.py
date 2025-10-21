"""
═══════════════════════════════════════════════════════════════════════
    EXCEPTION MODULE FOR TCP/UDP CHAT APPLICATION
═══════════════════════════════════════════════════════════════════════
This module provides comprehensive exception handling for all possible
errors that can occur in socket programming, including:
- Connection errors
- Sending/receiving issues  
- Socket binding problems
- Message format errors
- Authentication failures
- Server/client crashes
═══════════════════════════════════════════════════════════════════════
"""

import datetime
import traceback
import sys


# ═══════════════════════════════════════════════════════════════════════
#                           BASE EXCEPTION CLASS
# ═══════════════════════════════════════════════════════════════════════

class ChatException(Exception):
    """
    Base exception class for all chat-related errors.
    
    All custom exceptions inherit from this class to provide:
    - Consistent error handling
    - Original exception preservation
    - Automatic logging capability
    - Human-readable error messages
    """
    
    def __init__(self, message, original_error=None):
        """
        Initialize the exception.
        
        Args:
            message (str): Human-readable error description
            original_error (Exception): The original exception that caused this error
        """
        self.message = message
        self.original_error = original_error
        self.timestamp = datetime.datetime.now()
        super().__init__(self.message)
    
    def __str__(self):
        """Return formatted error message with original error if available"""
        if self.original_error:
            return f"{self.message} | Original: {str(self.original_error)}"
        return self.message
    
    def get_details(self):
        """
        Get detailed information about the exception.
        
        Returns:
            dict: Dictionary containing all exception details
        """
        return {
            'type': type(self).__name__,
            'message': self.message,
            'original_error': str(self.original_error) if self.original_error else None,
            'original_type': type(self.original_error).__name__ if self.original_error else None,
            'timestamp': self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def log(self, log_file="error_log.txt"):
        """
        Log this exception to a file.
        
        Args:
            log_file (str): Path to the log file
        """
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*70}\n")
                f.write(f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}]\n")
                f.write(f"Exception Type: {type(self).__name__}\n")
                f.write(f"Message: {self.message}\n")
                if self.original_error:
                    f.write(f"Original Error: {type(self.original_error).__name__}\n")
                    f.write(f"Original Message: {str(self.original_error)}\n")
                f.write(f"Traceback:\n{traceback.format_exc()}\n")
        except Exception as e:
            print(f"⚠️ Failed to log exception: {e}", file=sys.stderr)


# ═══════════════════════════════════════════════════════════════════════
#                        CONNECTION-RELATED EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════

class ConnectionError(ChatException):
    """
    Raised when establishing a connection fails.
    
    Common scenarios:
    - Server is not running
    - Wrong host/port combination
    - Network is unreachable
    - Connection timeout
    - Firewall blocking connection
    
    Example:
        try:
            sock.connect((HOST, PORT))
        except socket.error as e:
            raise ConnectionError("Failed to connect to server", e)
    """
    pass


class DisconnectionError(ChatException):
    """
    Raised when an unexpected disconnection occurs.
    
    Common scenarios:
    - Server crashes
    - Client forcefully closes connection
    - Network cable unplugged
    - TCP connection reset
    - Receiving empty message (EOF)
    
    Example:
        data = sock.recv(1024)
        if not data:
            raise DisconnectionError("Connection closed by peer")
    """
    pass


class SocketBindError(ChatException):
    """
    Raised when socket binding fails.
    
    Common scenarios:
    - Port already in use (another process using it)
    - Insufficient permissions (ports < 1024)
    - Invalid address/port combination
    - Address already in use (TIME_WAIT state)
    
    Example:
        try:
            sock.bind((HOST, PORT))
        except OSError as e:
            raise SocketBindError(f"Cannot bind to {HOST}:{PORT}", e)
    """
    pass


class SocketCreationError(ChatException):
    """
    Raised when socket creation fails.
    
    Common scenarios:
    - Too many open file descriptors
    - System resource exhaustion
    - Invalid socket parameters
    
    Example:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except OSError as e:
            raise SocketCreationError("Failed to create socket", e)
    """
    pass


# ═══════════════════════════════════════════════════════════════════════
#                       MESSAGE-RELATED EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════

class MessageSendError(ChatException):
    """
    Raised when sending a message fails.
    
    Common scenarios:
    - Socket is closed
    - Connection is broken
    - Buffer overflow
    - Network error during send
    - Peer reset connection
    
    Example:
        try:
            sock.send(message.encode())
        except socket.error as e:
            raise MessageSendError("Failed to send message", e)
    """
    pass


class MessageReceiveError(ChatException):
    """
    Raised when receiving a message fails.
    
    Common scenarios:
    - Socket is closed
    - Connection timeout
    - Network error during receive
    - Buffer issues
    - Peer closed connection
    
    Example:
        try:
            data = sock.recv(1024)
        except socket.error as e:
            raise MessageReceiveError("Failed to receive message", e)
    """
    pass


class InvalidMessageFormatError(ChatException):
    """
    Raised when message format is invalid.
    
    Common scenarios:
    - Invalid UTF-8 encoding
    - Message too long
    - Empty message when not allowed
    - Malformed command syntax
    - Invalid characters in message
    
    Example:
        try:
            message = data.decode("utf-8")
        except UnicodeDecodeError as e:
            raise InvalidMessageFormatError("Invalid UTF-8 encoding", e)
    """
    pass


class MessageTimeoutError(ChatException):
    """
    Raised when message operation times out.
    
    Common scenarios:
    - Send operation takes too long
    - Receive operation exceeds timeout
    - No response from peer within timeout
    
    Example:
        try:
            sock.settimeout(5.0)
            data = sock.recv(1024)
        except socket.timeout as e:
            raise MessageTimeoutError("Receive operation timed out", e)
    """
    pass


# ═══════════════════════════════════════════════════════════════════════
#                    AUTHENTICATION & VALIDATION EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════

class AuthenticationError(ChatException):
    """
    Raised when client authentication fails.
    
    Common scenarios:
    - Invalid nickname
    - Authentication timeout
    - Client sent invalid credentials
    - Duplicate nickname (if checking)
    
    Example:
        if not nickname or len(nickname) > 50:
            raise AuthenticationError("Invalid nickname format")
    """
    pass


class ValidationError(ChatException):
    """
    Raised when input validation fails.
    
    Common scenarios:
    - Empty required field
    - Value out of range
    - Invalid data type
    - Failed format check
    
    Example:
        if len(nickname) < 1:
            raise ValidationError("Nickname cannot be empty")
    """
    pass


# ═══════════════════════════════════════════════════════════════════════
#                       SERVER-RELATED EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════

class ServerShutdownError(ChatException):
    """
    Raised during server shutdown operations.
    
    Common scenarios:
    - Error while closing client connections
    - Error while stopping server threads
    - Cleanup operation failure
    - Resource release failure
    
    Example:
        try:
            server.close()
        except OSError as e:
            raise ServerShutdownError("Failed to shutdown server", e)
    """
    pass


class ServerStartupError(ChatException):
    """
    Raised when server fails to start.
    
    Common scenarios:
    - Cannot bind to port
    - Configuration error
    - Resource allocation failure
    - Permission denied
    
    Example:
        try:
            server.listen()
        except OSError as e:
            raise ServerStartupError("Server failed to start", e)
    """
    pass


class BroadcastError(ChatException):
    """
    Raised when broadcasting to multiple clients fails.
    
    Common scenarios:
    - Some clients disconnected during broadcast
    - Network error while broadcasting
    - Encoding error in broadcast message
    
    Example:
        failed_clients = []
        for client in clients:
            try:
                client.send(message)
            except socket.error:
                failed_clients.append(client)
        if failed_clients:
            raise BroadcastError(f"Failed to broadcast to {len(failed_clients)} clients")
    """
    pass


# ═══════════════════════════════════════════════════════════════════════
#                       PROTOCOL-SPECIFIC EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════

class TCPError(ChatException):
    """
    Raised for TCP-specific errors.
    
    Common scenarios:
    - TCP connection issues
    - Stream errors
    - TCP-specific socket options failure
    """
    pass


class UDPError(ChatException):
    """
    Raised for UDP-specific errors.
    
    Common scenarios:
    - UDP datagram issues
    - Packet loss detection
    - UDP-specific socket options failure
    """
    pass


# ═══════════════════════════════════════════════════════════════════════
#                         UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def handle_socket_error(error, operation, context=""):
    """
    Convert socket errors to appropriate custom exceptions.
    
    Args:
        error (Exception): The original socket error
        operation (str): The operation that failed (e.g., "connect", "send")
        context (str): Additional context about the error
    
    Returns:
        ChatException: Appropriate custom exception for the error
    
    Example:
        try:
            sock.connect((HOST, PORT))
        except socket.error as e:
            raise handle_socket_error(e, "connect", f"to {HOST}:{PORT}")
    """
    import socket as sock_module
    
    error_type = type(error).__name__
    error_msg = str(error)
    
    # Connection-related errors
    if operation in ["connect", "accept"]:
        if isinstance(error, sock_module.timeout):
            return ConnectionError(f"Connection timeout {context}", error)
        elif "refused" in error_msg.lower():
            return ConnectionError(f"Connection refused {context}", error)
        elif "unreachable" in error_msg.lower():
            return ConnectionError(f"Network unreachable {context}", error)
        else:
            return ConnectionError(f"Connection failed {context}", error)
    
    # Send errors
    elif operation == "send":
        if "broken pipe" in error_msg.lower():
            return DisconnectionError(f"Connection broken during send {context}", error)
        elif "reset" in error_msg.lower():
            return DisconnectionError(f"Connection reset during send {context}", error)
        else:
            return MessageSendError(f"Failed to send {context}", error)
    
    # Receive errors
    elif operation == "recv":
        if isinstance(error, sock_module.timeout):
            return MessageTimeoutError(f"Receive timeout {context}", error)
        elif "reset" in error_msg.lower():
            return DisconnectionError(f"Connection reset during receive {context}", error)
        else:
            return MessageReceiveError(f"Failed to receive {context}", error)
    
    # Bind errors
    elif operation == "bind":
        if "already in use" in error_msg.lower() or "address already in use" in error_msg.lower():
            return SocketBindError(f"Address already in use {context}", error)
        elif "permission denied" in error_msg.lower():
            return SocketBindError(f"Permission denied {context}", error)
        else:
            return SocketBindError(f"Failed to bind {context}", error)
    
    # Default
    else:
        return ChatException(f"Socket error during {operation} {context}", error)


def is_connection_error(error):
    """
    Check if an error is a connection-related error.
    
    Args:
        error (Exception): The error to check
    
    Returns:
        bool: True if it's a connection error
    """
    return isinstance(error, (ConnectionError, DisconnectionError, SocketBindError))


def is_message_error(error):
    """
    Check if an error is a message-related error.
    
    Args:
        error (Exception): The error to check
    
    Returns:
        bool: True if it's a message error
    """
    return isinstance(error, (MessageSendError, MessageReceiveError, InvalidMessageFormatError))


def format_error_for_user(error):
    """
    Format an exception for user-friendly display.
    
    Args:
        error (Exception): The exception to format
    
    Returns:
        str: User-friendly error message
    """
    if isinstance(error, ConnectionError):
        return f"❌ Connection failed: {error.message}"
    elif isinstance(error, DisconnectionError):
        return f"⚠️ Disconnected: {error.message}"
    elif isinstance(error, MessageSendError):
        return f"❌ Failed to send message: {error.message}"
    elif isinstance(error, MessageReceiveError):
        return f"❌ Failed to receive message: {error.message}"
    elif isinstance(error, InvalidMessageFormatError):
        return f"⚠️ Invalid message: {error.message}"
    elif isinstance(error, AuthenticationError):
        return f"❌ Authentication failed: {error.message}"
    elif isinstance(error, SocketBindError):
        return f"❌ Cannot start server: {error.message}"
    elif isinstance(error, ChatException):
        return f"❌ Error: {error.message}"
    else:
        return f"❌ Unexpected error: {str(error)}"


# ═══════════════════════════════════════════════════════════════════════
#                         EXCEPTION SUMMARY
# ═══════════════════════════════════════════════════════════════════════

def get_exception_hierarchy():
    """
    Get a string representation of the exception hierarchy.
    
    Returns:
        str: Formatted exception hierarchy
    """
    hierarchy = """
    Exception Hierarchy:
    
    ChatException (Base)
    ├── ConnectionError          - Connection establishment failures
    ├── DisconnectionError       - Unexpected disconnections
    ├── SocketBindError          - Socket binding failures
    ├── SocketCreationError      - Socket creation failures
    ├── MessageSendError         - Message sending failures
    ├── MessageReceiveError      - Message receiving failures
    ├── InvalidMessageFormatError- Invalid message format
    ├── MessageTimeoutError      - Message operation timeout
    ├── AuthenticationError      - Authentication failures
    ├── ValidationError          - Input validation failures
    ├── ServerShutdownError      - Server shutdown errors
    ├── ServerStartupError       - Server startup errors
    ├── BroadcastError           - Broadcast operation errors
    ├── TCPError                 - TCP-specific errors
    └── UDPError                 - UDP-specific errors
    """
    return hierarchy


if __name__ == "__main__":
    print("═" * 70)
    print("  EXCEPTION MODULE - TCP/UDP CHAT APPLICATION")
    print("═" * 70)
    print(get_exception_hierarchy())
    print("\n✅ Exception module loaded successfully!")
    print("📝 Total exception classes: 16")
    print("🔧 Utility functions available: 5")
    print("\nImport this module in your server.py and client.py:")
    print("  from exceptions import *")
    print("═" * 70)