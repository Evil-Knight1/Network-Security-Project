"""
FASTAPI CHAT SERVER WITH WEBSOCKET SUPPORT + REST "FTP" (upload/download/list)
نسخة محسّنة - تشتغل على الشبكة + Pydantic V2 + hMailServer Integration
"""

import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
import json


from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    HTTPException,
    status,
    UploadFile,
    File,
    Request,
    Depends,
    Header,
    Query,
    Form,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, field_validator  # ✅ Pydantic V2
from contextlib import asynccontextmanager  # ✅ للـ lifespan
from jose import JWTError, jwt

import uvicorn
import asyncio

# Import database and email modules
import database
import email_service


# Dummy exceptions module
class _DummyExc(Exception):
    def log(self, *a, **k):
        pass


class exceptions:
    class ChatException(Exception):
        def __init__(self, *a, **k):
            super().__init__(*a)

        def log(self, *a, **k):
            pass

    @staticmethod
    def log_exception(e):
        print("Exception:", e)

    @staticmethod
    def format_error_for_user(e):
        return str(e)


# ───────────────────────────────────────────
# Configuration
# ───────────────────────────────────────────
class Settings:
    HOST = "0.0.0.0"  # ✅✅ كده هيشتغل على كل الشبكة
    PORT = 8000
    BUFFER_SIZE = 1024
    MAX_MESSAGE_LENGTH = 10000
    LOG_FILE = "server_log.txt"
    SSL_CERTFILE = "server.crt"
    SSL_KEYFILE = "server.key"
    USE_SSL = False
    UPLOAD_DIR = "uploads"
    JWT_SECRET_KEY = "your-secret-key-change-in-production"  # Change this in production
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_HOURS = 24


settings = Settings()
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)


# ───────────────────────────────────────────
# Pydantic models (V2)
# ───────────────────────────────────────────
class Message(BaseModel):
    content: str
    nickname: Optional[str] = "Anonymous"
    timestamp: Optional[datetime] = None

    @field_validator("content")  # ✅ Pydantic V2
    @classmethod
    def validate_content(cls, v):
        if not v or not v.strip():
            raise ValueError("Message content cannot be empty")
        if len(v) > settings.MAX_MESSAGE_LENGTH:
            raise ValueError(
                f"Message too long (max {settings.MAX_MESSAGE_LENGTH} chars)"
            )
        return v.strip()

    @field_validator("nickname")  # ✅ Pydantic V2
    @classmethod
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


# Authentication models
class SignupRequest(BaseModel):
    nick_name: str
    password: str


class LoginRequest(BaseModel):
    nick_name: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict


# Security
security = HTTPBearer()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Get current authenticated user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token = credentials.credentials
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = database.get_user_by_id(user_id)
    if user is None:
        raise credentials_exception
    return {k: v for k, v in user.items() if k != "password"}


