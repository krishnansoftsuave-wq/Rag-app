import os
import sqlite3
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from app.core.config import DATA_DIR
from app.core.security import hash_password, verify_password

DB_PATH = os.path.join(DATA_DIR, "users.db")


def init_db():
    """Initialize SQLite database schema for Users and Document Ownership."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create Users Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    
    # Create Document Ownership Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_documents (
            doc_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            upload_time TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()


# Auto-initialize database schema on module load
init_db()


class UserService:
    @staticmethod
    def register_user(username: str, email: str, password: str) -> Dict[str, Any]:
        """Create a new user account."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if username or email exists
        cursor.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
        if cursor.fetchone():
            conn.close()
            raise ValueError("Username or email already registered.")
        
        user_id = f"usr_{uuid.uuid4().hex[:10]}"
        hashed_pwd = hash_password(password)
        created_at = datetime.utcnow().isoformat()
        
        cursor.execute(
            "INSERT INTO users (id, username, email, hashed_password, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, username, email, hashed_pwd, created_at)
        )
        conn.commit()
        conn.close()
        
        return {
            "id": user_id,
            "username": username,
            "email": email,
            "created_at": created_at
        }

    @staticmethod
    def authenticate_user(username_or_email: str, password: str) -> Optional[Dict[str, Any]]:
        """Verify user credentials and return user object if valid."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT id, username, email, hashed_password, created_at FROM users WHERE username = ? OR email = ?",
            (username_or_email, username_or_email)
        )
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        user_id, username, email, hashed_pwd, created_at = row
        if not verify_password(password, hashed_pwd):
            return None
        
        return {
            "id": user_id,
            "username": username,
            "email": email,
            "created_at": created_at
        }

    @staticmethod
    def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
        """Find user by user_id."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, email, created_at FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return {"id": row[0], "username": row[1], "email": row[2], "created_at": row[3]}

    @staticmethod
    def associate_document(doc_id: str, user_id: str, filename: str):
        """Record document ownership for user isolation."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        upload_time = datetime.utcnow().isoformat()
        cursor.execute(
            "INSERT OR REPLACE INTO user_documents (doc_id, user_id, filename, upload_time) VALUES (?, ?, ?, ?)",
            (doc_id, user_id, filename, upload_time)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_user_doc_ids(user_id: str) -> List[str]:
        """Get list of document IDs owned by a user."""
        if user_id == "default_user":
            # Guest user can access un-owned or default documents
            return []
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT doc_id FROM user_documents WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [r[0] for r in rows]
