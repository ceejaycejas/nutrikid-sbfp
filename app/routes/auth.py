from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from app.models.user import User
from app.models.school import School
from app.models.password_reset import PasswordResetRequest
from app.utils.password_validator import PasswordValidator
from app.services.password_reset_service import PasswordResetService
from app import db
from datetime import datetime
from app.routes.school import log_activity

bp = Blueprint('auth', __name__, url_prefix='/auth')
password_validator = PasswordValidator()

def clear_inappropriate_flash_messages():
    """Clear flash messages that shouldn't appear on login/logout pages"""
    if '_flashes' in session:
        # Filter out messages that are inappropriate for login page
        inappropriate_messages = [
            'Report sent to Super Admin successfully!',
            'Notification deleted.',
            'Notification marked as read.',
            'Student added successfully!',
            'Student created successfully!',
            'Student updated successfully!',
            'Student deleted successfully!',
            'Profile picture updated!',
            'Cover image updated!',
            'Your account has been updated successfully!'
        ]
        
        # Get current flashes
        flashes = session.get('_flashes', [])
        # Filter out inappropriate messages
        filtered_flashes = []
        for category, message in flashes:
            if not any(inappropriate_msg in message for inappropriate_msg in inappropriate_messages):
                filtered_flashes.append((category, message))
        
        # Update session with filtered messages
        session['_flashes'] = filtered_flashes

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user:
            if user.is_account_locked():
                minutes_remaining = user.get_lock_time_remaining()
                flash(f'Account is locked. Please try again in {minutes_remaining} minutes.', 'danger')
                log_activity(user.id, 'login_attempt', f'Account locked, login attempt blocked for user {email}', request.remote_addr)
                return render_template('auth/animated_auth.html', initial_state='login')
            
            if user.check_password(password):
                login_user(user)
                log_activity(user.id, 'login', f'User logged in successfully: {email}', request.remote_addr)
                next_page = request.args.get('next')
                return redirect(next_page or url_for('school.dashboard'))
            else:
                attempts_remaining = 3 - user.login_attempts
                if attempts_remaining > 0:
                    flash(f'Invalid email or password. {attempts_remaining} attempts remaining.', 'danger')
                    log_activity(user.id, 'login_failed', f'Invalid password attempt for user {email}', request.remote_addr)
                else:
                    flash('Account has been locked for 15 minutes due to too many failed attempts.', 'danger')
                    log_activity(user.id, 'account_locked', f'Account locked due to too many failed login attempts for user {email}', request.remote_addr)
        else:
            flash('Invalid email or password', 'danger')
            log_activity(None, 'login_failed', f'Login attempt with unknown email: {email}', request.remote_addr)
        
        return render_template('auth/animated_auth.html', initial_state='login')

    # Clear inappropriate flash messages when showing login page
    clear_inappropriate_flash_messages()
    return render_template('auth/animated_auth.html', initial_state='login')



@bp.route('/logout')
@login_required
def logout():
    log_activity(current_user.id, 'logout', f'User logged out: {current_user.email}', request.remote_addr)
    logout_user()
    # Clear any inappropriate messages before setting logout message
    clear_inappropriate_flash_messages()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Simple forgot password page"""
    if request.method == 'POST':
        email = request.form.get('email')
        reason = request.form.get('reason', 'User requested password reset via forgot password form')
        
        if not email:
            flash('Email address is required', 'danger')
            return render_template('auth/forgot_password.html')
        
        # Find user by email
        user = User.query.filter_by(email=email).first()
        if user:
            # Create password reset request
            success, message = PasswordResetService.create_reset_request(user.id, reason)
            if success:
                flash('Password reset request submitted successfully. You will be notified when it is processed.', 'success')
            else:
                flash(message, 'warning')
        else:
            # Don't reveal if email exists or not for security
            flash('If an account with that email exists, a password reset request has been submitted.', 'info')
        
        return render_template('auth/forgot_password.html')
    
    return render_template('auth/forgot_password.html')