async def get_current_user_optional(
    authorization: Optional[str] = Header(None),
) -> Optional[dict]:
    """Get current user optionally (for WebSocket)"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        token = authorization.split(" ")[1]
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id:
            user = database.get_user_by_id(user_id)
            if user:
                return {k: v for k, v in user.items() if k != "password"}
    except:
        pass
    return None


# ───────────────────────────────────────────
# Connection manager
# ───────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[WebSocket, dict] = {}
        self.message_history: List[dict] = []
        self.max_history = 100
        # Chat room connections: {chat_id: [websockets]}
        self.private_chat_rooms: Dict[str, List[WebSocket]] = {}
        self.group_chat_rooms: Dict[str, List[WebSocket]] = {}

    def get_user_sockets(self, user_id: str) -> List[WebSocket]:
        """Get all active WebSocket connections for a specific user"""
        user_sockets = []
        for ws, info in self.active_connections.items():
            if info.get("user_id") == user_id:
                user_sockets.append(ws)
        return user_sockets

    async def connect(self, websocket: WebSocket, user_id: str, nickname: str):
        await websocket.accept()
        self.active_connections[websocket] = {
            "user_id": user_id,
            "nickname": nickname,
            "connected_at": datetime.now(),
            "message_count": 0,
        }
        log_event(f"{nickname} connected via WebSocket")

        # Broadcast user connected status
        await self.broadcast(
            json.dumps(
                {
                    "type": "user_status",
                    "status": "online",
                    "user_id": user_id,
                    "nickname": nickname,
                }
            )
        )

    async def join_private_chat(self, websocket: WebSocket, chat_id: str):
        """Join a private chat room"""
        if chat_id not in self.private_chat_rooms:
            self.private_chat_rooms[chat_id] = []
        if websocket not in self.private_chat_rooms[chat_id]:
            self.private_chat_rooms[chat_id].append(websocket)

    async def leave_private_chat(self, websocket: WebSocket, chat_id: str):
        """Leave a private chat room"""
        if chat_id in self.private_chat_rooms:
            if websocket in self.private_chat_rooms[chat_id]:
                self.private_chat_rooms[chat_id].remove(websocket)

    async def join_group_chat(self, websocket: WebSocket, group_id: str):
        """Join a group chat room"""
        if group_id not in self.group_chat_rooms:
            self.group_chat_rooms[group_id] = []
        if websocket not in self.group_chat_rooms[group_id]:
            self.group_chat_rooms[group_id].append(websocket)

    async def leave_group_chat(self, websocket: WebSocket, group_id: str):
        """Leave a group chat room"""
        if group_id in self.group_chat_rooms:
            if websocket in self.group_chat_rooms[group_id]:
                self.group_chat_rooms[group_id].remove(websocket)

    async def send_to_private_chat(
        self,
        chat_id: str,
        message: dict,
        exclude: Union[WebSocket, List[WebSocket], None] = None,
    ):
        """Send message to all participants in a private chat"""
        if chat_id in self.private_chat_rooms:
            disconnected = []

            # Normalize exclude to a list
            exclude_list = []
            if isinstance(exclude, list):
                exclude_list = exclude
            elif exclude:
                exclude_list = [exclude]

            for connection in self.private_chat_rooms[chat_id]:
                if connection not in exclude_list:
                    try:
                        await connection.send_json(message)
                    except Exception as e:
                        exceptions.log_exception(e)
                        disconnected.append(connection)
            for conn in disconnected:
                await self.leave_private_chat(conn, chat_id)

    async def send_to_group_chat(
        self,
        group_id: str,
        message: dict,
        exclude: Union[WebSocket, List[WebSocket], None] = None,
    ):
        """Send message to all members in a group chat"""
        if group_id in self.group_chat_rooms:
            disconnected = []

            # Normalize exclude to a list
            exclude_list = []
            if isinstance(exclude, list):
                exclude_list = exclude
            elif exclude:
                exclude_list = [exclude]

            for connection in self.group_chat_rooms[group_id]:
                if connection not in exclude_list:
                    try:
                        await connection.send_json(message)
                    except Exception as e:
                        exceptions.log_exception(e)
                        disconnected.append(connection)
            for conn in disconnected:
                await self.leave_group_chat(conn, group_id)

    async def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            user_info = self.active_connections[websocket]
            nickname = user_info["nickname"]
            user_id = user_info["user_id"]

            # Remove from all chat rooms
            for chat_id in list(self.private_chat_rooms.keys()):
                if websocket in self.private_chat_rooms[chat_id]:
                    self.private_chat_rooms[chat_id].remove(websocket)
            for group_id in list(self.group_chat_rooms.keys()):
                if websocket in self.group_chat_rooms[group_id]:
                    self.group_chat_rooms[group_id].remove(websocket)
            del self.active_connections[websocket]
            log_event(f"{nickname} disconnected")

            # Broadcast user disconnected status
            await self.broadcast(
                json.dumps(
                    {
                        "type": "user_status",
                        "status": "offline",
                        "user_id": user_id,
                        "nickname": nickname,
                    }
                )
            )

            return nickname
        return None

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception as e:
            exceptions.log_exception(e)
            raise

    async def broadcast(
        self, message: str, exclude: Union[WebSocket, List[WebSocket], None] = None
    ):
        disconnected = []

        # Normalize exclude to a list
        exclude_list = []
        if isinstance(exclude, list):
            exclude_list = exclude
        elif exclude:
            exclude_list = [exclude]

        for connection in list(self.active_connections.keys()):
            if connection not in exclude_list:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    exceptions.log_exception(e)
                    disconnected.append(connection)
        for conn in disconnected:
            await self.disconnect(conn)

    async def send_history(self, websocket: WebSocket):
        if self.message_history:
            history_msg = "\n--- Recent Messages ---\n"
            for msg in self.message_history[-20:]:
                history_msg += (
                    f"[{msg['timestamp']}] {msg['nickname']}: {msg['content']}\n"
                )
            history_msg += "--- End of History ---\n"
            await self.send_personal_message(history_msg, websocket)

    def add_to_history(self, nickname: str, content: str):
        self.message_history.append(
            {
                "nickname": nickname,
                "content": content,
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            }
        )
        if len(self.message_history) > self.max_history:
            self.message_history = self.message_history[-self.max_history :]

    def get_online_users(self) -> List[UserInfo]:
        return [
            UserInfo(
                nickname=info["nickname"],
                connected_at=info["connected_at"],
                message_count=info["message_count"],
            )
            for info in self.active_connections.values()
        ]


# ───────────────────────────────────────────
# Utilities
# ───────────────────────────────────────────
def log_event(message: str):
    try:
        with open(settings.LOG_FILE, "a", encoding="utf-8") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        print(f"Failed to log event: {e}")


manager = ConnectionManager()


# ───────────────────────────────────────────
# Lifespan (✅ بدل on_event)
# ───────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        # Initialize database
        database.init_database()
        log_event("=" * 70)
        log_event("FastAPI Chat Server Started")
        log_event(f"Host: {settings.HOST}")
        log_event(f"Port: {settings.PORT}")
        log_event(f"SSL Enabled: {settings.USE_SSL}")
        log_event("=" * 70)
        print(f"🚀 Server started on {settings.HOST}:{settings.PORT}")
        scheme = "https" if settings.USE_SSL else "http"
        print(
            f"📡 WebSocket endpoint: {'wss' if settings.USE_SSL else 'ws'}://{settings.HOST}:{settings.PORT}/ws"
        )
        print(f"📝 API docs: {scheme}://{settings.HOST}:{settings.PORT}/docs")
    except Exception as e:
        exceptions.log_exception(e)
        raise

    yield  # Server running

    # Shutdown
    try:
        log_event("Server shutting down...")
        await manager.broadcast("Server is shutting down. Goodbye!")
        for connection in list(manager.active_connections.keys()):
            try:
                await connection.close()
            except:
                pass
        log_event("Server shutdown complete")
        print("👋 Server stopped")
    except Exception as e:
        exceptions.log_exception(e)


# ───────────────────────────────────────────
# FastAPI app
# ───────────────────────────────────────────
app = FastAPI(
    title="Chat Server API",
    description="Real-time chat server with WebSocket + FTP REST endpoints + hMailServer",
    version="2.0.0",
    lifespan=lifespan,  # ✅ استخدام lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(exceptions.ChatException)
async def chat_exception_handler(request, exc: exceptions.ChatException):
    try:
        exc.log("server_exception_log.txt")
    except Exception:
        pass
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "message": exceptions.format_error_for_user(exc),
            "details": getattr(exc, "args", []),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    try:
        wrapped_exc = exceptions.ChatException("Unexpected server error", exc)
        wrapped_exc.log("server_exception_log.txt")
    except Exception:
        pass
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "message": "An unexpected error occurred",
            "error": str(exc),
        },
    )


# Endpoints
@app.get("/", response_model=ChatResponse)
async def root():
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
    return ChatResponse(
        status="success",
        message="Server is healthy",
        data={
            "active_users": len(manager.active_connections),
            "message_history_size": len(manager.message_history),
            "uptime": "N/A",
        },
    )


@app.get("/users", response_model=ChatResponse)
async def get_users():
    try:
        users = manager.get_online_users()
        return ChatResponse(
            status="success",
            message=f"Found {len(users)} online users",
            data={"users": [u.model_dump() for u in users], "count": len(users)},
        )
    except Exception as e:
        exceptions.log_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users",
        )


@app.get("/history")
async def get_message_history():
    try:
        return ChatResponse(
            status="success",
            message="Message history retrieved",
            data={
                "messages": manager.message_history[-50:],
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
    try:
        if not message.content:
            raise exceptions.ChatException("Message content is empty")
        formatted_msg = f"{message.nickname}: {message.content}"
        await manager.broadcast(formatted_msg)
        manager.add_to_history(message.nickname, message.content)
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


# Authentication endpoints
@app.post("/api/auth/signup", response_model=TokenResponse)
async def signup(request: SignupRequest):
    """Register a new user"""
    try:
        if not request.nick_name or len(request.nick_name.strip()) < 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nickname must be at least 3 characters",
            )
        if not request.password or len(request.password) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 6 characters",
            )

        user = database.create_user(request.nick_name.strip(), request.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nickname already exists",
            )

        access_token = create_access_token(data={"sub": user["id"]})
        user_data = {k: v for k, v in user.items() if k != "password"}
        return TokenResponse(
            access_token=access_token, token_type="bearer", user=user_data
        )
    except HTTPException:
        raise
    except Exception as e:
        exceptions.log_exception(e)
        error_msg = str(e)
        print(f"Signup error: {error_msg}")  # Debug print
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {error_msg}",
        )


@app.post("/api/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Authenticate user and return JWT token"""
    try:
        user = database.authenticate_user(request.nick_name, request.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid nickname or password",
            )

        access_token = create_access_token(data={"sub": user["id"]})
        return TokenResponse(access_token=access_token, token_type="bearer", user=user)
    except HTTPException:
        raise
    except Exception as e:
        exceptions.log_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to authenticate",
        )


