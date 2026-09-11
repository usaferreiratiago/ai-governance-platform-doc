"""
User service for managing users in the database.
"""
import hashlib
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import text
from streamlit_app.db import engine, SessionLocal, User, AuditLog

def hash_password(password: str) -> str:
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return hash_password(password) == password_hash

def create_user(username: str, password: str, email: str = "", 
                full_name: str = "", role: str = "VIEWER") -> Optional[Dict]:
    """Create a new user in the database."""
    try:
        db = SessionLocal()
        
        # Check if user already exists
        existing = db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing:
            db.close()
            return None
        
        # Create new user
        user = User(
            id=f"user-{uuid.uuid4().hex[:8]}",
            username=username,
            email=email or f"{username}@company.com",
            password_hash=hash_password(password),
            full_name=full_name or username,
            role=role,
            is_active=True,
            created_at=datetime.now()
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        user_dict = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None
        }
        
        db.close()
        return user_dict
    except Exception as e:
        print(f"Error creating user: {e}")
        return None

def get_all_users() -> List[Dict]:
    """Get all users from the database."""
    try:
        db = SessionLocal()
        users = db.query(User).all()
        db.close()
        
        return [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "full_name": u.full_name,
                "role": u.role,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None
            }
            for u in users
        ]
    except Exception as e:
        print(f"Error getting users: {e}")
        return []

def get_user_by_username(username: str) -> Optional[Dict]:
    """Get a user by username."""
    try:
        db = SessionLocal()
        user = db.query(User).filter(User.username == username).first()
        db.close()
        
        if user:
            return {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat() if user.created_at else None
            }
        return None
    except Exception as e:
        print(f"Error getting user: {e}")
        return None

def update_user(username: str, **kwargs) -> bool:
    """Update a user's information."""
    try:
        db = SessionLocal()
        user = db.query(User).filter(User.username == username).first()
        
        if not user:
            db.close()
            return False
        
        # Update fields
        for key, value in kwargs.items():
            if hasattr(user, key) and key not in ['id', 'username', 'created_at']:
                setattr(user, key, value)
        
        user.updated_at = datetime.now()
        db.commit()
        db.close()
        return True
    except Exception as e:
        print(f"Error updating user: {e}")
        return False

def toggle_user_active(username: str) -> bool:
    """Toggle a user's active status."""
    try:
        db = SessionLocal()
        user = db.query(User).filter(User.username == username).first()
        
        if not user:
            db.close()
            return False
        
        user.is_active = not user.is_active
        user.updated_at = datetime.now()
        db.commit()
        db.close()
        return True
    except Exception as e:
        print(f"Error toggling user: {e}")
        return False

def delete_user(username: str) -> bool:
    """Delete a user from the database."""
    try:
        db = SessionLocal()
        user = db.query(User).filter(User.username == username).first()
        
        if not user:
            db.close()
            return False
        
        # Don't allow deleting the last admin
        admin_count = db.query(User).filter(User.role == 'ADMIN', User.is_active == True).count()
        if user.role == 'ADMIN' and admin_count == 1:
            db.close()
            return False
        
        db.delete(user)
        db.commit()
        db.close()
        return True
    except Exception as e:
        print(f"Error deleting user: {e}")
        return False

def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """Authenticate a user."""
    try:
        db = SessionLocal()
        user = db.query(User).filter(User.username == username).first()
        db.close()
        
        if user and verify_password(password, user.password_hash) and user.is_active:
            return {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "is_active": user.is_active
            }
        return None
    except Exception as e:
        print(f"Error authenticating user: {e}")
        return None

def get_user_statistics() -> Dict[str, Any]:
    """Get user statistics."""
    try:
        db = SessionLocal()
        total = db.query(User).count()
        active = db.query(User).filter(User.is_active == True).count()
        admin = db.query(User).filter(User.role == 'ADMIN').count()
        db.close()
        
        return {
            "total": total,
            "active": active,
            "inactive": total - active,
            "admin": admin
        }
    except Exception as e:
        print(f"Error getting user statistics: {e}")
        return {"total": 0, "active": 0, "inactive": 0, "admin": 0}
