# FastAPI Chat Server - Setup Guide

bash

# Install dependencies

pip install -r requirements.txt

# Or install manually

pip install fastapi uvicorn[standard] websockets pydantic python-multipart

## 📁 File Structure

project/
├── server.py # FastAPI server with WebSocket
├── client.py # WebSocket client
├── exceptions.py # Exception handling module (existing)
├── requirements.txt # Python dependencies
├── server_log.txt # Server activity log (auto-generated)
├── client_log.txt # Client activity log (auto-generated)
└── server_exception_log.txt # Exception log (auto-generated)

## ⚡ Quick Start

### 1. Start the Server

bash

# Basic start

python server.py

# Or with uvicorn directly

uvicorn server:app --host 127.0.0.1 --port 8000 --reload

# With SSL (make sure you have server.crt and server.key)

uvicorn server:app --host 127.0.0.1 --port 8000 --ssl-keyfile server.key --ssl-certfile server.crt

### 2. Start Client(s)

bash

# In another terminal

python client.py

You can start multiple clients in different terminals!

## 📡 API Endpoints

### REST API

| Method | Endpoint | Description                   |
| ------ | -------- | ----------------------------- |
| GET    | /        | Health check                  |
| GET    | /health  | Detailed health status        |
| GET    | /users   | List online users             |
| GET    | /history | Get message history           |
| POST   | /message | Send message via REST         |
| GET    | /docs    | Interactive API documentation |

### WebSocket

ws://127.0.0.1:8000/ws/{nickname}

## 🔍 Testing the API

### 1. Using Browser

Open in your browser:

- API Docs: http://127.0.0.1:8000/docs
- Health Check: http://127.0.0.1:8000/health

### 2. Using curl

bash

# Health check

curl http://127.0.0.1:8000/health

# Get online users

curl http://127.0.0.1:8000/users

# Send message via REST

curl -X POST http://127.0.0.1:8000/message \
 -H "Content-Type: application/json" \
 -d '{"nickname": "API User", "content": "Hello from REST!"}'

# Get message history

curl http://127.0.0.1:8000/history

### 3. Using Python requests

python
import requests

# Health check

response = requests.get("http://127.0.0.1:8000/health")
print(response.json())

# Send message

response = requests.post(
"http://127.0.0.1:8000/message",
json={"nickname": "Bob", "content": "Hello!"}
)
print(response.json())

## 🎯 Client Commands

When connected, you can use these commands:

- /users - List all online users
- /quit or quit or exit - Disconnect from chat

## 🔧 Configuration

Edit the Settings class in server.py:

python
class Settings:
HOST = "127.0.0.1" # Server host
PORT = 8000 # Server port
BUFFER_SIZE = 1024 # Buffer size
MAX_MESSAGE_LENGTH = 10000 # Max message length
LOG_FILE = "server_log.txt" # Log file path
USE_SSL = False # Enable/disable SSL

## 🔒 SSL Configuration (Optional)

To enable SSL:

1. Generate SSL certificates:
   bash
   openssl req -x509 -newkey rsa:4096 -keyout server.key -out server.crt -days 365 -nodes

2. Set USE_SSL = True in Settings

3. Run server:
   bash
   python server.py

Client will need to use wss:// instead of ws://

## 🐛 Exception Handling

All exceptions are logged to:

- server_exception_log.txt - Detailed exception traces
- server_log.txt - General server events
- client_log.txt - Client events

Exception types handled:

- ConnectionError - Connection failures
- DisconnectionError - Disconnection issues
- MessageSendError - Message sending failures
- MessageReceiveError - Message receiving failures
- InvalidMessageFormatError - Invalid message format
- And more...

## 📊 Features

### ✅ Implemented

- ✅ WebSocket real-time communication
- ✅ REST API endpoints
- ✅ Comprehensive exception handling
- ✅ Message history (last 100 messages)
- ✅ Online user tracking
- ✅ Automatic logging
- ✅ CORS enabled
- ✅ SSL/TLS support
- ✅ Input validation with Pydantic
- ✅ Graceful shutdown
- ✅ Multiple client support
- ✅ Interactive API docs (Swagger UI)

### 🔄 Compared to Original

| Feature    | Original    | New FastAPI      |
| ---------- | ----------- | ---------------- |
| Protocol   | TCP/UDP     | WebSocket + REST |
| Framework  | Raw sockets | FastAPI          |
| Server     | Threading   | Async/Await      |
| API        | None        | REST + WebSocket |
| Docs       | None        | Auto-generated   |
| Validation | Manual      | Pydantic         |
| CORS       | None        | Built-in         |

## 🚦 Production Deployment

For production, consider:

1. _Disable reload mode_:
   python
   uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)

2. _Use a process manager_ (e.g., systemd, supervisor, pm2)

3. _Set up a reverse proxy_ (nginx, Apache)

4. _Enable SSL/TLS_

5. _Add authentication_ (JWT, OAuth2)

6. _Rate limiting_ (slowapi)

7. _Database_ for message persistence

8. _Redis_ for session management

## 🤝 Contributing

Key differences from original implementation:

1. _No UDP_ - WebSocket provides bidirectional communication
2. _Async/await_ - Better performance and scalability
3. _REST API_ - Additional flexibility
4. _Auto docs_ - Built-in API documentation
5. _Validation_ - Automatic input validation

## 📝 Notes

- WebSocket keeps connections alive with ping/pong
- Message history limited to 100 messages (configurable)
- Nicknames limited to 50 characters
- Messages limited to 10,000 characters (configurable)
- Server auto-reloads on code changes in dev mode

## 🐞 Troubleshooting

### Port already in use

bash

# Linux/Mac

lsof -ti:8000 | xargs kill -9

# Windows

netstat -ano | findstr :8000
taskkill /PID <PID> /F

### Connection refused

- Make sure server is running
- Check firewall settings
- Verify HOST and PORT settings

### WebSocket connection fails

- Check browser console for errors
- Ensure WebSocket URL is correct
- Verify server is accepting WebSocket connections

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [WebSocket Protocol](https://websockets.readthedocs.io/)
- [Uvicorn Documentation](https://www.uvicorn.org/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
