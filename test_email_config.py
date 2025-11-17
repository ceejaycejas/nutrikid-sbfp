#!/usr/bin/env python3
"""Test email configuration"""
from dotenv import load_dotenv
import os

load_dotenv()

print("=" * 50)
print("📧 Email Configuration Status")
print("=" * 50)

username = os.getenv('MAIL_USERNAME', 'NOT SET')
password = os.getenv('MAIL_PASSWORD', 'NOT SET')
server = os.getenv('MAIL_SERVER', 'NOT SET')
port = os.getenv('MAIL_PORT', 'NOT SET')
use_tls = os.getenv('MAIL_USE_TLS', 'NOT SET')

print(f"✅ MAIL_USERNAME: {username}")
print(f"✅ MAIL_PASSWORD: {'*' * len(password) if password != 'NOT SET' else 'NOT SET'}")
print(f"✅ MAIL_SERVER: {server}")
print(f"✅ MAIL_PORT: {port}")
print(f"✅ MAIL_USE_TLS: {use_tls}")

if all([username != 'NOT SET', password != 'NOT SET', server != 'NOT SET']):
    print("\n✨ Email configuration is complete!")
    print("   Restart your Flask application to start sending emails.")
else:
    print("\n⚠️  Some email configuration is missing.")
    print("   Please check your .env file.")

