from app import db

class School(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(200))
    contact_number = db.Column(db.String(20))
    email = db.Column(db.String(120))
    logo = db.Column(db.String(256), nullable=True)  # Path to school logo image
    users = db.relationship('User', backref='school', lazy=True)
    students = db.relationship('Student', backref='school', lazy=True) 
    # Add missing relationships so related models have .school available
    sections = db.relationship('Section', backref='school', lazy=True)
    grade_levels = db.relationship('GradeLevel', backref='school', lazy=True)