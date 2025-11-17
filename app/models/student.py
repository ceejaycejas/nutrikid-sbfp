from app import db
from datetime import datetime
from sqlalchemy import event

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True)
    section_id = db.Column(db.Integer, db.ForeignKey('section.id'))
    name = db.Column(db.String(64), nullable=False)
    birth_date = db.Column(db.Date)
    gender = db.Column(db.String(10))
    height = db.Column(db.Float)  # in centimeters
    weight = db.Column(db.Float)  # in kilograms
    bmi = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    school_id = db.Column(db.Integer, db.ForeignKey('school.id'))
    allergies = db.relationship('Allergy', backref='student', lazy=True)
    preferences = db.Column(db.String(256))  # Column for preferences/allergy info
    registered_by = db.Column(db.Integer, db.ForeignKey('user.id'))  # Admin who registered the student
    is_beneficiary = db.Column(db.Boolean, default=False)  # Explicitly mark as beneficiary
    _skip_beneficiary_update = False  # Flag to skip automatic beneficiary status update (used for manual overrides)

    @property
    def age(self):
        """Calculate age from birth date with error handling"""
        try:
            if self.birth_date:
                today = datetime.now().date()
                return today.year - self.birth_date.year - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
        except (AttributeError, TypeError, ValueError) as e:
            print(f"Error calculating age for student {self.id}: {e}")
        return None

    def calculate_bmi(self):
        """Calculate BMI with improved validation and error handling"""
        try:
            if self.height and self.weight and self.height > 0 and self.weight > 0:
                # Validate reasonable ranges
                if not (50 <= self.height <= 250):  # 50cm to 250cm
                    print(f"Warning: Unusual height {self.height}cm for student {self.id}")
                if not (5 <= self.weight <= 200):  # 5kg to 200kg
                    print(f"Warning: Unusual weight {self.weight}kg for student {self.id}")
                
                height_m = self.height / 100  # convert cm to m
                calculated_bmi = self.weight / (height_m * height_m)
                
                # Validate BMI range
                if 5 <= calculated_bmi <= 50:  # Reasonable BMI range
                    self.bmi = round(calculated_bmi, 2)
                else:
                    print(f"Warning: Calculated BMI {calculated_bmi} is outside normal range for student {self.id}")
                    self.bmi = None
            else:
                self.bmi = None
        except (TypeError, ValueError, ZeroDivisionError) as e:
            print(f"Error calculating BMI for student {self.id}: {e}")
            self.bmi = None
        
        return self.bmi

    @property
    def bmi_category(self):
        """Get BMI category with proper classification"""
        if not self.bmi:
            return 'No Data'
        
        try:
            if self.bmi < 16:
                return 'Severely Underweight'
            elif self.bmi < 18.5:
                return 'Underweight'
            elif self.bmi < 25:
                return 'Normal Weight'
            elif self.bmi < 30:
                return 'Overweight'
            else:
                return 'Obese'
        except (TypeError, ValueError):
            return 'Invalid Data'

    @property
    def is_at_risk(self):
        """Determine if student is at nutritional risk"""
        try:
            return self.bmi is not None and (self.bmi < 16 or self.bmi >= 30)
        except (TypeError, ValueError):
            return False

    @property
    def health_status(self):
        """Get overall health status"""
        if not self.bmi:
            return {'status': 'unknown', 'color': 'secondary', 'message': 'No health data available'}
        
        try:
            if self.bmi < 16:
                return {'status': 'critical', 'color': 'danger', 'message': 'Severely underweight'}
            elif self.bmi < 18.5:
                return {'status': 'warning', 'color': 'warning', 'message': 'Underweight'}
            elif self.bmi < 25:
                return {'status': 'healthy', 'color': 'success', 'message': 'Normal'}
            elif self.bmi < 30:
                return {'status': 'warning', 'color': 'warning', 'message': 'Overweight'}
            else:
                return {'status': 'critical', 'color': 'danger', 'message': 'Obese'}
        except (TypeError, ValueError):
            return {'status': 'error', 'color': 'secondary', 'message': 'Invalid health data'}

    def update_beneficiary_status(self):
        """Update beneficiary status based on current BMI
        
        NOTE: This will only auto-update if _skip_beneficiary_update is False.
        Set _skip_beneficiary_update = True before saving to prevent auto-update (for manual overrides).
        
        IMPORTANT: If is_beneficiary is already True, we preserve it (manual selection takes precedence).
        """
        try:
            # Skip automatic update if manual override is set
            if getattr(self, '_skip_beneficiary_update', False):
                return
            
            # If is_beneficiary is already True, preserve it (manual selection)
            # Only auto-update if it's False or None
            if self.is_beneficiary is True:
                return
            
            if self.bmi is not None:
                # Mark as beneficiary if BMI indicates nutritional risk
                self.is_beneficiary = (self.bmi < 18.5 or self.bmi >= 25)
            else:
                # Keep existing status if no BMI data
                pass
        except (TypeError, ValueError) as e:
            print(f"Error updating beneficiary status for student {self.id}: {e}")

    def __repr__(self):
        return f'<Student {self.name}>'

# Event listeners for automatic updates
@event.listens_for(Student, 'before_insert')
@event.listens_for(Student, 'before_update')
def calculate_bmi_and_status(mapper, connection, target):
    """Automatically calculate BMI and update beneficiary status before saving"""
    try:
        target.calculate_bmi()
        target.update_beneficiary_status()
    except Exception as e:
        print(f"Error in BMI calculation event listener: {e}")

class Allergy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    allergen = db.Column(db.String(64)) 