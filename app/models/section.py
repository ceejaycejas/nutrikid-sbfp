from app import db
from datetime import datetime

class Section(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    grade_level_id = db.Column(db.Integer, db.ForeignKey('grade_level.id'), nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey('school.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    students = db.relationship('Student', backref='section', lazy=True)
    grade_level = db.relationship('GradeLevel', backref=db.backref('sections_list', lazy=True))