# database.py
"""
Database module for JSON-based persistent storage
Handles users, private chats, groups, and contact submissions
Uses Argon2 for password hashing (no 72-byte limit)
"""

import json
import os
import threading
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from passlib.context import CryptContext

# Password hashing context using Argon2
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# Database file path
DB_FILE = "database.json"

# Thread lock for file operations
db_lock = threading.Lock()

# Default database structure
DEFAULT_DB = {"users": [], "private_chats": [], "groups": [], "contact_submissions": []}


def init_database():
    """Initialize database file if it doesn't exist"""
    if not os.path.exists(DB_FILE):
        save_database(DEFAULT_DB)


def load_database() -> Dict:
    """Load database from JSON file"""
    init_database()
    with db_lock:
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            save_database(DEFAULT_DB)
            return DEFAULT_DB.copy()


def save_database(data: Dict):
    """Save database to JSON file"""
    with db_lock:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# User operations
def hash_password(password: str) -> str:
    """Hash a password using Argon2"""
    if not isinstance(password, str):
        password = str(password)
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    if not isinstance(plain_password, str):
        plain_password = str(plain_password)
    return pwd_context.verify(plain_password, hashed_password)


def create_user(nick_name: str, password: str) -> Optional[Dict]:
    """Create a new user"""
    db = load_database()

    for user in db["users"]:
        if user["nick_name"].lower() == nick_name.lower():
            return None

    user = {
        "id": str(uuid.uuid4()),
        "nick_name": nick_name,
        "password": hash_password(password),
        "created_at": datetime.now().isoformat(),
    }

    db["users"].append(user)
    save_database(db)
    return user


def get_user_by_nickname(nick_name: str) -> Optional[Dict]:
    db = load_database()
    for user in db["users"]:
        if user["nick_name"].lower() == nick_name.lower():
            return user
    return None


def get_user_by_id(user_id: str) -> Optional[Dict]:
    db = load_database()
    for user in db["users"]:
        if user["id"] == user_id:
            return user
    return None


def authenticate_user(nick_name: str, password: str) -> Optional[Dict]:
    user = get_user_by_nickname(nick_name)
    if user and verify_password(password, user["password"]):
        return {k: v for k, v in user.items() if k != "password"}
    return None


# Private chat operations
def create_private_chat(user1_id: str, user2_id: str) -> Dict:
    db = load_database()
    for chat in db["private_chats"]:
        if set(chat["participants"]) == {user1_id, user2_id}:
            return chat

    chat = {
        "id": str(uuid.uuid4()),
        "participants": [user1_id, user2_id],
        "messages": [],
        "created_at": datetime.now().isoformat(),
    }
    db["private_chats"].append(chat)
    save_database(db)
    return chat


def get_private_chat(chat_id: str) -> Optional[Dict]:
    db = load_database()
    for chat in db["private_chats"]:
        if chat["id"] == chat_id:
            return chat
    return None


def get_user_private_chats(user_id: str) -> List[Dict]:
    db = load_database()
    return [chat for chat in db["private_chats"] if user_id in chat["participants"]]


def add_private_chat_message(
    chat_id: str,
    sender_id: str,
    content: str,
    attachment_filename: Optional[str] = None,
) -> Optional[Dict]:
    db = load_database()
    for chat in db["private_chats"]:
        if chat["id"] == chat_id:
            message = {
                "id": str(uuid.uuid4()),
                "sender_id": sender_id,
                "content": content,
                "attachment_filename": attachment_filename,
                "timestamp": datetime.now().isoformat(),
            }
            chat["messages"].append(message)
            save_database(db)
            return message
    return None


# Group chat operations
def create_group(name: str, creator_id: str) -> Dict:
    db = load_database()
    group = {
        "id": str(uuid.uuid4()),
        "name": name,
        "creator_id": creator_id,
        "members": [creator_id],
        "messages": [],
        "created_at": datetime.now().isoformat(),
    }
    db["groups"].append(group)
    save_database(db)
    return group


def get_group(group_id: str) -> Optional[Dict]:
    db = load_database()
    for group in db["groups"]:
        if group["id"] == group_id:
            return group
    return None


def get_user_groups(user_id: str) -> List[Dict]:
    db = load_database()
    return [group for group in db["groups"] if user_id in group["members"]]


def add_group_member(group_id: str, user_id: str) -> bool:
    db = load_database()
    for group in db["groups"]:
        if group["id"] == group_id and user_id not in group["members"]:
            group["members"].append(user_id)
            save_database(db)
            return True
    return False


def remove_group_member(group_id: str, user_id: str) -> bool:
    db = load_database()
    for group in db["groups"]:
        if (
            group["id"] == group_id
            and user_id in group["members"]
            and len(group["members"]) > 1
        ):
            group["members"].remove(user_id)
            save_database(db)
            return True
    return False


def add_group_message(
    group_id: str,
    sender_id: str,
    content: str,
    attachment_filename: Optional[str] = None,
) -> Optional[Dict]:
    db = load_database()
    for group in db["groups"]:
        if group["id"] == group_id and sender_id in group["members"]:
            message = {
                "id": str(uuid.uuid4()),
                "sender_id": sender_id,
                "content": content,
                "attachment_filename": attachment_filename,
                "timestamp": datetime.now().isoformat(),
            }
            group["messages"].append(message)
            save_database(db)
            return message
    return None


def delete_group(group_id: str) -> bool:
    db = load_database()
    for i, group in enumerate(db["groups"]):
        if group["id"] == group_id:
            db["groups"].pop(i)
            save_database(db)
            return True
    return False


# Contact submission operations
def add_contact_submission(
    name: str, email: str, message: str, attachment_filename: Optional[str] = None
) -> Dict:
    db = load_database()
    submission = {
        "id": str(uuid.uuid4()),
        "name": name,
        "email": email,
        "message": message,
        "attachment_filename": attachment_filename,
        "timestamp": datetime.now().isoformat(),
    }
    db["contact_submissions"].append(submission)
    save_database(db)
    return submission


def get_contact_submissions() -> List[Dict]:
    db = load_database()
    return db["contact_submissions"]


def get_all_users() -> List[Dict]:
    db = load_database()
    return [{k: v for k, v in user.items() if k != "password"} for user in db["users"]]


# Initialize the database on import
init_database()
