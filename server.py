"""
═══════════════════════════════════════════════════════════════════════
    FASTAPI CHAT SERVER WITH WEBSOCKET SUPPORT
═══════════════════════════════════════════════════════════════════════
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, validator
import asyncio
import uvicorn
import ssl
import exceptions

# ═══════════════════════════════════════════════════════════════════════
#                           CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════


class Settings:
    HOST = "127.0.0.1"
    PORT = 8000
    BUFFER_SIZE = 1024
    MAX_MESSAGE_LENGTH = 10000
    LOG_FILE = "server_log.txt"
    SSL_CERTFILE = "server.crt"
    SSL_KEYFILE = "server.key"
    USE_SSL = False  # Set to True to enable SSL


settings = Settings()

# ═══════════════════════════════════════════════════════════════════════
#                           PYDANTIC MODELS
# ═══════════════════════════════════════════════════════════════════════


class Message(BaseModel):
    content: str
    nickname: Optional[str] = "Anonymous"
    timestamp: Optional[datetime] = None

    @validator("content")
    def validate_content(cls, v):
        if not v or not v.strip():
            raise ValueError("Message content cannot be empty")
        if len(v) > settings.MAX_MESSAGE_LENGTH:
            raise ValueError(
                f"Message too long (max {settings.MAX_MESSAGE_LENGTH} chars)"
            )
        return v.strip()

    @validator("nickname")
    def validate_nickname(cls, v):
        if v and len(v) > 50:
            raise ValueError("Nickname too long (max 50 chars)")
        return v.strip() if v else "Anonymous"


class ChatResponse(BaseModel):
    status: str
    message: str
    data: Optional[dict] = None


class UserInfo(BaseModel):
    nickname: str
    connected_at: datetime
    message_count: int


# ═══════════════════════════════════════════════════════════════════════
#                           CONNECTION MANAGER
# ═══════════════════════════════════════════════════════════════════════


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[WebSocket, dict] = {}
        self.message_history: List[dict] = []
        self.max_history = 100

    async def connect(self, websocket: WebSocket, nickname: str):
        """Accept and register a new WebSocket connection"""
        try:
            await websocket.accept()
            self.active_connections[websocket] = {
                "nickname": nickname,
                "connected_at": datetime.now(),
                "message_count": 0,
            }
            log_event(f"{nickname} connected via WebSocket")

            # Send connection confirmation
            await self.send_personal_message(
                f"Welcome {nickname}! You are now connected.", websocket
            )

            # Notify others
            await self.broadcast(f"{nickname} joined the chat!", exclude=websocket)

            # Send recent message history
            await self.send_history(websocket)

        except Exception as e:
            exceptions.log_exception(
                exceptions.ConnectionError(f"Failed to connect user {nickname}", e)
            )
            raise

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        if websocket in self.active_connections:
            user_info = self.active_connections[websocket]
            nickname = user_info["nickname"]
            del self.active_connections[websocket]
            log_event(f"{nickname} disconnected")
            return nickname
        return None

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send message to a specific client"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            exceptions.log_exception(
                exceptions.MessageSendError(f"Failed to send personal message", e)
            )
            raise

    async def broadcast(self, message: str, exclude: Optional[WebSocket] = None):
        """Broadcast message to all connected clients"""
        disconnected = []

        for connection in self.active_connections:
            if connection != exclude:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    exceptions.log_exception(
                        exceptions.MessageSendError(
                            f"Failed to broadcast to {self.active_connections[connection]['nickname']}",
                            e,
                        )
                    )
                    disconnected.append(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

    async def send_history(self, websocket: WebSocket):
        """Send recent message history to newly connected client"""
        try:
            if self.message_history:
                history_msg = "\n--- Recent Messages ---\n"
                for msg in self.message_history[-20:]:  # Last 20 messages
                    history_msg += (
                        f"[{msg['timestamp']}] {msg['nickname']}: {msg['content']}\n"
                    )
                history_msg += "--- End of History ---\n"
                await self.send_personal_message(history_msg, websocket)
        except Exception as e:
            exceptions.log_exception(
                exceptions.MessageReceiveError("Failed to send history", e)
            )

    def add_to_history(self, nickname: str, content: str):
        """Add message to history"""
        self.message_history.append(
            {
                "nickname": nickname,
                "content": content,
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            }
        )

        # Trim history if too long
        if len(self.message_history) > self.max_history:
            self.message_history = self.message_history[-self.max_history :]

    def get_online_users(self) -> List[UserInfo]:
        """Get list of currently connected users"""
        return [
            UserInfo(
                nickname=info["nickname"],
                connected_at=info["connected_at"],
                message_count=info["message_count"],
            )
            for info in self.active_connections.values()
        ]


# ═══════════════════════════════════════════════════════════════════════
#                           UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════


def log_event(message: str):
    """Log events to file"""
    try:
        with open(settings.LOG_FILE, "a", encoding="utf-8") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        print(f"Failed to log event: {e}")


# ═══════════════════════════════════════════════════════════════════════
#                           FASTAPI APPLICATION
# ═══════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="Chat Server API",
    description="Real-time chat server with WebSocket support",
    version="2.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connection manager instance
manager = ConnectionManager()

# ═══════════════════════════════════════════════════════════════════════
#                           EXCEPTION HANDLERS
# ═══════════════════════════════════════════════════════════════════════


@app.exception_handler(exceptions.ChatException)
async def chat_exception_handler(request, exc: exceptions.ChatException):
    """Handle custom chat exceptions"""
    exc.log("server_exception_log.txt")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "message": exceptions.format_error_for_user(exc),
            "details": exc.get_details(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Handle general exceptions"""
    wrapped_exc = exceptions.ChatException("Unexpected server error", exc)
    wrapped_exc.log("server_exception_log.txt")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "message": "An unexpected error occurred",
            "error": str(exc),
        },
    )


