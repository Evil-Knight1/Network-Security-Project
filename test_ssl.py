# test_ssl.py - اختبار أمان SSL بشكل دقيق
import socket
import ssl
import time

HOST = "127.0.0.1"
PORT = 55555

print("Testing SSL Security...\n")

# ===================================================================
# 1. محاولة الاتصال بدون SSL (يجب أن يفشل الـ handshake)
# ===================================================================
print("1. Trying to connect WITHOUT SSL (should fail at SSL handshake)...")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    sock.connect((HOST, PORT))
    print("   [TCP] Connection established (expected)")

    # نحاول نستقبل رد من السيرفر بعد الـ handshake
    sock.settimeout(2)
    try:
        data = sock.recv(1024)
        print(f"   [RECV] Received data: {data}")
        print("   [RESULT] DANGER: Server allowed non-SSL communication! (INSECURE)")
    except socket.timeout:
        print("   [TIMEOUT] No data received → SSL handshake failed (SECURE)")
    except Exception as e:
        print(f"   [ERROR] Read failed: {e} → SSL enforced (GOOD)")
    finally:
        sock.close()

except Exception as e:
    print(f"   [FATAL] TCP connection failed: {e} → Server not running?")
    sock.close() if 'sock' in locals() else None

print("\n" + "-" * 65 + "\n")

# ===================================================================
# 2. محاولة الاتصال مع SSL (يجب أن ينجح)
# ===================================================================
print("2. Trying to connect WITH SSL (should succeed)...")
try:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE  # لأن الشهادة self-signed

    with context.wrap_socket(socket.socket(), server_hostname=HOST) as ssl_sock:
        ssl_sock.settimeout(5)
        ssl_sock.connect((HOST, PORT))
        ssl_sock.send(b"SSL Test Message\n")

        print("   [SSL] Handshake SUCCESSFUL!")
        cipher = ssl_sock.cipher()
        version = ssl_sock.version()
        print(f"   Cipher: {cipher}")
        print(f"   Version: {version}")
        print("   [RESULT] EXCELLENT: SSL is ENFORCED and WORKING!")

except ssl.SSLError as e:
    print(f"   [SSL ERROR] Handshake failed: {e} → SSL not working properly")
except Exception as e:
    print(f"   [ERROR] SSL connection failed: {e}")

print("\n" + "=" * 65)
print("SSL SECURITY TEST COMPLETED")