@app.post("/api/auth/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """Logout user (client should discard token)"""
    return {"status": "success", "message": "Logged out successfully"}


@app.get("/api/auth/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information"""
    return current_user


# Chat endpoints
@app.get("/api/chats/private")
async def get_private_chats(current_user: dict = Depends(get_current_user)):
    """Get all private chats for current user"""
    try:
        chats = database.get_user_private_chats(current_user["id"])
        # Enrich with participant names
        for chat in chats:
            other_participant_id = [
                p for p in chat["participants"] if p != current_user["id"]
            ][0]
            other_user = database.get_user_by_id(other_participant_id)
            chat["other_participant"] = (
                other_user["nick_name"] if other_user else "Unknown"
            )
        return {"status": "success", "chats": chats}
    except Exception as e:
        exceptions.log_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get private chats",
        )


@app.post("/api/chats/private")
async def create_private_chat(
    other_user_id: str = Query(...), current_user: dict = Depends(get_current_user)
):
    """Create a new private chat with another user"""
    try:
        other_user = database.get_user_by_id(other_user_id)
        if not other_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        if other_user_id == current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create chat with yourself",
            )

        chat = database.create_private_chat(current_user["id"], other_user_id)
        return {"status": "success", "chat": chat}
    except HTTPException:
        raise
    except Exception as e:
        exceptions.log_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create private chat",
        )


