#!/usr/bin/env python3
"""
Email Configuration Checker for NutriKid System

This script helps verify that your email configuration is correct
and can send emails to Gmail accounts.
"""

import os
from dotenv import load_dotenv

def check_email_config():
    """Check if email configuration is properly set up"""
    print("📧 NutriKid Email Configuration Checker")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    
    # Check required environment variables
    required_vars = ['MAIL_SERVER', 'MAIL_PORT', 'MAIL_USE_TLS', 'MAIL_USERNAME', 'MAIL_PASSWORD']
    missing_vars = []
    
    for var in required_vars:
        value = os.environ.get(var)
        if not value:
            missing_vars.append(var)
        elif var == 'MAIL_USERNAME':
            print(f"✅ {var}: {value}")
        elif var == 'MAIL_PASSWORD':
            print(f"✅ {var}: {'*' * len(value) if value else 'NOT SET'}")
        else:
            print(f"✅ {var}: {value}")
    
    if missing_vars:
        print(f"\n❌ Missing required environment variables: {', '.join(missing_vars)}")
        return False
    
    # Check if using placeholder values
    mail_username = os.environ.get('MAIL_USERNAME', '')
    mail_password = os.environ.get('MAIL_PASSWORD', '')
    
    if mail_username == 'your-real-gmail@gmail.com':
        print("\n❌ ERROR: You need to update MAIL_USERNAME with your actual Gmail address")
        print("   Edit the .env file and replace 'your-real-gmail@gmail.com' with your Gmail address")
        return False
        
    if mail_password == 'your-16-character-gmail-app-password':
        print("\n❌ ERROR: You need to update MAIL_PASSWORD with your Gmail App Password")
        print("   Edit the .env file and replace 'your-16-character-gmail-app-password' with your actual App Password")
        return False
        
    if len(mail_password) < 16:
        print("\n⚠️  WARNING: Gmail App Passwords are typically 16 characters long")
        print("   Make sure you're using an App Password, not your regular Gmail password")
        
    print("\n✅ Email configuration looks good!")
    print("\n📝 Next steps:")
    print("1. Restart your Flask server: Ctrl+C to stop, then 'python app.py' to start")
    print("2. Test by approving a password reset request")
    print("3. Check your Gmail inbox (and Spam folder) for the email")
    
    return True

if __name__ == "__main__":
    check_email_config()