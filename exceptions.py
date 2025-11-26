"""
═══════════════════════════════════════════════════════════════════════
    EXCEPTION MODULE FOR TCP/UDP CHAT APPLICATION
═══════════════════════════════════════════════════════════════════════
"""

import datetime
import traceback
import sys

# ═══════════════════════════════════════════════════════════════════════
#                           BASE EXCEPTION CLASS
# ═══════════════════════════════════════════════════════════════════════

class ChatException(Exception):
    def __init__(self, message, original_error=None):
        self.message = message
        self.original_error = original_error
        self.timestamp = datetime.datetime.now()
        super().__init__(self.message)
    
    def __str__(self):
        if self.original_error:
            return f"{self.message} | Original: {str(self.original_error)}"
        return self.message
    
    def get_details(self):
        return {
            'type': type(self).__name__,
            'message': self.message,
            'original_error': str(self.original_error) if self.original_error else None,
            'original_type': type(self.original_error).__name__ if self.original_error else None,
            'timestamp': self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def log(self, log_file="error_log.txt"):
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
            print(f"Failed to log exception: {e}", file=sys.stderr)

# ═══════════════════════════════════════════════════════════════════════
#                        ALL OTHER EXCEPTIONS (مختصرة)
# ═══════════════════════════════════════════════════════════════════════

class ConnectionError(ChatException): pass
class DisconnectionError(ChatException): pass
class SocketBindError(ChatException): pass
class SocketCreationError(ChatException): pass
class MessageSendError(ChatException): pass
class MessageReceiveError(ChatException): pass
class InvalidMessageFormatError(ChatException): pass
class MessageTimeoutError(ChatException): pass
class AuthenticationError(ChatException): pass
class ValidationError(ChatException): pass
class ServerShutdownError(ChatException): pass
class ServerStartupError(ChatException): pass
class BroadcastError(ChatException): pass
class TCPError(ChatException): pass
class UDPError(ChatException): pass

# ═══════════════════════════════════════════════════════════════════════
#                         UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def handle_socket_error(error, operation, context=""):
    import socket as sock_module
    error_msg = str(error).lower()
    if operation in ["connect", "accept"]:
        return ConnectionError(f"Connection failed {context}", error)
    elif operation == "send":
        return MessageSendError(f"Failed to send {context}", error)
    elif operation == "recv":
        return MessageReceiveError(f"Failed to receive {context}", error)
    elif operation == "bind":
        return SocketBindError(f"Failed to bind {context}", error)
    else:
        return ChatException(f"Socket error during {operation} {context}", error)

def is_connection_error(error):
    return isinstance(error, (ConnectionError, DisconnectionError, SocketBindError))

def is_message_error(error):
    return isinstance(error, (MessageSendError, MessageReceiveError, InvalidMessageFormatError))

def format_error_for_user(error):
    if isinstance(error, ConnectionError): return f"Connection failed: {error.message}"
    elif isinstance(error, DisconnectionError): return f"Disconnected: {error.message}"
    elif isinstance(error, MessageSendError): return f"Failed to send: {error.message}"
    elif isinstance(error, MessageReceiveError): return f"Failed to receive: {error.message}"
    elif isinstance(error, ChatException): return f"Error: {error.message}"
    else: return f"Unexpected error: {str(error)}"

# ═══════════════════════════════════════════════════════════════════════
#                         log_exception (الدالة المطلوبة)
# ═══════════════════════════════════════════════════════════════════════

def log_exception(e):
    """
    Log any exception using the ChatException logging system.
    """
    if isinstance(e, ChatException):
        e.log("server_exception_log.txt")
    else:
        wrapped = ChatException("Unexpected error in server", e)
        wrapped.log("server_exception_log.txt")
    print(f"[EXCEPTION] {e}")

# ═══════════════════════════════════════════════════════════════════════
#                         EXCEPTION SUMMARY
# ═══════════════════════════════════════════════════════════════════════

def get_exception_hierarchy():
    return """
    Exception Hierarchy:
    ChatException (Base)
    ├── ConnectionError
    ├── DisconnectionError
    ├── SocketBindError
    └── ... (16 total)
    """

if __name__ == "__main__":
    print("Exception module loaded successfully!")