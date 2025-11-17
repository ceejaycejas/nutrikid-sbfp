from flask import Blueprint, redirect, url_for, render_template, request, flash
from flask_login import current_user
from app import db
from app.models.user_activity import UserActivity

def log_activity(user_id, activity_type, description, ip_address=None):
    if user_id:  # Only log if user is authenticated
        activity = UserActivity(user_id=user_id, activity_type=activity_type, description=description, ip_address=ip_address)
        db.session.add(activity)
        db.session.commit()

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    if current_user.is_authenticated:
        log_activity(current_user.id, 'home_redirect', 'Redirected from home to dashboard', request.remote_addr)
        return redirect(url_for('school.dashboard'))
    return render_template('landing.html')

@bp.route('/forgot-password')
def forgot_password_redirect():
    """Redirect to auth forgot password page"""
    return redirect(url_for('auth.forgot_password'))

@bp.route('/newsletter/subscribe', methods=['POST'])
def newsletter_subscribe():
    """Handle newsletter subscription"""
    email = request.form.get('email')
    if email:
        # TODO: Add email to newsletter database or service
        flash('Thank you for subscribing! You will receive updates at ' + email, 'success')
    else:
        flash('Please provide a valid email address.', 'error')
    return redirect(url_for('main.index')) 