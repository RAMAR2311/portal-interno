from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from models import User, TimeLog, db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Verificar si el usuario ya está autenticado
    if current_user.is_authenticated:
        if current_user.rol == 'Admin':
            return redirect(url_for('admin.dashboard'))
        elif current_user.rol == 'Empleado':
            return redirect(url_for('employee.dashboard'))
        else:
            # Fallback por si hay otro rol
            return redirect(url_for('employee.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user)
            
            # --- TIME TRACKING START ---
            if user.rol != 'Admin':
                user.current_status = 'Activo'
                new_log = TimeLog(user_id=user.id, new_status='Activo')
                db.session.add(new_log)
                db.session.commit()
            # --- TIME TRACKING END ---

            if user.rol == 'Admin':
                return redirect(url_for('admin.dashboard'))
            else:
                return redirect(url_for('employee.dashboard'))
        else:
            flash('Email o contraseña incorrectos.', 'danger')
            
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    # --- TIME TRACKING STOP ---
    if current_user.rol != 'Admin':
        current_user.current_status = 'Inactivo'
        new_log = TimeLog(user_id=current_user.id, new_status='Inactivo')
        db.session.add(new_log)
        db.session.commit()
    # --- TIME TRACKING END ---
    
    logout_user()
    return redirect(url_for('auth.login'))