@app.get("/api/chats/private/{chat_id}")
async def get_private_chat_messages(
    chat_id: str, current_user: dict = Depends(get_current_user)
):
    """Get messages from a private chat"""
    try:
        chat = database.get_private_chat(chat_id)
        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found"
            )
        if current_user["id"] not in chat["participants"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

        # Enrich messages with sender names
        messages = []
        for msg in chat["messages"]:
            sender = database.get_user_by_id(msg["sender_id"])
            messages.append(
                {**msg, "sender_name": sender["nick_name"] if sender else "Unknown"}
            )
        return {"status": "success", "messages": messages}
    except HTTPException:
        raise
    except Exception as e:
        exceptions.log_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get messages",
        )


@app.post("/api/chats/private/{chat_id}/message")
async def send_private_message(
    chat_id: str,
    content: str = Form(""),
    file: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user),
):
    """Send a message to a private chat"""
    try:
        chat = database.get_private_chat(chat_id)
        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found"
            )
        if current_user["id"] not in chat["participants"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

        # Handle file upload if present
        attachment_filename = None
        if file and file.filename:
            # Save file with unique name
            file_ext = os.path.splitext(file.filename)[1]
            unique_filename = f"{uuid.uuid4()}{file_ext}"
            file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

            with open(file_path, "wb") as f:
                f.write(await file.read())

            attachment_filename = unique_filename

        message = database.add_private_chat_message(
            chat_id, current_user["id"], content, attachment_filename
        )
        if not message:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send message",
            )

        # Broadcast message to other participants via WebSocket
        message_data = {
            "type": "message",
            "chat_id": chat_id,
            "chat_type": "private",
            "message": {**message, "sender_name": current_user["nick_name"]},
        }

        # Exclude sender's sockets from broadcast
        sender_sockets = manager.get_user_sockets(current_user["id"])
        await manager.send_to_private_chat(
            chat_id, message_data, exclude=sender_sockets
        )

        return {
            "status": "success",
            "message": {**message, "sender_name": current_user["nick_name"]},
        }
    except HTTPException:
        raise
    except Exception as e:
        exceptions.log_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send message",
        )


