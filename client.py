"""
FASTAPI WEBSOCKET CLIENT (async) + REST "FTP" commands
"""

import asyncio
import ssl
import websockets
import json
import sys
import os
from datetime import datetime

import aiohttp

# If you have an exceptions module, this client uses it; otherwise behavior falls back to simple prints.
try:
    import exceptions
except Exception:
    class exceptions:
        @staticmethod
        def log_exception(e): print("Exception:", e)

# CONFIG
HOST = "127.0.0.1"
PORT = 8000
LOG_FILE = "client_log.txt"

def log_event(message: str):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        print(f"Failed to log: {e}")

def safe_print(message: str):
    print(message)
    log_event(message)

class ChatClient:
    def __init__(self, host: str, port: int, nickname: str, use_ssl: bool = False):
        self.host = host
        self.port = port
        self.nickname = nickname
        self.websocket = None
        self.running = False
        self.use_ssl = use_ssl
        ws_scheme = "wss" if use_ssl else "ws"
        self.ws_url = f"{ws_scheme}://{host}:{port}/ws/{nickname}"
        self.http_scheme = "https" if use_ssl else "http"
        self.session = None  # aiohttp session

    async def connect(self):
        try:
            safe_print(f"🔌 Connecting to {self.ws_url}...")
            ssl_ctx = ssl._create_unverified_context() if self.use_ssl else None
            self.websocket = await websockets.connect(self.ws_url, ping_interval=20, ping_timeout=10, ssl=ssl_ctx)
            self.running = True
            safe_print("✅ Connected to server!")
            return True
        except Exception as e:
            exceptions.log_exception(e)
            safe_print(f"❌ Connection failed: {e}")
            return False

    async def receive_messages(self):
        try:
            while self.running:
                try:
                    message = await self.websocket.recv()
                    safe_print(f"\r{message}")
                    print("You: ", end="", flush=True)
                except websockets.exceptions.ConnectionClosed:
                    safe_print("\n⚠  Connection closed by server")
                    self.running = False
                    break
                except Exception as e:
                    exceptions.log_exception(e)
                    if self.running:
                        safe_print(f"\n⚠  Error receiving message: {str(e)}")
        except Exception as e:
            exceptions.log_exception(e)
            self.running = False

    async def send_message(self, message: str):
        try:
            if not self.websocket or not self.running:
                raise Exception("Not connected to server")
            await self.websocket.send(message)
            log_event(f"Sent: {message}")
        except websockets.exceptions.ConnectionClosed:
            exceptions.log_exception("Connection closed while sending")
            safe_print("❌ Connection closed. Cannot send message.")
            self.running = False
        except Exception as e:
            exceptions.log_exception(e)
            safe_print(f"❌ Failed to send message: {str(e)}")

    # ========== FTP (REST) helpers ==========
    async def ftp_upload(self, file_path: str):
        if not os.path.exists(file_path):
            safe_print("❌ File does not exist")
            return
        url = f"{self.http_scheme}://{self.host}:{self.port}/ftp/upload"
        try:
            async with aiohttp.ClientSession() as session:
                form = aiohttp.FormData()
                form.add_field("file", open(file_path, "rb"), filename=os.path.basename(file_path))
                async with session.post(url, data=form) as resp:
                    try:
                        result = await resp.json()
                    except Exception:
                        result_text = await resp.text()
                        safe_print(f"📤 Upload response: {resp.status} {result_text}")
                        return
                    safe_print(f"📤 Upload result: {result}")
        except Exception as e:
            exceptions.log_exception(e)
            safe_print(f"❌ Upload failed: {e}")

    async def ftp_download(self, filename: str):
        url = f"{self.http_scheme}://{self.host}:{self.port}/ftp/download/{filename}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        safe_print(f"❌ Download failed ({resp.status}): {text}")
                        return
                    data = await resp.read()
                    with open(filename, "wb") as f:
                        f.write(data)
                    safe_print(f"📥 Download completed: {filename}")
        except Exception as e:
            exceptions.log_exception(e)
            safe_print(f"❌ Download failed: {e}")

    async def ftp_list(self):
        url = f"{self.http_scheme}://{self.host}:{self.port}/ftp/list"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    result = await resp.json()
                    safe_print(f"📂 Files on server: {result.get('files', [])}")
        except Exception as e:
            exceptions.log_exception(e)
            safe_print(f"❌ Failed to list files: {e}")

    # ========== chat send loop includes ftp commands ==========
    async def send_messages(self):
        try:
            print("\n" + "=" * 60)
            print("📝 You can now start chatting!")
            print("   Commands:")
            print("   - /users            : List online users")
            print("   - /quit             : Exit the chat")
            print("   - /upload <path>    : Upload a file to server")
            print("   - /download <name>  : Download a file from server")
            print("   - /files            : List files on server")
            print("=" * 60 + "\n")

            loop = asyncio.get_event_loop()
            while self.running:
                try:
                    print("You: ", end="", flush=True)
                    message = await loop.run_in_executor(None, sys.stdin.readline)
                    message = message.strip()
                    if not message:
                        continue

                    # FTP commands
                    if message.startswith("/upload "):
                        file_path = message[len("/upload "):].strip()
                        await self.ftp_upload(file_path)
                        continue

                    if message.startswith("/download "):
                        filename = message[len("/download "):].strip()
                        await self.ftp_download(filename)
                        continue

                    if message == "/files":
                        await self.ftp_list()
                        continue

                    # Quit
                    if message.lower() in ["/quit", "quit", "exit"]:
                        safe_print("👋 Disconnecting...")
                        try:
                            await self.send_message("quit")
                        except:
                            pass
                        self.running = False
                        break

                    # default: send chat message
                    await self.send_message(message)

                except KeyboardInterrupt:
                    safe_print("\n\n⚠  Interrupted by user")
                    self.running = False
                    break
                except Exception as e:
                    exceptions.log_exception(e)
                    if self.running:
                        safe_print(f"❌ Error: {str(e)}")
        except Exception as e:
            exceptions.log_exception(e)
            self.running = False

    async def disconnect(self):
        try:
            self.running = False
            if self.websocket:
                await self.websocket.close()
                safe_print("✅ Disconnected from server")
        except Exception as e:
            exceptions.log_exception(e)

    async def run(self):
        try:
            if not await self.connect():
                return
            receive_task = asyncio.create_task(self.receive_messages())
            send_task = asyncio.create_task(self.send_messages())
            done, pending = await asyncio.wait([receive_task, send_task], return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        except Exception as e:
            exceptions.log_exception(e)
            safe_print(f"❌ Client error: {e}")
        finally:
            await self.disconnect()

# Main
async def main():
    print("\n" + "=" * 60)
    print("           💬 FASTAPI CHAT CLIENT")
    print("=" * 60)
    nickname = input("\n👤 Enter your nickname: ").strip()
    if not nickname:
        nickname = "Anonymous"
        print(f"ℹ  Using default nickname: {nickname}")

    # If you run server with SSL, set use_ssl=True
    client = ChatClient(HOST, PORT, nickname, use_ssl=False)
    await client.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)
