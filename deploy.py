#!/usr/bin/env python3
"""
NutriKid Deployment Script
This script sets up the complete NutriKid application with all necessary components
"""

import os
import sys
import subprocess
import mysql.connector
from mysql.connector import Error
from datetime import datetime

def print_step(step_name):
    """Print a formatted step header"""
    print("\n" + "="*60)
    print(f"STEP: {step_name}")
    print("="*60)

def print_success(message):
    """Print success message"""
    print(f"✅ {message}")

def print_error(message):
    """Print error message"""
    print(f"❌ {message}")

def print_info(message):
    """Print info message"""
    print(f"ℹ️  {message}")

def check_python_version():
    """Check if Python version is compatible"""
    print_step("Checking Python Version")
    
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print_error(f"Python 3.8+ required. Current version: {version.major}.{version.minor}")
        return False
    
    print_success(f"Python version {version.major}.{version.minor}.{version.micro} is compatible")
    return True

def check_mysql_connection():
    """Check MySQL connection and create database if needed"""
    print_step("Checking MySQL Connection")
    
    try:
        # Try to connect to MySQL
        connection = mysql.connector.connect(
            host="127.0.0.1",
            port=3306,
            user="root",
            password="root"
        )
        
        if connection.is_connected():
            print_success("Connected to MySQL server")
            
            cursor = connection.cursor()
            
            # Create database if it doesn't exist
            cursor.execute("CREATE DATABASE IF NOT EXISTS capstone")
            cursor.execute("USE capstone")
            print_success("Database 'capstone' is ready")
            
            # Check if tables exist
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            print_info(f"Found {len(tables)} existing tables")
            
            cursor.close()
            connection.close()
            return True
            
    except Error as e:
        print_error(f"MySQL connection failed: {e}")
        print_info("Please ensure MySQL is running and credentials are correct")
        return False

def install_dependencies():
    """Install Python dependencies"""
    print_step("Installing Dependencies")
    
    try:
        # Check if virtual environment exists
        venv_path = os.path.join(os.getcwd(), '.venv')
        if not os.path.exists(venv_path):
            print_info("Creating virtual environment...")
            subprocess.run([sys.executable, '-m', 'venv', '.venv'], check=True)
            print_success("Virtual environment created")
        
        # Activate virtual environment and install dependencies
        if os.name == 'nt':  # Windows
            pip_path = os.path.join(venv_path, 'Scripts', 'pip.exe')
            python_path = os.path.join(venv_path, 'Scripts', 'python.exe')
        else:  # Unix/Linux
            pip_path = os.path.join(venv_path, 'bin', 'pip')
            python_path = os.path.join(venv_path, 'bin', 'python')
        
        # Install requirements
        if os.path.exists('requirements.txt'):
            print_info("Installing from requirements.txt...")
            subprocess.run([pip_path, 'install', '-r', 'requirements.txt'], check=True)
        else:
            print_info("Installing core dependencies...")
            dependencies = [
                'Flask==3.1.1',
                'Flask-SQLAlchemy==3.1.1',
                'Flask-Login==0.6.3',
                'Flask-Migrate==4.1.0',
                'Flask-Mail==0.10.0',
                'PyMySQL==1.1.1',
                'python-dotenv==1.1.1',
                'pandas==2.3.1',
                'xlsxwriter==3.2.5',
                'Werkzeug==3.1.3'
            ]
            
            for dep in dependencies:
                subprocess.run([pip_path, 'install', dep], check=True)
        
        print_success("Dependencies installed successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to install dependencies: {e}")
        return False
    except Exception as e:
        print_error(f"Unexpected error during dependency installation: {e}")
        return False

def setup_database():
    """Set up database tables and migrations"""
    print_step("Setting Up Database")
    
    try:
        # Import Flask app to create tables
        sys.path.insert(0, os.getcwd())
        from app import create_app, db
        
        app = create_app()
        with app.app_context():
            # Create all tables
            db.create_all()
            print_success("Database tables created")
            
            # Check if we need to run migrations
            try:
                from flask_migrate import upgrade
                upgrade()
                print_success("Database migrations applied")
            except Exception as e:
                print_info(f"Migration info: {e}")
        
        return True
        
    except Exception as e:
        print_error(f"Database setup failed: {e}")
        return False

