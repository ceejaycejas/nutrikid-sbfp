from app import db
from datetime import datetime
from enum import Enum

class NotificationType(Enum):
    ACCOUNT_CREATED = "account_created"
    ACCOUNT_UPDATED = "account_updated"
    ACCOUNT_DELETED = "account_deleted"
    PASSWORD_CHANGED = "password_changed"
    PROFILE_UPDATED = "profile_updated"
    STUDENT_ADDED = "student_added"
    STUDENT_UPDATED = "student_updated"
    STUDENT_DELETED = "student_deleted"
    SECTION_CREATED = "section_created"
    SECTION_UPDATED = "section_updated"
    SECTION_DELETED = "section_deleted"
    GRADE_CREATED = "grade_created"
    GRADE_UPDATED = "grade_updated"
    GRADE_DELETED = "grade_deleted"
    SCHOOL_UPDATED = "school_updated"
    ADMIN_ASSIGNED = "admin_assigned"
    ADMIN_REMOVED = "admin_removed"
    SYSTEM_MAINTENANCE = "system_maintenance"
    SECURITY_ALERT = "security_alert"
    REPORT_GENERATED = "report_generated"

class NotificationPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)  # Using string instead of Enum for compatibility
    priority = db.Column(db.String(20), default='medium')
    
    # Status tracking
    is_read = db.Column(db.Boolean, default=False)
    is_email_sent = db.Column(db.Boolean, default=False)
    email_sent_at = db.Column(db.DateTime)
    
    # Metadata
    related_entity_type = db.Column(db.String(50))  # e.g., 'student', 'section', 'grade'
    related_entity_id = db.Column(db.Integer)
    action_url = db.Column(db.String(500))  # URL for action button
    action_text = db.Column(db.String(100))  # Text for action button
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)  # For temporary notifications
    
    # Legacy field for backward compatibility
    report_id = db.Column(db.Integer, nullable=True)  # Link to Student report if relevant
    
    # Relationships
    recipient = db.relationship('User', backref=db.backref('notifications', lazy=True, order_by='Notification.created_at.desc()'))
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.read_at = datetime.utcnow()
        db.session.commit()
    
    def to_dict(self):
        """Convert notification to dictionary for JSON responses"""
        return {
            'id': self.id,
            'title': self.title,
            'message': self.message,
            'type': self.notification_type,
            'priority': self.priority,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat(),
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'action_url': self.action_url,
            'action_text': self.action_text,
            'related_entity_type': self.related_entity_type,
            'related_entity_id': self.related_entity_id
        }
    
    @staticmethod
    def get_unread_count(user_id):
        """Get count of unread notifications for a user"""
        return Notification.query.filter_by(recipient_id=user_id, is_read=False).count()
    
    @staticmethod
    def get_recent_notifications(user_id, limit=10):
        """Get recent notifications for a user"""
        return Notification.query.filter_by(recipient_id=user_id)\
                                .order_by(Notification.created_at.desc())\
                                .limit(limit).all()
    
    def __repr__(self):
        return f'<Notification {self.id}: {self.title} for User {self.recipient_id}>' 