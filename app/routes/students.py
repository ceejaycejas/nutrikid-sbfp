from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models.student import Student
from app import db

bp = Blueprint('students', __name__, url_prefix='/students')

@bp.route('/add', methods=['GET', 'POST'])
def add_student():
    if request.method == 'POST':
        name = request.form.get('name')
        age = request.form.get('age')
        preferences = request.form.get('preferences')  # Ensure this is captured

        # Validate input
        if not name or not age:
            flash('Name and age are required.', 'danger')
            return render_template('students/add_student.html')

        try:
            # Add student to the database
            student = Student(name=name, age=age, preferences=preferences)
            db.session.add(student)
            db.session.commit()
            flash('Student added successfully!', 'success')
            return redirect(url_for('students.list_students'))
        except Exception as e:
            db.session.rollback()
            print(f"Error adding student: {e}")
            flash('An error occurred while adding the student.', 'danger')
            return render_template('students/add_student.html')

    return render_template('students/add_student.html')