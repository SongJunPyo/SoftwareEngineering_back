-- Migration script to add email verification fields to users table

-- Add email verification columns
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verification_token VARCHAR;
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verification_token_expires_at TIMESTAMPTZ;

-- Set default values for existing users
UPDATE users SET email_verified = FALSE WHERE email_verified IS NULL;
ALTER TABLE users ALTER COLUMN email_verified SET NOT NULL;

-- Fix role column type from integer to varchar
ALTER TABLE users ALTER COLUMN role TYPE VARCHAR USING 
    CASE 
        WHEN role = '3' OR role::text = '3' THEN 'member'
        WHEN role = '1' OR role::text = '1' THEN 'pending' 
        WHEN role = '2' OR role::text = '2' THEN 'admin'
        ELSE role::VARCHAR 
    END;

-- Set default role for any null values
UPDATE users SET role = 'member' WHERE role IS NULL OR role = '';

-- Verify the changes
SELECT column_name, data_type, is_nullable, column_default 
FROM information_schema.columns 
WHERE table_name = 'users' 
ORDER BY column_name;