# ═══════════════════════════════════════════════════════════════════════
#                           REST ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════


@app.get("/", response_model=ChatResponse)
async def root():
    """Health check endpoint"""
    return ChatResponse(
        status="success",
        message="Chat server is running",
        data={
            "version": "2.0.0",
            "active_connections": len(manager.active_connections),
            "timestamp": datetime.now().isoformat(),
        },
    )


@app.get("/health", response_model=ChatResponse)
async def health_check():
    """Detailed health check"""
    return ChatResponse(
        status="success",
        message="Server is healthy",
        data={
            "active_users": len(manager.active_connections),
            "message_history_size": len(manager.message_history),
            "uptime": "N/A",  # You can track this with a global variable
        },
    )


@app.get("/users", response_model=ChatResponse)
async def get_users():
    """Get list of online users"""
    try:
        users = manager.get_online_users()
        return ChatResponse(
            status="success",
            message=f"Found {len(users)} online users",
            data={"users": [user.dict() for user in users], "count": len(users)},
        )
    except Exception as e:
        exceptions.log_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users",
        )


@app.get("/history")
async def get_message_history():
    """Get recent message history"""
    try:
        return ChatResponse(
            status="success",
            message="Message history retrieved",
            data={
                "messages": manager.message_history[-50:],  # Last 50 messages
                "count": len(manager.message_history),
            },
        )
    except Exception as e:
        exceptions.log_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve message history",
        )


@app.post("/message", response_model=ChatResponse)
async def send_message(message: Message):
    """Send a message via REST API (alternative to WebSocket)"""
    try:
        # Validate message
        if not message.content:
            raise exceptions.InvalidMessageFormatError("Message content is empty")

        # Create formatted message
        formatted_msg = f"{message.nickname}: {message.content}"

        # Broadcast to all WebSocket clients
        await manager.broadcast(formatted_msg)

        # Add to history
        manager.add_to_history(message.nickname, message.content)

        # Log event
        log_event(f"REST API message from {message.nickname}: {message.content}")

        return ChatResponse(
            status="success",
            message="Message sent successfully",
            data={"sent_at": datetime.now().isoformat()},
        )

    except exceptions.ChatException as e:
        exceptions.log_exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exceptions.format_error_for_user(e),
        )
    except Exception as e:
        exceptions.log_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send message",
        )


# ═══════════════════════════════════════════════════════════════════════
#                           WEBSOCKET ENDPOINT
# ═══════════════════════════════════════════════════════════════════════