@app.get("/api/chats/groups")
async def get_groups(current_user: dict = Depends(get_current_user)):
    """Get all groups for current user"""
    try:
        groups = database.get_user_groups(current_user["id"])
        return {"status": "success", "groups": groups}
    except Exception as e:
        exceptions.log_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get groups",
        )


@app.post("/api/chats/groups")
async def create_group(
    name: str = Query(...), current_user: dict = Depends(get_current_user)
):
    """Create a new group"""
    try:
        if not name or len(name.strip()) < 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Group name must be at least 3 characters",
            )

        group = database.create_group(name.strip(), current_user["id"])

        # Broadcast group created event
        await manager.broadcast(json.dumps({"type": "group_created", "group": group}))

        return {"status": "success", "group": group}
    except HTTPException:
        raise
    except Exception as e:
        exceptions.log_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create group",
        )


@app.delete("/api/chats/groups/{group_id}")
async def delete_group(group_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a group (creator only)"""
    try:
        group = database.get_group(group_id)
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
            )

        # Check if user is creator
        if group["creator_id"] != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the group creator can delete this group",
            )

        success = database.delete_group(group_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete group",
            )

        # Broadcast group deleted event
        await manager.broadcast(
            json.dumps({"type": "group_deleted", "group_id": group_id})
        )

        return {"status": "success", "message": "Group deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        exceptions.log_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete group",
        )


@app.get("/api/chats/groups/{group_id}")
async def get_group_messages(
    group_id: str, current_user: dict = Depends(get_current_user)
):
    """Get messages from a group"""
    try:
        group = database.get_group(group_id)
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
            )
        if current_user["id"] not in group["members"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

        # Enrich messages with sender names
        messages = []
        for msg in group["messages"]:
            sender = database.get_user_by_id(msg["sender_id"])
            messages.append(
                {**msg, "sender_name": sender["nick_name"] if sender else "Unknown"}
            )
        return {"status": "success", "messages": messages}
    except HTTPException:
        raise
    except Exception as e:
        exceptions.log_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get messages",
        )


@app.post("/api/chats/groups/{group_id}/message")
async def send_group_message(
    group_id: str,
    content: str = Form(""),
    file: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user),
):
    """Send a message to a group"""
    try:
        group = database.get_group(group_id)
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
            )
        if current_user["id"] not in group["members"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

        # Handle file upload if present
        attachment_filename = None
        if file and file.filename:
            # Save file with unique name
            file_ext = os.path.splitext(file.filename)[1]
            unique_filename = f"{uuid.uuid4()}{file_ext}"
            file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

            with open(file_path, "wb") as f:
                f.write(await file.read())

            attachment_filename = unique_filename

        message = database.add_group_message(
            group_id, current_user["id"], content, attachment_filename
        )
        if not message:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send message",
            )

        # Broadcast message to group members via WebSocket
        message_data = {
            "type": "message",
            "group_id": group_id,
            "chat_type": "group",
            "message": {**message, "sender_name": current_user["nick_name"]},
        }

        # Exclude sender's sockets from broadcast
        sender_sockets = manager.get_user_sockets(current_user["id"])
        await manager.send_to_group_chat(group_id, message_data, exclude=sender_sockets)

        return {
            "status": "success",
            "message": {**message, "sender_name": current_user["nick_name"]},
        }
    except HTTPException:
        raise
    except Exception as e:
        exceptions.log_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send message",
        )


@app.post("/api/chats/groups/{group_id}/members")
async def add_group_member(
    group_id: str,
    user_id: str = Query(...),
    current_user: dict = Depends(get_current_user),
):
    """Add a member to a group"""
    try:
        group = database.get_group(group_id)
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
            )
        if current_user["id"] not in group["members"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

        success = database.add_group_member(group_id, user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to add member"
            )

        return {"status": "success", "message": "Member added successfully"}
    except HTTPException:
        raise
    except Exception as e:
        exceptions.log_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add member",
        )


@app.delete("/api/chats/groups/{group_id}/members/{user_id}")
async def remove_group_member(
    group_id: str, user_id: str, current_user: dict = Depends(get_current_user)
):
    """Remove a member from a group"""
    try:
        group = database.get_group(group_id)
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
            )
        if current_user["id"] not in group["members"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

        success = database.remove_group_member(group_id, user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to remove member",
            )

        return {"status": "success", "message": "Member removed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        exceptions.log_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove member",
        )


@app.get("/api/users")
async def get_users_list(current_user: dict = Depends(get_current_user)):
    """Get all users (for creating chats)"""
    try:
        users = database.get_all_users()
        # Filter out current user
        users = [u for u in users if u["id"] != current_user["id"]]
        return {"status": "success", "users": users}
    except Exception as e:
        exceptions.log_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get users",
        )


# File download endpoint
@app.get("/api/chats/files/{filename}")
async def download_chat_file(
    filename: str,
    token: Optional[str] = Query(None),
    current_user: Optional[dict] = (
        Depends(get_current_user) if not Query(None) else None
    ),
):
    """Download a chat attachment file"""
    try:
        # If token provided in query, validate it
        if token:
            try:
                payload = jwt.decode(
                    token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
                )
                user_id = payload.get("sub")
                if not user_id:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
                    )
            except JWTError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
                )
        elif not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
            )

        file_path = os.path.join(settings.UPLOAD_DIR, filename)
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
            )
        return FileResponse(file_path, filename=filename)
    except HTTPException:
        raise
    except Exception as e:
        exceptions.log_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download file",
        )


# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint with authentication and chat room support"""
    # Don't accept here - will be accepted in manager.connect() after authentication

    # Get token from query params or headers
    token = None
    try:
        # Try to get token from query params
        query_params = dict(websocket.query_params)
        token = query_params.get("token")
        if not token:
            # Try to get from headers
            headers = dict(websocket.headers)
            auth_header = headers.get("authorization") or headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
    except:
        pass

    if not token:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required"
        )
        return

    # Authenticate user
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token"
            )
            return

        user = database.get_user_by_id(user_id)
        if not user:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="User not found"
            )
            return

        nickname = user["nick_name"]
        await manager.connect(websocket, user_id, nickname)
        await manager.send_personal_message(
            {
                "type": "connected",
                "message": f"Welcome {nickname}! You are now connected.",
            },
            websocket,
        )

        while True:
            try:
                data = await websocket.receive_json()
                msg_type = data.get("type")

                if msg_type == "join_private_chat":
                    chat_id = data.get("chat_id")
                    if chat_id:
                        chat = database.get_private_chat(chat_id)
                        if chat and user_id in chat["participants"]:
                            await manager.join_private_chat(websocket, chat_id)
                            await manager.send_personal_message(
                                {
                                    "type": "joined",
                                    "chat_id": chat_id,
                                    "chat_type": "private",
                                },
                                websocket,
                            )

                elif msg_type == "join_group_chat":
                    group_id = data.get("group_id")
                    if group_id:
                        group = database.get_group(group_id)
                        if group and user_id in group["members"]:
                            await manager.join_group_chat(websocket, group_id)
                            await manager.send_personal_message(
                                {
                                    "type": "joined",
                                    "group_id": group_id,
                                    "chat_type": "group",
                                },
                                websocket,
                            )

                elif msg_type == "private_message":
                    chat_id = data.get("chat_id")
                    content = data.get("content")
                    if chat_id and content:
                        chat = database.get_private_chat(chat_id)
                        if chat and user_id in chat["participants"]:
                            message = database.add_private_chat_message(
                                chat_id, user_id, content
                            )
                            if message:
                                message_data = {
                                    "type": "message",
                                    "chat_id": chat_id,
                                    "chat_type": "private",
                                    "message": {**message, "sender_name": nickname},
                                }
                                await manager.send_to_private_chat(
                                    chat_id, message_data, exclude=websocket
                                )
                                await manager.send_personal_message(
                                    {
                                        "type": "message_sent",
                                        "message_id": message["id"],
                                    },
                                    websocket,
                                )

                elif msg_type == "group_message":
                    group_id = data.get("group_id")
                    content = data.get("content")
                    if group_id and content:
                        group = database.get_group(group_id)
                        if group and user_id in group["members"]:
                            message = database.add_group_message(
                                group_id, user_id, content
                            )
                            if message:
                                message_data = {
                                    "type": "message",
                                    "group_id": group_id,
                                    "chat_type": "group",
                                    "message": {**message, "sender_name": nickname},
                                }
                                await manager.send_to_group_chat(
                                    group_id, message_data, exclude=websocket
                                )
                                await manager.send_personal_message(
                                    {
                                        "type": "message_sent",
                                        "message_id": message["id"],
                                    },
                                    websocket,
                                )

            except WebSocketDisconnect:
                raise
            except Exception as e:
                exceptions.log_exception(e)
                await manager.send_personal_message(
                    {
                        "type": "error",
                        "message": "An error occurred processing your message.",
                    },
                    websocket,
                )
    except WebSocketDisconnect:
        nickname = await manager.disconnect(websocket)
        if nickname:
            log_event(f"{nickname} disconnected (WebSocketDisconnect)")
    except JWTError:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token"
        )
    except Exception as e:
        exceptions.log_exception(e)
        nickname = await manager.disconnect(websocket)
        if nickname:
            log_event(f"{nickname} disconnected")