def create_sample_data():
    """Create sample data for testing"""
    print_step("Creating Sample Data")
    
    try:
        sys.path.insert(0, os.getcwd())
        from app import create_app, db
        from app.models.user import User
        from app.models.school import School
        from app.models.section import Section
        from app.models.grade_level import GradeLevel
        from app.models.student import Student

        from werkzeug.security import generate_password_hash
        from datetime import date, timedelta
        
        app = create_app()
        with app.app_context():
            # Check if sample data already exists
            if User.query.filter_by(username='superadmin').first():
                print_info("Sample data already exists")
                return True
            
            # Create super admin
            super_admin = User(
                username='superadmin',
                email='superadmin@nutrikid.com',
                password_hash=generate_password_hash('admin123'),
                role='super_admin',
                is_active=True
            )
            db.session.add(super_admin)
            
            # Create sample school
            school = School(
                name='Sample Elementary School',
                address='123 Education Street',
                contact_number='555-0123',
                email='info@sampleschool.edu',
                principal_name='Dr. Jane Smith'
            )
            db.session.add(school)
            db.session.flush()  # Get the school ID
            
            # Create admin for the school
            admin = User(
                username='admin',
                email='admin@sampleschool.edu',
                password_hash=generate_password_hash('admin123'),
                role='admin',
                school_id=school.id,
                is_active=True
            )
            db.session.add(admin)
            
            # Create grade levels
            grade_levels = []
            for i in range(1, 7):  # Grades 1-6
                grade = GradeLevel(name=f'Grade {i}')
                db.session.add(grade)
                grade_levels.append(grade)
            
            db.session.flush()
            
            # Create sections
            sections = []
            section_names = ['Section A', 'Section B', 'Section C']
            for grade in grade_levels[:3]:  # Only for first 3 grades
                for section_name in section_names:
                    section = Section(
                        name=f'{grade.name} - {section_name}',
                        school_id=school.id,
                        grade_level_id=grade.id
                    )
                    db.session.add(section)
                    sections.append(section)
            
            db.session.flush()
            
            # Create sample students
            student_names = [
                'Alice Johnson', 'Bob Smith', 'Carol Davis', 'David Wilson',
                'Emma Brown', 'Frank Miller', 'Grace Lee', 'Henry Taylor',
                'Ivy Chen', 'Jack Anderson', 'Kate Martinez', 'Liam Garcia'
            ]
            
            students = []
            for i, name in enumerate(student_names):
                student = Student(
                    name=name,
                    birth_date=date(2015, 1, 1) + timedelta(days=i*30),
                    gender='Male' if i % 2 == 0 else 'Female',
                    height=120 + (i * 2),  # Heights from 120-142 cm
                    weight=25 + (i * 1.5),  # Weights from 25-41.5 kg
                    school_id=school.id,
                    section_id=sections[i % len(sections)].id if sections else None,
                    registered_by=admin.id
                )
                db.session.add(student)
                students.append(student)
            
            db.session.flush()
            

            
            # Commit all changes
            db.session.commit()
            
            print_success("Sample data created successfully")
            print_info("Login credentials:")
            print_info("  Super Admin - Username: superadmin, Password: admin123")
            print_info("  School Admin - Username: admin, Password: admin123")
            
            return True
            
    except Exception as e:
        print_error(f"Failed to create sample data: {e}")
        return False

def verify_installation():
    """Verify that the installation is working"""
    print_step("Verifying Installation")
    
    try:
        sys.path.insert(0, os.getcwd())
        from app import create_app
        
        app = create_app()
        
        # Test app creation
        print_success("Flask app created successfully")
        
        # Test database connection
        with app.app_context():
            from app.models.user import User
            user_count = User.query.count()
            print_success(f"Database connection verified ({user_count} users found)")
        
        # Test routes
        with app.test_client() as client:
            response = client.get('/')
            if response.status_code in [200, 302]:  # 302 for redirect to login
                print_success("Routes are working")
            else:
                print_error(f"Route test failed with status {response.status_code}")
                return False
        
        return True
        
    except Exception as e:
        print_error(f"Installation verification failed: {e}")
        return False

def print_deployment_summary():
    """Print deployment summary and next steps"""
    print_step("Deployment Summary")
    
    print_success("NutriKid application deployed successfully!")
    print("\n📋 NEXT STEPS:")
    print("1. Start the application:")
    print("   python app.py")
    print("\n2. Open your browser and go to:")
    print("   http://localhost:8000 (or whichever free port is chosen)")
    print("\n3. Login with sample credentials:")
    print("   Super Admin: superadmin / admin123")
    print("   School Admin: admin / admin123")
    print("\n🔧 FEATURES AVAILABLE:")
    print("✅ User Management (Super Admin, Admin, Student roles)")
    print("✅ School Management")
    print("✅ Student Registration and Management")
    print("✅ BMI Calculation and Health Monitoring")
    
    print("✅ Dashboard with Analytics")
    print("✅ Reports and Data Export")
    print("✅ Notification System")
    print("✅ Password Reset Functionality")
    print("\n📁 PROJECT STRUCTURE:")
    print("├── app/                 # Main application package")
    print("├── migrations/          # Database migrations")
    print("├── static/             # Static files (CSS, JS, images)")
    print("├── templates/          # HTML templates")
    print("├── .env               # Environment configuration")
    print("├── app.py             # Application entry point")
    print("└── config.py          # Configuration settings")
    print("\n🛠️  TROUBLESHOOTING:")
    print("- If MySQL connection fails, check if MySQL is running")
    print("- If port 8000 is busy, the app will try port 5000")
    print("- Check logs in the console for any errors")
    print("- Ensure all dependencies are installed in the virtual environment")

def main():
    """Main deployment function"""
    print("🚀 NutriKid Application Deployment")
    print("=" * 60)
    print("This script will set up the complete NutriKid application")
    print("with all necessary components and sample data.")
    print("=" * 60)
    
    # Run deployment steps
    steps = [
        ("Python Version Check", check_python_version),
        ("MySQL Connection", check_mysql_connection),
        ("Dependencies Installation", install_dependencies),
        ("Database Setup", setup_database),
        ("Sample Data Creation", create_sample_data),
        ("Installation Verification", verify_installation)
    ]
    
    failed_steps = []
    
    for step_name, step_function in steps:
        if not step_function():
            failed_steps.append(step_name)
            print_error(f"Step '{step_name}' failed!")
            
            # Ask user if they want to continue
            response = input("\nDo you want to continue with the next step? (y/n): ")
            if response.lower() != 'y':
                print_error("Deployment aborted by user")
                return False
    
    if failed_steps:
        print_step("Deployment Completed with Issues")
        print_error("The following steps had issues:")
        for step in failed_steps:
            print(f"  - {step}")
        print_info("The application may still work, but some features might not be available.")
    else:
        print_deployment_summary()
    
    return len(failed_steps) == 0

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print_error("\nDeployment interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error during deployment: {e}")
        sys.exit(1)