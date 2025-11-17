#!/usr/bin/env python3
"""
Script to reset super admin password
Usage: python reset_super_admin_password.py
"""
from app import create_app, db
from app.models.user import User

def reset_password():
    app = create_app()
    
    with app.app_context():
        email = 'ceejay.cejas@dssc.edu.ph'
        
        # Find the user
        user = User.query.filter_by(email=email).first()
        
        if not user:
            print(f"❌ User with email '{email}' not found in database.")
            print("\nAvailable super admin accounts:")
            super_admins = User.query.filter_by(role='super_admin').all()
            if super_admins:
                for sa in super_admins:
                    print(f"  - {sa.email} (Name: {sa.name})")
            else:
                print("  No super admin accounts found.")
            return False
        
        if user.role != 'super_admin':
            print(f"⚠️  User '{email}' exists but is not a super admin.")
            print(f"   Current role: {user.role}")
            return False
        
        # Set new password
        new_password = input(f"\nEnter new password for {user.name} ({email}): ")
        if not new_password:
            print("❌ Password cannot be empty.")
            return False
        
        confirm = input("Confirm password: ")
        if new_password != confirm:
            print("❌ Passwords do not match.")
            return False
        
        # Update password
        try:
            user.set_password(new_password)
            db.session.commit()
            print(f"\n✅ Password reset successfully for {user.name} ({email})")
            print(f"   New password: {new_password}")
            print("\n⚠️  Please change this password after logging in for security.")
            return True
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error resetting password: {e}")
            return False

if __name__ == '__main__':
    print("=" * 60)
    print("🔐 Super Admin Password Reset Tool")
    print("=" * 60)
    reset_password()