# Contact form endpoint - FIXED VERSION
@app.post("/api/contact")
async def submit_contact_form(
    name: str = Form(...),
    email: str = "ibrahim@myserver.local",
    message: str = Form(...),
    file: Optional[UploadFile] = File(None),
):
    """Submit contact form and send email via SMTP"""
    try:
        # Save attachment if provided
        attachment_filename = None
        attachment_path = None
        if file and file.filename:
            attachment_filename = file.filename
            attachment_path = os.path.join(
                settings.UPLOAD_DIR, f"contact_{file.filename}"
            )
            with open(attachment_path, "wb") as f:
                f.write(await file.read())

        # Save to database
        submission = database.add_contact_submission(
            name, email, message, attachment_filename
        )

        # Send email via SMTP
        email_body = f"""
Contact Form Submission

Name: {name}
Email: {email}
Message: {message}
        """
        if attachment_filename:
            email_body += f"\nAttachment: {attachment_filename}"

        email_sent = await email_service.send_email(
            to_email=email_service.EmailConfig.FROM_EMAIL,
            subject=f"Contact Form: {name}",
            body=email_body,
            attachment_path=attachment_path,
        )

        return {
            "status": "success",
            "message": "Contact form submitted successfully",
            "submission_id": submission["id"],
            "email_sent": email_sent,
        }
    except Exception as e:
        exceptions.log_exception(e)
        print(f"Contact form error: {str(e)}")  # Debug log
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit contact form: {str(e)}",
        )


