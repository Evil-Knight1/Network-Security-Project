"""
Email service for SMTP (sending), IMAP and POP3 (receiving)
Refactored to match Lab Code (smtplib/imaplib) with async wrappers
"""

import smtplib
import imaplib
import poplib
import email
import ssl
import os
from typing import List, Dict, Optional
from email.message import EmailMessage
from email.header import decode_header
from starlette.concurrency import run_in_threadpool


# ----------------------------------------------------------
# EmailConfig
# ----------------------------------------------------------


class EmailConfig:
    # SMTP Defaults
    SMTP_SERVER = "localhost"
    SMTP_PORT = 25
    SMTP_USERNAME = "ibrahim@myserver.local"
    SMTP_PASSWORD = "123456"
    SMTP_USE_TLS = False
    SMTP_USE_SSL = False

    # IMAP Defaults
    IMAP_SERVER = "localhost"
    IMAP_PORT = 143
    IMAP_USERNAME = "ibrahim@myserver.local"
    IMAP_PASSWORD = "123456"
    IMAP_USE_SSL = False  # Change to True if using IMAPS (port 993)
    IMAP_USE_STARTTLS = False
    # POP3 Defaults
    POP3_SERVER = "localhost"
    POP3_PORT = 110
    POP3_USERNAME = "ibrahim@myserver.local"
    POP3_PASSWORD = "123456"
    POP3_USE_SSL = False

    FROM_EMAIL = "ibrahim@myserver.local"


# ----------------------------------------------------------
# Internal Synchronous Functions
# ----------------------------------------------------------


