#!/usr/bin/env python3
"""
Direct password reset script for super admin
Usage: Edit the NEW_PASSWORD variable below and run this script
"""
from app import create_app, db
from app.models.user import User

# ============================================
# CONFIGURATION - EDIT THIS:
# ============================================
EMAIL = 'ceejay.cejas@dssc.edu.ph'
NEW_PASSWORD = 'Admin@123'  # Default password - CHANGE THIS after logging in
# ============================================

app = create_app()

with app.app_context():
    print("=" * 60)
    print("🔐 Super Admin Password Reset")
    print("=" * 60)
    
    # Find the user
    user = User.query.filter_by(email=EMAIL).first()
    
    if not user:
        print(f"❌ User with email '{EMAIL}' not found.")
        print("\nAvailable super admin accounts:")
        super_admins = User.query.filter_by(role='super_admin').all()
        for sa in super_admins:
            print(f"  - {sa.email} (Name: {sa.name})")
        exit(1)
    
    if user.role != 'super_admin':
        print(f"⚠️  User '{EMAIL}' is not a super admin (role: {user.role})")
        exit(1)
    
    # Reset password
    try:
        print(f"\n📧 Resetting password for: {user.name} ({user.email})")
        user.set_password(NEW_PASSWORD)
        db.session.commit()
        
        print(f"\n✅ Password reset successfully!")
        print(f"   Email: {user.email}")
        print(f"   New Password: {NEW_PASSWORD}")
        print(f"\n⚠️  IMPORTANT: Change this password after logging in for security.")
        print(f"\n🔑 You can now login with:")
        print(f"   Email: {EMAIL}")
        print(f"   Password: {NEW_PASSWORD}")
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error resetting password: {e}")
        exit(1)

