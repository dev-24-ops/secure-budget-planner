import sqlite3
import json
from datetime import datetime
import os
import shutil
from auth_manager import AuthManager

class BudgetDatabase:
    def __init__(self, db_name="budget.db", user_id=None):
        self.db_name = db_name
        self.user_id = user_id
        self.auth_manager = AuthManager()
        self.backup_dir = "backups"
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)
        self.init_database()

    def init_database(self):
        """Initialize the database with required tables"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()

        # Create salary table with user_id
        c.execute('''
            CREATE TABLE IF NOT EXISTS salary
            (id INTEGER PRIMARY KEY,
             user_id INTEGER NOT NULL,
             amount_encrypted BLOB NOT NULL,
             updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
        ''')

        # Create transactions table with user_id
        c.execute('''
            CREATE TABLE IF NOT EXISTS transactions
            (id INTEGER PRIMARY KEY,
             user_id INTEGER NOT NULL,
             date DATE NOT NULL,
             amount_encrypted BLOB NOT NULL,
             category TEXT NOT NULL,
             description_encrypted BLOB,
             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
        ''')

        conn.commit()
        conn.close()

    def update_salary(self, amount):
        """Update the monthly salary"""
        if not self.user_id:
            raise ValueError("User not authenticated")
            
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        # Encrypt the salary amount
        encrypted_amount = self.auth_manager.encrypt_data(str(amount))
        c.execute("DELETE FROM salary WHERE user_id = ?", (self.user_id,))
        c.execute("INSERT INTO salary (user_id, amount_encrypted) VALUES (?, ?)", 
                 (self.user_id, encrypted_amount))
        conn.commit()
        conn.close()

    def get_salary(self):
        """Get the current monthly salary"""
        if not self.user_id:
            raise ValueError("User not authenticated")
            
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("SELECT amount_encrypted FROM salary WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1", 
                 (self.user_id,))
        result = c.fetchone()
        conn.close()
        
        if result:
            # Decrypt the salary amount
            decrypted_amount = self.auth_manager.decrypt_data(result[0])
            return float(decrypted_amount)
        return 0.0

    def add_transaction(self, date, amount, category, description=""):
        """Add a new transaction"""
        if not self.user_id:
            raise ValueError("User not authenticated")
            
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        
        # Encrypt sensitive data
        encrypted_amount = self.auth_manager.encrypt_data(str(amount))
        encrypted_description = self.auth_manager.encrypt_data(description)
        
        c.execute("""
            INSERT INTO transactions 
            (user_id, date, amount_encrypted, category, description_encrypted)
            VALUES (?, ?, ?, ?, ?)
        """, (self.user_id, date, encrypted_amount, category, encrypted_description))
        
        conn.commit()
        conn.close()

    def get_transactions(self, start_date=None, end_date=None):
        """Get transactions within a date range"""
        if not self.user_id:
            raise ValueError("User not authenticated")
            
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        query = "SELECT * FROM transactions WHERE user_id = ?"
        params = [self.user_id]
        
        if start_date and end_date:
            query += " AND date BETWEEN ? AND ?"
            params.extend([start_date, end_date])
        
        query += " ORDER BY date DESC"
        
        c.execute(query, params)
        encrypted_transactions = c.fetchall()
        conn.close()
        
        # Decrypt transactions
        transactions = []
        for trans in encrypted_transactions:
            decrypted_trans = dict(trans)
            decrypted_trans['amount'] = float(self.auth_manager.decrypt_data(trans['amount_encrypted']))
            decrypted_trans['description'] = self.auth_manager.decrypt_data(trans['description_encrypted'])
            transactions.append(decrypted_trans)
        
        return transactions

    def get_category_totals(self, start_date=None, end_date=None):
        """Get total spending by category within a date range"""
        if not self.user_id:
            raise ValueError("User not authenticated")
            
        transactions = self.get_transactions(start_date, end_date)
        totals = {}
        for trans in transactions:
            category = trans['category']
            amount = trans['amount']
            totals[category] = totals.get(category, 0) + amount
        return totals

    def export_database(self, backup_name=None):
        """Export the database to a backup file"""
        if not self.user_id:
            raise ValueError("User not authenticated")
            
        if backup_name is None:
            backup_name = f"budget_backup_{self.user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        
        backup_path = os.path.join(self.backup_dir, backup_name)
        
        # Create an encrypted backup
        data = {
            'salary': self.get_salary(),
            'transactions': self.get_transactions()
        }
        
        # Encrypt the entire backup
        encrypted_data = self.auth_manager.encrypt_data(json.dumps(data))
        
        # Save encrypted backup
        with open(backup_path, 'wb') as f:
            f.write(encrypted_data)
        
        return backup_path

    def import_database(self, backup_path):
        """Import a database from a backup file"""
        if not self.user_id:
            raise ValueError("User not authenticated")
            
        try:
            # Read and decrypt backup
            with open(backup_path, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = self.auth_manager.decrypt_data(encrypted_data)
            data = json.loads(decrypted_data)
            
            # Clear existing data for this user
            conn = sqlite3.connect(self.db_name)
            c = conn.cursor()
            c.execute("DELETE FROM salary WHERE user_id = ?", (self.user_id,))
            c.execute("DELETE FROM transactions WHERE user_id = ?", (self.user_id,))
            conn.commit()
            conn.close()
            
            # Import salary
            if data['salary']:
                self.update_salary(float(data['salary']))
            
            # Import transactions
            for trans in data['transactions']:
                self.add_transaction(
                    datetime.strptime(trans['date'], '%Y-%m-%d').date(),
                    float(trans['amount']),
                    trans['category'],
                    trans['description']
                )
                
            return True
        except Exception as e:
            print(f"Error importing backup: {str(e)}")
            return False

    def list_backups(self):
        """List all available database backups for the current user"""
        if not self.user_id:
            raise ValueError("User not authenticated")
            
        backups = []
        for file in os.listdir(self.backup_dir):
            if file.startswith(f"budget_backup_{self.user_id}_"):
                backup_path = os.path.join(self.backup_dir, file)
                backup_time = datetime.fromtimestamp(os.path.getmtime(backup_path))
                backups.append({
                    'filename': file,
                    'path': backup_path,
                    'created_at': backup_time
                })
        return sorted(backups, key=lambda x: x['created_at'], reverse=True)
