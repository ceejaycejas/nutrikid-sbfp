from app import db
from datetime import datetime, timedelta
import secrets
import string

class PasswordResetRequest(db.Model):
    __tablename__ = 'password_reset_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected, completed, expired
    reason = db.Column(db.Text)  # User's reason for password reset
    admin_notes = db.Column(db.Text)  # Admin's notes
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    approved_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    # Who handled the request
    approved_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref='password_reset_requests')
    approved_by = db.relationship('User', foreign_keys=[approved_by_id])
    
    def __init__(self, user_id, reason=None):
        self.user_id = user_id
        self.reason = reason
        self.token = self.generate_token()
        self.expires_at = datetime.utcnow() + timedelta(hours=24)  # Expires in 24 hours
    
    @staticmethod
    def generate_token():
        """Generate a secure random token"""
        return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
    
    def is_expired(self):
        """Check if the request has expired"""
        return datetime.utcnow() > self.expires_at
    
    def can_be_approved(self):
        """Check if the request can be approved"""
        return self.status == 'pending' and not self.is_expired()
    
    def approve(self, approved_by_id, admin_notes=None):
        """Approve the password reset request"""
        if not self.can_be_approved():
            return False
        
        self.status = 'approved'
        self.approved_by_id = approved_by_id
        self.approved_at = datetime.utcnow()
        if admin_notes:
            self.admin_notes = admin_notes
        
        db.session.commit()
        return True
    
    def reject(self, approved_by_id, admin_notes=None):
        """Reject the password reset request"""
        if self.status != 'pending':
            return False
        
        self.status = 'rejected'
        self.approved_by_id = approved_by_id
        self.approved_at = datetime.utcnow()
        if admin_notes:
            self.admin_notes = admin_notes
        
        db.session.commit()
        return True
    
    def complete(self):
        """Mark the request as completed"""
        if self.status != 'approved':
            return False
        
        self.status = 'completed'
        self.completed_at = datetime.utcnow()
        db.session.commit()
        return True
    
    def get_status_badge_class(self):
        """Get Bootstrap badge class for status"""
        status_classes = {
            'pending': 'bg-warning',
            'approved': 'bg-success',
            'rejected': 'bg-danger',
            'completed': 'bg-info',
            'expired': 'bg-secondary'
        }
        if self.is_expired() and self.status == 'pending':
            return status_classes.get('expired', 'bg-secondary')
        return status_classes.get(self.status, 'bg-secondary')
    
    def get_display_status(self):
        """Get human-readable status"""
        if self.is_expired() and self.status == 'pending':
            return 'Expired'
        return self.status.title()