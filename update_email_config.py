#!/usr/bin/env python3
"""
Helper script to update email configuration in .env file
"""
import os
import re

def update_env_file():
    """Update or create .env file with email configuration"""
    env_file = '.env'
    
    # Email configuration
    email_config = {
        'MAIL_SERVER': 'smtp.gmail.com',
        'MAIL_PORT': '587',
        'MAIL_USE_TLS': 'true',
        'MAIL_USERNAME': 'cejasceejay2004@gmail.com',
        'MAIL_PASSWORD': 'qeeg qhle hvub nsay'  # App Password (spaces will be removed)
    }
    
    # Read existing .env if it exists
    env_content = {}
    if os.path.exists(env_file):
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_content[key.strip()] = value.strip()
    
    # Update with email configuration
    env_content.update(email_config)
    
    # Remove spaces from App Password
    if 'MAIL_PASSWORD' in env_content:
        env_content['MAIL_PASSWORD'] = env_content['MAIL_PASSWORD'].replace(' ', '')
    
    # Ensure other required variables exist
    if 'MYSQL_USER' not in env_content:
        env_content['MYSQL_USER'] = 'root'
    if 'MYSQL_PASSWORD' not in env_content:
        env_content['MYSQL_PASSWORD'] = 'root'
    if 'MYSQL_HOST' not in env_content:
        env_content['MYSQL_HOST'] = '127.0.0.1'
    if 'MYSQL_PORT' not in env_content:
        env_content['MYSQL_PORT'] = '3306'
    if 'MYSQL_DB' not in env_content:
        env_content['MYSQL_DB'] = 'capstone'
    if 'SECRET_KEY' not in env_content:
        env_content['SECRET_KEY'] = 'your-secret-key-change-in-production'
    
    # Write .env file
    with open(env_file, 'w', encoding='utf-8') as f:
        f.write("# Database Configuration\n")
        f.write(f"MYSQL_USER={env_content['MYSQL_USER']}\n")
        f.write(f"MYSQL_PASSWORD={env_content['MYSQL_PASSWORD']}\n")
        f.write(f"MYSQL_HOST={env_content['MYSQL_HOST']}\n")
        f.write(f"MYSQL_PORT={env_content['MYSQL_PORT']}\n")
        f.write(f"MYSQL_DB={env_content['MYSQL_DB']}\n")
        f.write("\n")
        f.write("# Secret Key\n")
        f.write(f"SECRET_KEY={env_content['SECRET_KEY']}\n")
        f.write("\n")
        f.write("# Email Configuration (Gmail)\n")
        f.write(f"MAIL_SERVER={env_content['MAIL_SERVER']}\n")
        f.write(f"MAIL_PORT={env_content['MAIL_PORT']}\n")
        f.write(f"MAIL_USE_TLS={env_content['MAIL_USE_TLS']}\n")
        f.write(f"MAIL_USERNAME={env_content['MAIL_USERNAME']}\n")
        f.write("# Gmail App Password (spaces removed automatically)\n")
        f.write(f"MAIL_PASSWORD={env_content['MAIL_PASSWORD']}\n")
    
    print("✅ .env file updated successfully!")
    print(f"\n📧 Email Configuration:")
    print(f"   Email: {env_content['MAIL_USERNAME']}")
    print(f"   Server: {env_content['MAIL_SERVER']}")
    print(f"   Port: {env_content['MAIL_PORT']}")
    print(f"   TLS: {env_content['MAIL_USE_TLS']}")
    print(f"   Password: {'*' * len(env_content['MAIL_PASSWORD'])} (App Password configured)")
    print("\n✨ Your email notifications are now configured!")
    print("   Restart your Flask application to apply the changes.")

if __name__ == '__main__':
    try:
        update_env_file()
    except Exception as e:
        print(f"❌ Error updating .env file: {str(e)}")
        print("\nPlease manually create/update the .env file with the following content:")
        print("\n" + "="*50)
        print("MAIL_SERVER=smtp.gmail.com")
        print("MAIL_PORT=587")
        print("MAIL_USE_TLS=true")
        print("MAIL_USERNAME=cejasceejay2004@gmail.com")
        print("MAIL_PASSWORD=qeegqhlehvubnsay")
        print("="*50)

