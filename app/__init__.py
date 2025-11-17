from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail
from config import Config
from app.routes.beneficiary import bp as beneficiary_bp

# ✅ Fix for Windows: Use PyMySQL instead of MySQLdb
import pymysql
pymysql.install_as_MySQLdb()

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
mail = Mail()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    with app.app_context():
        # Import models and routes here to register with the app
        from app.models import User, School, Student, Section, GradeLevel, Notification, PasswordResetRequest, UserActivity
        from app.routes import auth, school, main, section, account, student, super_admin, reports, notifications, password_reset

        # Register blueprints
        app.register_blueprint(main.bp)
        app.register_blueprint(auth.bp)
        app.register_blueprint(school.bp)
        app.register_blueprint(section.bp)
        app.register_blueprint(account.bp)
        app.register_blueprint(student.bp)
        app.register_blueprint(super_admin.bp)
        app.register_blueprint(reports.bp)
        app.register_blueprint(beneficiary_bp)
        app.register_blueprint(notifications.bp)
        app.register_blueprint(password_reset.bp)

        # Create all database tables (if not already created)
        db.create_all()
        
        # Register error handlers
        register_error_handlers(app)

    return app

def register_error_handlers(app):
    """Register global error handlers"""
    from flask import render_template, request, flash, redirect, url_for
    
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(Exception)
    def handle_exception(e):
        # Log the error
        app.logger.error(f'Unhandled exception: {str(e)}')
        
        # If it's an HTTP exception, return the appropriate error page
        if hasattr(e, 'code'):
            if e.code == 404:
                return render_template('errors/404.html'), 404
            elif e.code == 403:
                return render_template('errors/403.html'), 403
            elif e.code == 500:
                return render_template('errors/500.html'), 500
        
        # For any other exception, return 500
        db.session.rollback()
        return render_template('errors/500.html'), 500
