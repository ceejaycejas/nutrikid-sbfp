from app import db
from datetime import datetime
from typing import Optional

class UserActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    activity_type = db.Column(db.String(50), nullable=False)  # e.g., 'login', 'update_profile', 'view_student'
    description = db.Column(db.String(255), nullable=False)
    ip_address = db.Column(db.String(45))  # IPv6 addresses can be up to 45 characters
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with User model
    user = db.relationship('User', backref=db.backref('activities', lazy=True))
    
    def __init__(self, user_id: int, activity_type: str, description: str, ip_address: Optional[str] = None):
        self.user_id = user_id
        self.activity_type = activity_type
        self.description = description
        self.ip_address = ip_address 