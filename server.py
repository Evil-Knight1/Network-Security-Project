"""
FASTAPI CHAT SERVER WITH WEBSOCKET SUPPORT + REST "FTP" (upload/download/list)
نسخة محسّنة - تشتغل على الشبكة + Pydantic V2
"""

import os
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, field_validator  # ✅ Pydantic V2
from contextlib import asynccontextmanager  # ✅ للـ lifespan

import uvicorn
import asyncio

# Dummy exceptions module
class _DummyExc(Exception):
    def log(self, *a, **k): pass

class exceptions:
    class ChatException(Exception):
        def __init__(self, *a, **k): super().__init__(*a)
        def log(self, *a, **k): pass
    @staticmethod
    def log_exception(e): print("Exception:", e)
    @staticmethod
    def format_error_for_user(e): return str(e)

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
            raise ValueError(f"Message too long (max {settings.MAX_MESSAGE_LENGTH} chars)")
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

# ───────────────────────────────────────────
# Connection manager
# ───────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[WebSocket, dict] = {}
        self.message_history: List[dict] = []
        self.max_history = 100

    async def connect(self, websocket: WebSocket, nickname: str):
        await websocket.accept()
        self.active_connections[websocket] = {
            "nickname": nickname,
            "connected_at": datetime.now(),
            "message_count": 0,
        }
        log_event(f"{nickname} connected via WebSocket")
        await self.send_personal_message(f"Welcome {nickname}! You are now connected.", websocket)
        await self.broadcast(f"{nickname} joined the chat!", exclude=websocket)
        await self.send_history(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            user_info = self.active_connections[websocket]
            nickname = user_info["nickname"]
            del self.active_connections[websocket]
            log_event(f"{nickname} disconnected")
            return nickname
        return None

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except Exception as e:
            exceptions.log_exception(e)
            raise

    async def broadcast(self, message: str, exclude: Optional[WebSocket] = None):
        disconnected = []
        for connection in list(self.active_connections.keys()):
            if connection != exclude:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    exceptions.log_exception(e)
                    disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)

    async def send_history(self, websocket: WebSocket):
        if self.message_history:
            history_msg = "\n--- Recent Messages ---\n"
            for msg in self.message_history[-20:]:
                history_msg += f"[{msg['timestamp']}] {msg['nickname']}: {msg['content']}\n"
            history_msg += "--- End of History ---\n"
            await self.send_personal_message(history_msg, websocket)

    def add_to_history(self, nickname: str, content: str):
        self.message_history.append({
            "nickname": nickname,
            "content": content,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        })
        if len(self.message_history) > self.max_history:
            self.message_history = self.message_history[-self.max_history:]

    def get_online_users(self) -> List[UserInfo]:
        return [
            UserInfo(
                nickname=info["nickname"],
                connected_at=info["connected_at"],
                message_count=info["message_count"],
            ) for info in self.active_connections.values()
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
        log_event("=" * 70)
        log_event("FastAPI Chat Server Started")
        log_event(f"Host: {settings.HOST}")
        log_event(f"Port: {settings.PORT}")
        log_event(f"SSL Enabled: {settings.USE_SSL}")
        log_event("=" * 70)
        print(f"🚀 Server started on {settings.HOST}:{settings.PORT}")
        scheme = "https" if settings.USE_SSL else "http"
        print(f"📡 WebSocket endpoint: {'wss' if settings.USE_SSL else 'ws'}://{settings.HOST}:{settings.PORT}/ws/{{nickname}}")
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
    description="Real-time chat server with WebSocket + FTP REST endpoints",
    version="2.0.0",
    lifespan=lifespan  # ✅ استخدام lifespan
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
            "details": getattr(exc, "args", [])
        }
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
        content={"status": "error", "message": "An unexpected error occurred", "error": str(exc)}
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
        }
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
        }
    )

@app.get("/users", response_model=ChatResponse)
async def get_users():
    try:
        users = manager.get_online_users()
        return ChatResponse(
            status="success",
            message=f"Found {len(users)} online users",
            data={"users": [u.model_dump() for u in users], "count": len(users)}
        )
    except Exception as e:
        exceptions.log_exception(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve users")

@app.get("/history")
async def get_message_history():
    try:
        return ChatResponse(
            status="success",
            message="Message history retrieved",
            data={"messages": manager.message_history[-50:], "count": len(manager.message_history)}
        )
    except Exception as e:
        exceptions.log_exception(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve message history")

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
            data={"sent_at": datetime.now().isoformat()}
        )
    except exceptions.ChatException as e:
        exceptions.log_exception(e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exceptions.format_error_for_user(e))
    except Exception as e:
        exceptions.log_exception(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send message")

# WebSocket endpoint
@app.websocket("/ws/{nickname}")
async def websocket_endpoint(websocket: WebSocket, nickname: str):
    if not nickname or len(nickname) > 50:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    nickname = nickname.strip()
    try:
        await manager.connect(websocket, nickname)
        while True:
            try:
                data = await websocket.receive_text()
                if data.lower() == "quit":
                    break
                if data.lower() == "/users":
                    users = manager.get_online_users()
                    user_list = "\n".join([f"- {u.nickname}" for u in users])
                    await manager.send_personal_message(f"Online users:\n{user_list}", websocket)
                    continue
                if not data.strip():
                    continue
                if len(data) > settings.MAX_MESSAGE_LENGTH:
                    await manager.send_personal_message(f"Error: Message too long (max {settings.MAX_MESSAGE_LENGTH} chars)", websocket)
                    continue
                manager.active_connections[websocket]["message_count"] += 1
                formatted_msg = f"{nickname}: {data}"
                log_event(formatted_msg)
                manager.add_to_history(nickname, data)
                await manager.broadcast(formatted_msg, exclude=websocket)
            except WebSocketDisconnect:
                raise
            except Exception as e:
                exceptions.log_exception(e)
                await manager.send_personal_message("An error occurred processing your message.", websocket)
    except WebSocketDisconnect:
        nickname = manager.disconnect(websocket)
        if nickname:
            await manager.broadcast(f"{nickname} left the chat!")
            log_event(f"{nickname} disconnected (WebSocketDisconnect)")
    except Exception as e:
        exceptions.log_exception(e)
        nickname = manager.disconnect(websocket)
        if nickname:
            await manager.broadcast(f"{nickname} left the chat!")

# FTP endpoints
@app.post("/ftp/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        file_path = os.path.join(settings.UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())
        log_event(f"File uploaded: {file.filename}")
        return {"status": "success", "message": f"{file.filename} uploaded successfully"}
    except Exception as e:
        exceptions.log_exception(e)
        raise HTTPException(status_code=500, detail="File upload failed")

@app.get("/ftp/download/{filename}")
async def download_file(filename: str):
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
            "ssl_keyfile": settings.SSL_KEYFILE
        }
        print("🔒 SSL enabled")

    uvicorn.run(
        "server:app",
        host=settings.HOST,  # ✅ 0.0.0.0
        port=settings.PORT,
        reload=True,          
        log_level="info",
        **ssl_config
    )