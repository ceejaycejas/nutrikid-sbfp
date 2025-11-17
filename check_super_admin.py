#!/usr/bin/env python3
"""
Script to check and reset super admin password
"""
from app import create_app, db
from app.models.user import User

app = create_app()

with app.app_context():
    email = 'ceejay.cejas@dssc.edu.ph'
    
    print("=" * 60)
    print("🔍 Checking Super Admin Account")
    print("=" * 60)
    
    # Find the user
    user = User.query.filter_by(email=email).first()
    
    if not user:
        print(f"❌ User with email '{email}' not found in database.")
        print("\n📋 Available super admin accounts:")
        super_admins = User.query.filter_by(role='super_admin').all()
        if super_admins:
            for sa in super_admins:
                print(f"  - Email: {sa.email}")
                print(f"    Name: {sa.name}")
                print(f"    ID: {sa.id}")
                print()
        else:
            print("  No super admin accounts found.")
        print("\n💡 To create a new super admin account, use the application's user creation feature.")
    else:
        print(f"✅ User found!")
        print(f"   Email: {user.email}")
        print(f"   Name: {user.name}")
        print(f"   Role: {user.role}")
        print(f"   ID: {user.id}")
        
        if user.role != 'super_admin':
            print(f"\n⚠️  Warning: This user is not a super admin (current role: {user.role})")
        else:
            print("\n" + "=" * 60)
            print("🔐 Password Reset")
            print("=" * 60)
            print("\nTo reset the password, run:")
            print("  python reset_password_direct.py")
            print("\nOr use the password reset feature in the application.")

