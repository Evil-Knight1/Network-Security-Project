"""
═══════════════════════════════════════════════════════════════════════
    FASTAPI WEBSOCKET CLIENT
═══════════════════════════════════════════════════════════════════════
"""

import asyncio
import ssl
import websockets
import json
import sys
from datetime import datetime
import exceptions

#    CONFIGURATION

HOST = "127.0.0.1"
PORT = 8000
LOG_FILE = "client_log.txt"

#     UTILITY FUNCTIONS


def log_event(message: str):
    """Log events to file"""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        print(f"Failed to log: {e}")


def safe_print(message: str):
    """Print and log message"""
    print(message)
    log_event(message)


#  CLIENT CLASS


class ChatClient:
    def __init__(self, host: str, port: int, nickname: str):
        self.host = host
        self.port = port
        self.nickname = nickname
        self.websocket = None
        self.running = False
        self.ws_url = f"wss://{host}:{port}/ws/{nickname}"

    async def connect(self):
        """Connect to the WebSocket server"""
        try:
            safe_print(f"🔌 Connecting to {self.ws_url}...")
            self.websocket = await websockets.connect(
                self.ws_url,
                ping_interval=20,
                ping_timeout=10,
                ssl=ssl._create_unverified_context(),
            )
            self.running = True
            safe_print("✅ Connected to server!")
            return True

        except websockets.exceptions.InvalidStatusCode as e:
            exceptions.log_exception(
                exceptions.ConnectionError(f"Invalid status code: {e.status_code}", e)
            )
            safe_print(f"❌ Connection failed: Invalid status code {e.status_code}")
            return False

        except Exception as e:
            exceptions.log_exception(
                exceptions.ConnectionError(f"Failed to connect to server", e)
            )
            safe_print(f"❌ Connection failed: {str(e)}")
            return False

    async def receive_messages(self):
        """Continuously receive messages from server"""
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
                    exceptions.log_exception(
                        exceptions.MessageReceiveError("Error receiving message", e)
                    )
                    if self.running:
                        safe_print(f"\n⚠  Error receiving message: {str(e)}")

        except Exception as e:
            exceptions.log_exception(
                exceptions.MessageReceiveError("Fatal error in receive loop", e)
            )
            self.running = False

    async def send_message(self, message: str):
        """Send a message to the server"""
        try:
            if not self.websocket or not self.running:
                raise exceptions.ConnectionError("Not connected to server")

            await self.websocket.send(message)
            log_event(f"Sent: {message}")

        except websockets.exceptions.ConnectionClosed:
            exceptions.log_exception(
                exceptions.DisconnectionError("Connection closed while sending")
            )
            safe_print("❌ Connection closed. Cannot send message.")
            self.running = False

        except Exception as e:
            exceptions.log_exception(
                exceptions.MessageSendError(f"Failed to send message", e)
            )
            safe_print(f"❌ Failed to send message: {str(e)}")

    async def send_messages(self):
        """Handle user input and send messages"""
        try:
            print("\n" + "=" * 60)
            print("📝 You can now start chatting!")
            print("   Commands:")
            print("   - /users    : List online users")
            print("   - /quit     : Exit the chat")
            print("=" * 60 + "\n")

            # Use asyncio to read from stdin
            loop = asyncio.get_event_loop()

            while self.running:
                try:
                    print("You: ", end="", flush=True)

                    # Read input in a non-blocking way
                    message = await loop.run_in_executor(None, sys.stdin.readline)
                    message = message.strip()

                    if not message:
                        continue

                    # Handle quit command
                    if message.lower() in ["/quit", "quit", "exit"]:
                        safe_print("👋 Disconnecting...")
                        await self.send_message("quit")
                        self.running = False
                        break

                    # Send the message
                    await self.send_message(message)

                except KeyboardInterrupt:
                    safe_print("\n\n⚠  Interrupted by user")
                    self.running = False
                    break

                except Exception as e:
                    if self.running:
                        exceptions.log_exception(
                            exceptions.MessageSendError("Error in send loop", e)
                        )
                        safe_print(f"❌ Error: {str(e)}")

        except Exception as e:
            exceptions.log_exception(
                exceptions.ChatException("Fatal error in send loop", e)
            )
            self.running = False

    async def disconnect(self):
        """Disconnect from the server"""
        try:
            self.running = False
            if self.websocket:
                await self.websocket.close()
                safe_print("✅ Disconnected from server")
        except Exception as e:
            exceptions.log_exception(
                exceptions.DisconnectionError("Error during disconnect", e)
            )

    async def run(self):
        """Main client loop"""
        try:
            # Connect to server
            if not await self.connect():
                return

            # Run receive and send tasks concurrently
            receive_task = asyncio.create_task(self.receive_messages())
            send_task = asyncio.create_task(self.send_messages())

            # Wait for either task to complete
            done, pending = await asyncio.wait(
                [receive_task, send_task], return_when=asyncio.FIRST_COMPLETED
            )

            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        except Exception as e:
            exceptions.log_exception(
                exceptions.ChatException("Error in main client loop", e)
            )
            safe_print(f"❌ Client error: {str(e)}")

        finally:
            await self.disconnect()


# ═══════════════════════════════════════════════════════════════════════
#                           MAIN FUNCTION
# ═══════════════════════════════════════════════════════════════════════


async def main():
    """Main entry point"""
    print("\n" + "=" * 60)
    print("           💬 FASTAPI CHAT CLIENT")
    print("=" * 60)

    # Get nickname from user
    nickname = input("\n👤 Enter your nickname: ").strip()

    if not nickname:
        nickname = "Anonymous"
        print(f"ℹ  Using default nickname: {nickname}")

    # Validate nickname
    if len(nickname) > 50:
        print("❌ Nickname too long (max 50 characters)")
        return

    # Create and run client
    try:
        client = ChatClient(HOST, PORT, nickname)
        await client.run()

    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")

    except Exception as e:
        exceptions.log_exception(exceptions.ChatException("Fatal client error", e))
        print(f"\n❌ Fatal error: {str(e)}")

    finally:
        print("\n" + "=" * 60)
        print("           Client terminated")
        print("=" * 60 + "\n")


# ═══════════════════════════════════════════════════════════════════════
#                           ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {str(e)}")
        sys.exit(1)
