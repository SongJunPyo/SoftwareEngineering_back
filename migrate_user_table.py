#!/usr/bin/env python3
"""
Database migration script to add email verification fields to the users table.
Run this script to update the database schema.
"""

from backend.database.base import engine
from sqlalchemy import text

def migrate_user_table():
    """Add missing email verification columns to users table"""
    
    # SQL commands to add missing columns
    sql_commands = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verification_token VARCHAR;", 
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verification_token_expires_at TIMESTAMPTZ;",
        "UPDATE users SET email_verified = FALSE WHERE email_verified IS NULL;",
        "ALTER TABLE users ALTER COLUMN email_verified SET NOT NULL;",
    ]
    
    # Commands to fix role column type
    role_commands = [
        "ALTER TABLE users ALTER COLUMN role TYPE VARCHAR USING CASE WHEN role = 3 THEN 'member' ELSE role::VARCHAR END;",
        "UPDATE users SET role = 'member' WHERE role IN ('3', '');",
        "UPDATE users SET role = 'pending' WHERE role = '1';",
        "UPDATE users SET role = 'admin' WHERE role = '2';",
    ]
    
    print("Starting database migration...")
    
    try:
        with engine.connect() as connection:
            # Add email verification columns
            for sql in sql_commands:
                try:
                    result = connection.execute(text(sql))
                    print(f"✓ Executed: {sql}")
                except Exception as e:
                    print(f"✗ Error executing {sql}: {e}")
            
            # Fix role column
            for sql in role_commands:
                try:
                    result = connection.execute(text(sql))
                    print(f"✓ Executed: {sql}")
                except Exception as e:
                    print(f"✗ Error executing {sql}: {e}")
            
            # Commit all changes
            connection.commit()
            print("\n🎉 Database migration completed successfully!")
            
            # Verify the changes
            result = connection.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'users' ORDER BY column_name;"))
            columns = result.fetchall()
            print("\nCurrent users table columns:")
            for column in columns:
                print(f"  - {column[0]}: {column[1]}")
                
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise

if __name__ == "__main__":
    migrate_user_table()