def _sync_send_email(
    to_email: str, subject: str, body: str, attachment_path: Optional[str] = None
) -> bool:
    """Synchronous version of send_email using smtplib"""
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = EmailConfig.FROM_EMAIL
        msg["To"] = to_email
        msg.set_content(body)

        # Attachments
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as f:
                file_data = f.read()
                filename = os.path.basename(attachment_path)
                msg.add_attachment(
                    file_data,
                    maintype="application",
                    subtype="octet-stream",
                    filename=filename,
                )

        # SMTP Connection
        if EmailConfig.SMTP_USE_SSL:
            server = smtplib.SMTP_SSL(EmailConfig.SMTP_SERVER, EmailConfig.SMTP_PORT)
        else:
            server = smtplib.SMTP(EmailConfig.SMTP_SERVER, EmailConfig.SMTP_PORT)
            if EmailConfig.SMTP_USE_TLS:
                server.starttls()

        server.login(EmailConfig.SMTP_USERNAME, EmailConfig.SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()

        print(f"Successfully sent email to {to_email}")
        return True

    except Exception as e:
        print(f"Error sending email: {e}")
        return False


def _sync_read_emails_imap(limit: int = 50) -> List[Dict]:
    """Synchronous IMAP reader with working TLS/SSL support"""
    emails = []
    try:
        print(
            f"Connecting to IMAP server: {EmailConfig.IMAP_SERVER}:{EmailConfig.IMAP_PORT}..."
        )

        # --- Proper IMAP connection handling ---
        if EmailConfig.IMAP_USE_SSL:
            M = imaplib.IMAP4_SSL(EmailConfig.IMAP_SERVER, EmailConfig.IMAP_PORT)
        else:
            M = imaplib.IMAP4(EmailConfig.IMAP_SERVER, EmailConfig.IMAP_PORT)
            if getattr(EmailConfig, "IMAP_USE_STARTTLS", False):
                print("Starting IMAP TLS...")
                M.starttls()

        print("Connection successful. Logging in...")
        M.login(EmailConfig.IMAP_USERNAME, EmailConfig.IMAP_PASSWORD)
        print(f"Logged in as: {EmailConfig.IMAP_USERNAME}")

        # Select mailbox
        M.select("INBOX")
        status, messages = M.search(None, "ALL")
        if status != "OK":
            print("IMAP search failed.")
            return emails

        email_ids = messages[0].split()
        email_ids = email_ids[-limit:] if len(email_ids) > limit else email_ids

        # Fetch emails
        for email_id in reversed(email_ids):
            try:
                status, msg_data = M.fetch(email_id, "(RFC822)")
                if status != "OK":
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                subject, enc = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(enc or "utf-8")

                email_data = {
                    "id": email_id.decode(),
                    "subject": subject,
                    "from": msg["From"],
                    "to": msg["To"],
                    "date": msg["Date"],
                    "body": "",
                    "attachments": [],
                }

                # Handle body & attachments
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        content_disp = str(part.get("Content-Disposition"))

                        if (
                            content_type == "text/plain"
                            and "attachment" not in content_disp
                        ):
                            try:
                                email_data["body"] = part.get_payload(
                                    decode=True
                                ).decode()
                            except:
                                pass

                        elif "attachment" in content_disp:
                            filename = part.get_filename()
                            if filename:
                                email_data["attachments"].append(filename)

                else:
                    try:
                        email_data["body"] = msg.get_payload(decode=True).decode()
                    except:
                        pass

                emails.append(email_data)

            except Exception as e:
                print(f"Error processing email ID {email_id}: {e}")

        M.close()
        M.logout()
        print("IMAP connection closed.")

    except Exception as e:
        print(f"Error reading emails via IMAP: {e}")

    return emails


def _sync_read_emails_pop3(limit: int = 50) -> List[Dict]:
    """POP3 email reader"""
    emails = []
    try:
        if EmailConfig.POP3_USE_SSL:
            mail = poplib.POP3_SSL(EmailConfig.POP3_SERVER, EmailConfig.POP3_PORT)
        else:
            mail = poplib.POP3(EmailConfig.POP3_SERVER, EmailConfig.POP3_PORT)

        mail.user(EmailConfig.POP3_USERNAME)
        mail.pass_(EmailConfig.POP3_PASSWORD)

        num_messages = len(mail.list()[1])
        start = max(0, num_messages - limit)

        for i in range(start, num_messages):
            try:
                resp, lines, octets = mail.retr(i + 1)
                msg_content = b"\n".join(lines)
                msg = email.message_from_bytes(msg_content)

                email_data = {
                    "id": str(i + 1),
                    "subject": msg["Subject"] or "",
                    "from": msg["From"] or "",
                    "to": msg["To"] or "",
                    "date": msg["Date"] or "",
                    "body": "",
                    "attachments": [],
                }

                if msg.is_multipart():
                    for part in msg.walk():
                        ctype = part.get_content_type()
                        disp = str(part.get("Content-Disposition"))

                        if ctype == "text/plain" and "attachment" not in disp:
                            try:
                                email_data["body"] = part.get_payload(
                                    decode=True
                                ).decode()
                            except:
                                pass
                        elif "attachment" in disp:
                            filename = part.get_filename()
                            if filename:
                                email_data["attachments"].append(filename)
                else:
                    try:
                        email_data["body"] = msg.get_payload(decode=True).decode()
                    except:
                        pass

                emails.append(email_data)

            except Exception as e:
                print(f"Error processing POP3 email {i + 1}: {e}")

        mail.quit()

    except Exception as e:
        print(f"Error reading emails via POP3: {e}")

    return emails


# ----------------------------------------------------------
# Async API Wrappers
# ----------------------------------------------------------


async def send_email(
    to_email: str, subject: str, body: str, attachment_path=None
) -> bool:
    return await run_in_threadpool(
        _sync_send_email, to_email, subject, body, attachment_path
    )


async def read_emails_imap(limit: int = 50) -> List[Dict]:
    return await run_in_threadpool(_sync_read_emails_imap, limit)


async def read_emails_pop3(limit: int = 50) -> List[Dict]:
    return await run_in_threadpool(_sync_read_emails_pop3, limit)


# ----------------------------------------------------------
# Helper to update config
# ----------------------------------------------------------


def update_email_config(
    smtp_server=None,
    smtp_port=None,
    smtp_username=None,
    smtp_password=None,
    smtp_use_tls=None,
    smtp_use_ssl=None,
    imap_server=None,
    imap_port=None,
    imap_username=None,
    imap_password=None,
    imap_use_ssl=None,
    pop3_server=None,
    pop3_port=None,
    pop3_username=None,
    pop3_password=None,
    pop3_use_ssl=None,
    from_email=None,
):
    if smtp_server:
        EmailConfig.SMTP_SERVER = smtp_server
    if smtp_port:
        EmailConfig.SMTP_PORT = smtp_port
    if smtp_username:
        EmailConfig.SMTP_USERNAME = smtp_username
    if smtp_password:
        EmailConfig.SMTP_PASSWORD = smtp_password
    if smtp_use_tls is not None:
        EmailConfig.SMTP_USE_TLS = smtp_use_tls
    if smtp_use_ssl is not None:
        EmailConfig.SMTP_USE_SSL = smtp_use_ssl

    if imap_server:
        EmailConfig.IMAP_SERVER = imap_server
    if imap_port:
        EmailConfig.IMAP_PORT = imap_port
    if imap_username:
        EmailConfig.IMAP_USERNAME = imap_username
    if imap_password:
        EmailConfig.IMAP_PASSWORD = imap_password
    if imap_use_ssl is not None:
        EmailConfig.IMAP_USE_SSL = imap_use_ssl

    if pop3_server:
        EmailConfig.POP3_SERVER = pop3_server
    if pop3_port:
        EmailConfig.POP3_PORT = pop3_port
    if pop3_username:
        EmailConfig.POP3_USERNAME = pop3_username
    if pop3_password:
        EmailConfig.POP3_PASSWORD = pop3_password
    if pop3_use_ssl is not None:
        EmailConfig.POP3_USE_SSL = pop3_use_ssl

    if from_email:
        EmailConfig.FROM_EMAIL = from_email


def get_email_config() -> Dict:
    return {
        "smtp_server": EmailConfig.SMTP_SERVER,
        "smtp_port": EmailConfig.SMTP_PORT,
        "smtp_username": EmailConfig.SMTP_USERNAME,
        "smtp_use_tls": EmailConfig.SMTP_USE_TLS,
        "smtp_use_ssl": EmailConfig.SMTP_USE_SSL,
        "imap_server": EmailConfig.IMAP_SERVER,
        "imap_port": EmailConfig.IMAP_PORT,
        "imap_username": EmailConfig.IMAP_USERNAME,
        "imap_use_ssl": EmailConfig.IMAP_USE_SSL,
        "pop3_server": EmailConfig.POP3_SERVER,
        "pop3_port": EmailConfig.POP3_PORT,
        "pop3_username": EmailConfig.POP3_USERNAME,
        "pop3_use_ssl": EmailConfig.POP3_USE_SSL,
        "from_email": EmailConfig.FROM_EMAIL,
    }
