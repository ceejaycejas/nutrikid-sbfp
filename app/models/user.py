from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from sqlalchemy.orm import relationship

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    name = db.Column(db.String(64))
    role = db.Column(db.String(20))  # 'super_admin', 'admin', 'student'
    school_id = db.Column(db.Integer, db.ForeignKey('school.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    student_profile = db.relationship('Student', backref='user', uselist=False, foreign_keys='Student.user_id')
    
    # Fields for login security
    login_attempts = db.Column(db.Integer, default=0)
    last_login_attempt = db.Column(db.DateTime)
    is_locked = db.Column(db.Boolean, default=False)
    lock_until = db.Column(db.DateTime)
    profile_image = db.Column(db.String(256), nullable=True)  # Path to profile image
    cover_image = db.Column(db.String(256), nullable=True)  # Path to cover image

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        # Reset login attempts when password is changed
        self.login_attempts = 0
        self.is_locked = False
        self.lock_until = None

    def check_password(self, password):
        # Check if account is locked
        if self.is_locked and self.lock_until and datetime.utcnow() < self.lock_until:
            return False
            
        # Check password
        is_correct = check_password_hash(self.password_hash, password)
        
        # Update login attempts
        if is_correct:
            self.login_attempts = 0
            self.last_login_attempt = datetime.utcnow()
            self.is_locked = False
            self.lock_until = None
        else:
            self.login_attempts += 1
            self.last_login_attempt = datetime.utcnow()
            
            # Lock account after 3 failed attempts
            if self.login_attempts >= 3:
                self.is_locked = True
                self.lock_until = datetime.utcnow() + timedelta(minutes=15)
        
        db.session.commit()
        return is_correct

    def has_role(self, role):
        return self.role == role
        
    def is_account_locked(self):
        if not self.is_locked:
            return False
        if not self.lock_until:
            return False
        return datetime.utcnow() < self.lock_until
        
    def get_lock_time_remaining(self):
        if not self.is_locked or not self.lock_until:
            return 0
        remaining = self.lock_until - datetime.utcnow()
        return max(0, int(remaining.total_seconds() / 60))

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(256), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user = relationship('User', backref='activity_logs')

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id)) 