@app.websocket("/ws/{nickname}")
async def websocket_endpoint(websocket: WebSocket, nickname: str):
    """WebSocket endpoint for real-time chat"""

    # Validate nickname
    if not nickname or len(nickname) > 50:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    nickname = nickname.strip()

    try:
        # Connect the client
        await manager.connect(websocket, nickname)

        # Main message loop
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()

                # Handle special commands
                if data.lower() == "quit":
                    break

                if data.lower() == "/users":
                    users = manager.get_online_users()
                    user_list = "\n".join([f"- {u.nickname}" for u in users])
                    await manager.send_personal_message(
                        f"Online users:\n{user_list}", websocket
                    )
                    continue

                # Validate message
                if not data.strip():
                    continue

                if len(data) > settings.MAX_MESSAGE_LENGTH:
                    await manager.send_personal_message(
                        f"Error: Message too long (max {settings.MAX_MESSAGE_LENGTH} chars)",
                        websocket,
                    )
                    continue

                # Update message count
                manager.active_connections[websocket]["message_count"] += 1

                # Create formatted message
                formatted_msg = f"{nickname}: {data}"

                # Log the message
                log_event(formatted_msg)

                # Add to history
                manager.add_to_history(nickname, data)

                # Broadcast to all clients
                await manager.broadcast(formatted_msg, exclude=websocket)

            except WebSocketDisconnect:
                raise  # Re-raise to handle in outer except

            except exceptions.MessageReceiveError as e:
                exceptions.log_exception(e)
                await manager.send_personal_message(
                    "Error receiving your message. Please try again.", websocket
                )

            except Exception as e:
                exceptions.log_exception(
                    exceptions.MessageReceiveError(
                        f"Error processing message from {nickname}", e
                    )
                )
                await manager.send_personal_message(
                    "An error occurred processing your message.", websocket
                )

    except WebSocketDisconnect:
        nickname = manager.disconnect(websocket)
        if nickname:
            await manager.broadcast(f"{nickname} left the chat!")
            log_event(f"{nickname} disconnected (WebSocketDisconnect)")

    except exceptions.ConnectionError as e:
        exceptions.log_exception(e)
        nickname = manager.disconnect(websocket)
        if nickname:
            log_event(f"{nickname} disconnected due to connection error")

    except Exception as e:
        exceptions.log_exception(
            exceptions.DisconnectionError(f"Unexpected error for user {nickname}", e)
        )
        nickname = manager.disconnect(websocket)
        if nickname:
            await manager.broadcast(f"{nickname} left the chat!")


# ═══════════════════════════════════════════════════════════════════════
#                           STARTUP/SHUTDOWN EVENTS
# ═══════════════════════════════════════════════════════════════════════


@app.on_event("startup")
async def startup_event():
    """Initialize server on startup"""
    try:
        log_event("=" * 70)
        log_event("FastAPI Chat Server Started")
        log_event(f"Host: {settings.HOST}")
        log_event(f"Port: {settings.PORT}")
        log_event(f"SSL Enabled: {settings.USE_SSL}")
        log_event("=" * 70)
        print(f"🚀 Server started on {settings.HOST}:{settings.PORT}")
        print(
            f"📡 WebSocket endpoint: ws://{settings.HOST}:{settings.PORT}/ws/{{nickname}}"
        )
        print(f"📝 API docs: http://{settings.HOST}:{settings.PORT}/docs")
    except Exception as e:
        exceptions.log_exception(
            exceptions.ServerStartupError("Failed to start server", e)
        )
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on server shutdown"""
    try:
        log_event("Server shutting down...")

        # Notify all connected clients
        await manager.broadcast("Server is shutting down. Goodbye!")

        # Close all connections
        for connection in list(manager.active_connections.keys()):
            try:
                await connection.close()
            except:
                pass

        log_event("Server shutdown complete")
        print("👋 Server stopped")
    except Exception as e:
        exceptions.log_exception(
            exceptions.ServerShutdownError("Error during shutdown", e)
        )


# ═══════════════════════════════════════════════════════════════════════
#                           MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "_main_":
    # SSL Configuration
    ssl_config = None
    if settings.USE_SSL:
        try:
            ssl_config = {
                "ssl_certfile": settings.SSL_CERTFILE,
                "ssl_keyfile": settings.SSL_KEYFILE,
            }
            print("🔒 SSL enabled")
        except Exception as e:
            print(f"⚠  SSL configuration failed: {e}")
            print("Running without SSL")
            ssl_config = None

    # Run server
    uvicorn.run(
        "server:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,  # Auto-reload on code changes (disable in production)
        log_level="info",
        **(ssl_config or {}),
    )
