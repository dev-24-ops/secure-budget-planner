import bcrypt
import jwt
import sqlite3
from datetime import datetime, timedelta
import secrets
import os
from cryptography.fernet import Fernet
from pathlib import Path

class AuthManager:
    def __init__(self, db_path="users.db"):
        self.db_path = db_path
        # Generate or load encryption key
        self.key_file = Path("encryption.key")
        if not self.key_file.exists():
            self.encryption_key = Fernet.generate_key()
            with open(self.key_file, "wb") as key_file:
                key_file.write(self.encryption_key)
        else:
            with open(self.key_file, "rb") as key_file:
                self.encryption_key = key_file.read()
        
        self.fernet = Fernet(self.encryption_key)
        self.jwt_secret = os.environ.get('JWT_SECRET', secrets.token_hex(32))
        self.init_db()

    def init_db(self):
        """Initialize the users database"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Create users table with security questions
        c.execute('''
            CREATE TABLE IF NOT EXISTS users
            (id INTEGER PRIMARY KEY,
             username TEXT UNIQUE NOT NULL,
             password_hash TEXT NOT NULL,
             email TEXT UNIQUE NOT NULL,
             security_question TEXT NOT NULL,
             security_answer_hash TEXT NOT NULL,
             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
             last_login TIMESTAMP,
             failed_attempts INTEGER DEFAULT 0,
             locked_until TIMESTAMP)
        ''')
        
        # Create session table
        c.execute('''
            CREATE TABLE IF NOT EXISTS sessions
            (id INTEGER PRIMARY KEY,
             user_id INTEGER,
             token TEXT NOT NULL,
             expires_at TIMESTAMP,
             FOREIGN KEY(user_id) REFERENCES users(id))
        ''')
        
        conn.commit()
        conn.close()

    def hash_password(self, password: str) -> bytes:
        """Hash a password using bcrypt"""
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

    def verify_password(self, password: str, password_hash: bytes) -> bool:
        """Verify a password against its hash"""
        return bcrypt.checkpw(password.encode(), password_hash)

    def create_user(self, username: str, password: str, email: str, 
                   security_question: str, security_answer: str) -> bool:
        """Create a new user with security question"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Hash password and security answer
            password_hash = self.hash_password(password)
            answer_hash = self.hash_password(security_answer.lower())
            
            c.execute("""
                INSERT INTO users 
                (username, password_hash, email, security_question, security_answer_hash)
                VALUES (?, ?, ?, ?, ?)
            """, (username, password_hash, email, security_question, answer_hash))
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False

    def login(self, username: str, password: str) -> tuple:
        """Login a user and return JWT token if successful"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        
        if not user:
            conn.close()
            return False, "Invalid username or password"
        
        # Check if account is locked
        if user[9] and datetime.now() < datetime.fromisoformat(user[9]):
            conn.close()
            return False, "Account is locked. Try again later."
        
        if not self.verify_password(password, user[2]):
            # Increment failed attempts
            failed_attempts = user[8] + 1
            locked_until = None
            
            if failed_attempts >= 5:
                # Lock account for 30 minutes after 5 failed attempts
                locked_until = datetime.now() + timedelta(minutes=30)
            
            c.execute("""
                UPDATE users 
                SET failed_attempts = ?, locked_until = ?
                WHERE id = ?
            """, (failed_attempts, locked_until, user[0]))
            
            conn.commit()
            conn.close()
            return False, "Invalid username or password"
        
        # Reset failed attempts on successful login
        c.execute("""
            UPDATE users 
            SET failed_attempts = 0, locked_until = NULL, last_login = ?
            WHERE id = ?
        """, (datetime.now(), user[0]))
        
        # Generate JWT token
        token = jwt.encode({
            'user_id': user[0],
            'username': user[1],
            'exp': datetime.utcnow() + timedelta(hours=24)
        }, self.jwt_secret, algorithm='HS256')
        
        # Store session
        c.execute("""
            INSERT INTO sessions (user_id, token, expires_at)
            VALUES (?, ?, ?)
        """, (user[0], token, datetime.utcnow() + timedelta(hours=24)))
        
        conn.commit()
        conn.close()
        
        return True, token

    def verify_token(self, token: str) -> tuple:
        """Verify a JWT token"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute("SELECT * FROM sessions WHERE token = ? AND expires_at > ?", 
                     (token, datetime.utcnow()))
            session = c.fetchone()
            
            if not session:
                conn.close()
                return False, None
                
            conn.close()
            return True, payload
        except jwt.ExpiredSignatureError:
            return False, "Token has expired"
        except jwt.InvalidTokenError:
            return False, "Invalid token"

    def reset_password(self, username: str, security_answer: str, new_password: str) -> bool:
        """Reset password using security question"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        
        if not user:
            conn.close()
            return False
        
        if not self.verify_password(security_answer.lower(), user[5]):
            conn.close()
            return False
        
        # Update password
        new_password_hash = self.hash_password(new_password)
        c.execute("UPDATE users SET password_hash = ? WHERE id = ?", 
                 (new_password_hash, user[0]))
        
        conn.commit()
        conn.close()
        return True

    def encrypt_data(self, data: str) -> bytes:
        """Encrypt sensitive data"""
        return self.fernet.encrypt(data.encode())

    def decrypt_data(self, encrypted_data: bytes) -> str:
        """Decrypt sensitive data"""
        return self.fernet.decrypt(encrypted_data).decode()

    def logout(self, token: str) -> bool:
        """Logout user by invalidating their session"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("DELETE FROM sessions WHERE token = ?", (token,))
        
        conn.commit()
        conn.close()
        return True