# Admin dashboard endpoints
# Store email mode preference (IMAP or POP3)
email_mode = "IMAP"  # Default to IMAP


@app.get("/api/admin/emails")
async def get_emails(limit: int = 50, current_user: dict = Depends(get_current_user)):
    """Get emails using IMAP or POP3 based on current mode"""
    # For now, allow any authenticated user to access admin endpoints
    # In production, add role-based access control
    try:
        global email_mode
        if email_mode == "IMAP":
            emails = await email_service.read_emails_imap(limit)
        else:
            emails = await email_service.read_emails_pop3(limit)

        return {
            "status": "success",
            "mode": email_mode,
            "emails": emails,
            "count": len(emails),
        }
    except Exception as e:
        exceptions.log_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve emails",
        )


@app.post("/api/admin/email-mode")
async def toggle_email_mode(
    mode: str = Query(...), current_user: dict = Depends(get_current_user)
):
    """Toggle between IMAP and POP3"""
    global email_mode
    if mode.upper() in ["IMAP", "POP3"]:
        email_mode = mode.upper()
        return {
            "status": "success",
            "message": f"Email mode changed to {email_mode}",
            "mode": email_mode,
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Mode must be IMAP or POP3"
        )


@app.get("/api/admin/email-mode")
async def get_email_mode(current_user: dict = Depends(get_current_user)):
    """Get current email mode"""
    global email_mode
    return {"status": "success", "mode": email_mode}


