from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.password_reset import PasswordResetRequest
from app.services.password_reset_service import PasswordResetService
from datetime import datetime

bp = Blueprint('password_reset', __name__, url_prefix='/password-reset')

@bp.route('/request', methods=['GET', 'POST'])
def request_reset():
    """Student/Admin request password reset"""
    if request.method == 'POST':
        email = request.form.get('email')
        reason = request.form.get('reason', '').strip()
        
        if not email:
            flash('Email address is required', 'danger')
            return redirect(url_for('password_reset.request_reset'))
        
        # Find user by email
        user = User.query.filter_by(email=email).first()
        if not user:
            # Don't reveal if email exists or not for security
            flash('If an account with that email exists, a password reset request has been submitted.', 'info')
            return redirect(url_for('auth.login'))
        
        # Only students and admins can request password reset
        if user.role not in ['student', 'admin']:
            flash('Password reset is not available for your account type.', 'danger')
            return redirect(url_for('auth.login'))
        
        # Create reset request
        reset_request, message = PasswordResetService.create_reset_request(user.id, reason)
        
        if reset_request:
            return redirect(url_for('password_reset.request_success'))
        else:
            flash(message, 'danger')
    
    return render_template('password_reset/request.html')

@bp.route('/success')
def request_success():
    """Show success page after password reset request submission"""
    return render_template('password_reset/request_success.html')


@bp.route('/my-requests')
@login_required
def my_requests():
    """View user's own password reset requests"""
    if current_user.role not in ['student', 'admin']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    user_requests = PasswordResetRequest.query.filter_by(
        user_id=current_user.id
    ).order_by(PasswordResetRequest.created_at.desc()).limit(10).all()
    
    return render_template('password_reset/my_requests.html', requests=user_requests)

@bp.route('/cleanup-expired', methods=['POST'])
@login_required
def cleanup_expired():
    """Cleanup expired password reset requests (Super admin only)"""
    if current_user.role != 'super_admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    cleaned_count = PasswordResetService.cleanup_expired_requests()
    
    return jsonify({
        'success': True,
        'message': f'Cleaned up {cleaned_count} expired requests'
    })

@bp.route('/clear-all', methods=['POST'])
@login_required
def clear_all():
    """Clear all password reset requests (Super admin only)"""
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    cleared = PasswordResetService.clear_all_requests()
    
    # Always redirect for form submissions
    flash(f'Successfully cleared {cleared} password reset request(s).', 'success')
    return redirect(url_for('school.dashboard'))

# Add to auth routes - forgot password link
@bp.route('/forgot-password')
def forgot_password():
    """Redirect to password reset request page"""
    return redirect(url_for('password_reset.request_reset'))