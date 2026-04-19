#!/usr/bin/env python3
"""
Update password hashes for KloutNetwork users.
Sets all passwords to 'password123' with proper bcrypt hashing.
"""

import psycopg2
import bcrypt
import sys

# Database connection parameters
DB_PARAMS = {
    'dbname': 'klout_network',
    'user': 'kaseymarcelle',
    'host': 'localhost',
    'port': 5432
}

def update_password_hashes():
    """Update password hashes for all users"""
    conn = None
    cur = None
    
    try:
        # Connect to database
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        print("✅ Connected to database")
        
        # Get all users
        cur.execute("SELECT id, username FROM users")
        users = cur.fetchall()
        
        # Hash password (use 'password123' for all users for testing)
        password = 'password123'
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        
        # Update password hashes for all users
        for user_id, username in users:
            cur.execute("""
                UPDATE users SET password_hash = %s WHERE id = %s
            """, (password_hash, user_id))
            print(f"✅ Updated password for user: {username} (ID: {user_id})")
        
        conn.commit()
        print(f"\n✅ Updated passwords for {len(users)} users")
        print("   All passwords set to: password123")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        if conn:
            conn.rollback()
        sys.exit(1)
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
        print("✅ Disconnected from database")

if __name__ == '__main__':
    update_password_hashes()