@app.get("/api/admin/contact-submissions")
async def get_contact_submissions(current_user: dict = Depends(get_current_user)):
    """Get all contact form submissions"""
    try:
        submissions = database.get_contact_submissions()
        return {
            "status": "success",
            "submissions": submissions,
            "count": len(submissions),
        }
    except Exception as e:
        exceptions.log_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve submissions",
        )


@app.post("/api/admin/email-config")
async def update_email_config(
    smtp_server: Optional[str] = Form(None),
    smtp_port: Optional[int] = Form(None),
    smtp_username: Optional[str] = Form(None),
    smtp_password: Optional[str] = Form(None),
    smtp_use_tls: Optional[bool] = Form(None),
    smtp_use_ssl: Optional[bool] = Form(None),
    imap_server: Optional[str] = Form(None),
    imap_port: Optional[int] = Form(None),
    imap_username: Optional[str] = Form(None),
    imap_password: Optional[str] = Form(None),
    imap_use_ssl: Optional[bool] = Form(None),
    pop3_server: Optional[str] = Form(None),
    pop3_port: Optional[int] = Form(None),
    pop3_username: Optional[str] = Form(None),
    pop3_password: Optional[str] = Form(None),
    pop3_use_ssl: Optional[bool] = Form(None),
    from_email: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
):
    """Update email server configuration"""
    try:
        email_service.update_email_config(
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            smtp_username=smtp_username,
            smtp_password=smtp_password,
            smtp_use_tls=smtp_use_tls,
            smtp_use_ssl=smtp_use_ssl,
            imap_server=imap_server,
            imap_port=imap_port,
            imap_username=imap_username,
            imap_password=imap_password,
            imap_use_ssl=imap_use_ssl,
            pop3_server=pop3_server,
            pop3_port=pop3_port,
            pop3_username=pop3_username,
            pop3_password=pop3_password,
            pop3_use_ssl=pop3_use_ssl,
            from_email=from_email,
        )
        return {
            "status": "success",
            "message": "Email configuration updated successfully",
        }
    except Exception as e:
        exceptions.log_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update email configuration",
        )


@app.get("/api/admin/email-config")
async def get_email_config(current_user: dict = Depends(get_current_user)):
    """Get current email configuration (without passwords)"""
    try:
        config = email_service.get_email_config()
        return {"status": "success", "config": config}
    except Exception as e:
        exceptions.log_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get email configuration",
        )


# FTP endpoints
@app.post("/ftp/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        file_path = os.path.join(settings.UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())
        log_event(f"File uploaded: {file.filename}")
        return {
            "status": "success",
            "message": f"{file.filename} uploaded successfully",
        }
    except Exception as e:
        exceptions.log_exception(e)
        raise HTTPException(status_code=500, detail="File upload failed")


@app.get("/ftp/download/{filename}")
async def download_ftp_file(filename: str):
    file_path = os.path.join(settings.UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=filename)


@app.get("/ftp/list")
async def list_files():
    try:
        files = os.listdir(settings.UPLOAD_DIR)
        return {"status": "success", "files": files}
    except Exception as e:
        exceptions.log_exception(e)
        raise HTTPException(status_code=500, detail="Failed to list files")


# Run server
if __name__ == "__main__":
    ssl_config = {}

    if settings.USE_SSL:
        ssl_config = {
            "ssl_certfile": settings.SSL_CERTFILE,
            "ssl_keyfile": settings.SSL_KEYFILE,
        }
        print("🔒 SSL enabled")

    uvicorn.run(
        "server:app",
        host=settings.HOST,  # ✅ 0.0.0.0
        port=settings.PORT,
        reload=True,
        log_level="info",
        **ssl_config,
    )
