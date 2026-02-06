import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import db, User, PayrollDoc, TimeLog, Comunicado, get_bogota_time
from datetime import datetime, timedelta, date, time
import pytz
import calendar
# from xhtml2pdf import pisa
# from io import BytesIO

admin_bp = Blueprint('admin', __name__)

# --- HELPERS FOR TIME AUDIT ---

def get_fortnight_range():
    """Returns start and end datetime for the current fortnight cycle."""
    now = get_bogota_time()
    if now.day <= 15:
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = now.replace(day=15, hour=23, minute=59, second=59, microsecond=999999)
    else:
        start_date = now.replace(day=16, hour=0, minute=0, second=0, microsecond=0)
        last_day = calendar.monthrange(now.year, now.month)[1]
        end_date = now.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)
    return start_date, end_date

def fmt_duration(seconds):
    """Format seconds into Xh Ym."""
    if seconds < 0: seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    if h > 0: 
        return f"{h}h {m}m"
    return f"{m}m"

def augment_logs_with_duration(logs):
    """
    Takes a list of TimeLog objects (sorted DESC or ASC? usually fetching DESC for display, 
    but for calculation ASC is easier).
    We will sort them ASC internally for calculation, then return them in original order (DESC).
    """
    if not logs:
        return []

    # Work with ASC order for logical diffs
    sorted_logs = sorted(logs, key=lambda x: x.timestamp)
    processed = []
    
    now_bogota = get_bogota_time().replace(tzinfo=None)

    for i, log in enumerate(sorted_logs):
        duration_seconds = 0
        is_excess = False
        excess_str = ""
        
        # Calculate Duration
        if i < len(sorted_logs) - 1:
            next_log = sorted_logs[i+1]
            duration_seconds = (next_log.timestamp - log.timestamp).total_seconds()
        else:
            # Last log (most recent)
            # If it's from today and not 'Inactivo', assume duration until now
            # Note: log.timestamp from DB might be naive or aware depending on driver.
            # We assume it matches get_bogota_time()'s nature (naive after strip) 
            # OR we try to handle both. simpler to make now_bogota match log.timestamp.tzinfo
            
            log_tz = log.timestamp.tzinfo
            current_now = get_bogota_time()
            if log_tz is None:
                current_now = current_now.replace(tzinfo=None)
            
            if log.timestamp.date() == current_now.date():
                if log.new_status != 'Inactivo':
                     duration_seconds = (current_now - log.timestamp).total_seconds()
            else:
                duration_seconds = 0 # Day closed without explicit logout

        # Determine Excess (Visual Only)
        # Rules: Break > 15m, Lunch > 60m
        if log.new_status == 'En Break' and duration_seconds > 15 * 60:
             is_excess = True
             excess = duration_seconds - (15*60)
             excess_str = f"+{int(excess//60)}m"
        elif log.new_status == 'En Almuerzo' and duration_seconds > 60 * 60:
             is_excess = True
             excess = duration_seconds - (60*60)
             excess_str = f"+{int(excess//60)}m"

        processed.append({
            'log': log,
            'duration_str': fmt_duration(duration_seconds),
            'duration_seconds': duration_seconds,
            'is_excess': is_excess,
            'excess_str': excess_str,
            'timestamp': log.timestamp
        })

    # Return in reverse order (DESC) as expected by template usually
    return processed[::-1]

def calculate_fortnight_debt(user_id):
    """Calculates total debt for the current fortnight."""
    start_date, end_date = get_fortnight_range()
    
    logs = TimeLog.query.filter(
        TimeLog.user_id == user_id,
        TimeLog.timestamp >= start_date,
        TimeLog.timestamp <= end_date
    ).order_by(TimeLog.timestamp).all()
    
    if not logs:
        return "0m"

    # We reuse the logic effectively, but we must group by day
    # First, get durations
    augmented = augment_logs_with_duration(logs) 
    # augmented is DESC, let's reverse to ASC for daily processing
    daily_items = augmented[::-1] 
    
    logs_by_date = {}
    for item in daily_items:
        d = item['timestamp'].date()
        if d not in logs_by_date: logs_by_date[d] = []
        logs_by_date[d].append(item)
    
    total_debt_seconds = 0
    now_date = get_bogota_time().date()

    for d, items in logs_by_date.items():
        # 1. Late Start (> 8:30 AM)
        first_active = next((x for x in items if x['log'].new_status == 'Activo'), None)
        if first_active:
            # Construct 8:30 on that day. careful with timezones.
            # item['timestamp'] has the tz info of the log.
            limit_830 = item['timestamp'].replace(hour=8, minute=30, second=0, microsecond=0)
            if item['timestamp'] > limit_830:
                total_debt_seconds += (item['timestamp'] - limit_830).total_seconds()
        
        # 2. Early Departure (< 4:30 PM) - Only for past days
        if d < now_date:
            last_item = items[-1] # Last log of the day
            # If they didn't logout, last item is whatever status. 
            # If they did logout, last status is Inactivo.
            # We assume the END of the last event is the 'departure time'.
            # If last event was 'Inactivo', departure was at timestamp.
            # If last event was 'Activo' (forgot to logout), technically they left at ??? 
            # Let's assume strict rule: Reference point is the timestamp of the LAST log entry.
            
            limit_1630 = last_item['timestamp'].replace(hour=16, minute=30, second=0, microsecond=0)
            
            # If the last log happened before 16:30
            if last_item['timestamp'] < limit_1630:
                total_debt_seconds += (limit_1630 - last_item['timestamp']).total_seconds()

        # 3. Cumulative Break Debt
        total_break = sum(x['duration_seconds'] for x in items if x['log'].new_status == 'En Break')
        if total_break > 15 * 60:
            total_debt_seconds += (total_break - 15 * 60)

        # 4. Cumulative Lunch Debt
        total_lunch = sum(x['duration_seconds'] for x in items if x['log'].new_status == 'En Almuerzo')
        if total_lunch > 60 * 60:
            total_debt_seconds += (total_lunch - 60 * 60)

    return fmt_duration(total_debt_seconds)


# Middleware to ensure only admins can access these routes
@admin_bp.before_request
@login_required
def admin_required():
    if current_user.rol != 'Admin':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('employee.dashboard'))

@admin_bp.route('/dashboard')
def dashboard():
    users = User.query.filter(User.rol != 'Admin').all()
    return render_template('admin/dashboard.html', users=users)

@admin_bp.route('/create_user', methods=['GET', 'POST'])
def create_user():
    if request.method == 'POST':
        email = request.form.get('email')
        # Check if user exists
        if User.query.filter_by(email=email).first():
            flash('El usuario ya existe.', 'warning')
            return redirect(url_for('admin.create_user'))

        # Basic Info
        nombre = request.form.get('nombre')
        password = request.form.get('password')
        telefono = request.form.get('telefono')
        cargo = request.form.get('cargo')
        fecha_ingreso_str = request.form.get('fecha_ingreso')
        tipo_contrato = request.form.get('tipo_contrato')
        salario_str = request.form.get('salario')
        salario = float(salario_str) if salario_str else 0.0
        
        # New Fields
        eps = request.form.get('eps')
        arl = request.form.get('arl')
        caja_compensacion = request.form.get('caja_compensacion')
        fondo_pensiones = request.form.get('fondo_pensiones')
        cesantias = request.form.get('cesantias')
        entidad_bancaria = request.form.get('entidad_bancaria')
        numero_cuenta = request.form.get('numero_cuenta')
        direccion = request.form.get('direccion')
        tipo_sangre = request.form.get('tipo_sangre')

        # Handle Profile Picture
        foto_perfil = None
        if 'foto_perfil' in request.files:
            file = request.files['foto_perfil']
            if file and file.filename != '':
                filename = secure_filename(f"profile_{email}_{int(datetime.now().timestamp())}_{file.filename}")
                save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profile_pics')
                os.makedirs(save_path, exist_ok=True)
                file.save(os.path.join(save_path, filename))
                foto_perfil = filename

        fecha_ingreso = None
        if fecha_ingreso_str:
            try:
                fecha_ingreso = datetime.strptime(fecha_ingreso_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Formato de fecha inválido.', 'danger')
                return redirect(url_for('admin.create_user'))

        new_user = User(
            email=email,
            rol='Empleado',
            nombre=nombre,
            cargo=cargo,
            fecha_ingreso=fecha_ingreso,
            salario=salario,
            tipo_contrato=tipo_contrato,
            telefono=telefono,
            eps=eps,
            arl=arl,
            caja_compensacion=caja_compensacion,
            fondo_pensiones=fondo_pensiones,
            cesantias=cesantias,
            entidad_bancaria=entidad_bancaria,
            numero_cuenta=numero_cuenta,
            direccion=direccion,
            tipo_sangre=tipo_sangre,
            foto_perfil=foto_perfil
        )
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        flash('Usuario creado exitosamente con todos los datos.', 'success')
        return redirect(url_for('admin.dashboard'))

    return render_template('admin/create_user.html')

@admin_bp.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if current_user.rol != 'Admin':
        return redirect(url_for('employee.dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        # Retrieve form data
        user.nombre = request.form.get('nombre')
        user.email = request.form.get('email')
        
        password = request.form.get('password')
        if password:
            user.set_password(password)
            
        user.telefono = request.form.get('telefono')
        user.cargo = request.form.get('cargo')
        user.tipo_contrato = request.form.get('tipo_contrato')
        
        salario_str = request.form.get('salario')
        user.salario = float(salario_str) if salario_str else 0.0
        
        fecha_ingreso_str = request.form.get('fecha_ingreso')
        if fecha_ingreso_str:
            try:
                user.fecha_ingreso = datetime.strptime(fecha_ingreso_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Formato de fecha inválido.', 'danger')
                return redirect(url_for('admin.edit_user', user_id=user.id))
        else:
            user.fecha_ingreso = None
            
        user.eps = request.form.get('eps')
        user.arl = request.form.get('arl')
        user.caja_compensacion = request.form.get('caja_compensacion')
        user.fondo_pensiones = request.form.get('fondo_pensiones')
        user.cesantias = request.form.get('cesantias')
        user.entidad_bancaria = request.form.get('entidad_bancaria')
        user.numero_cuenta = request.form.get('numero_cuenta')
        user.direccion = request.form.get('direccion')
        user.tipo_sangre = request.form.get('tipo_sangre')
        
        if 'foto_perfil' in request.files:
            file = request.files['foto_perfil']
            if file and file.filename != '':
                filename = secure_filename(f"profile_{user.email}_{int(datetime.now().timestamp())}_{file.filename}")
                save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profile_pics')
                os.makedirs(save_path, exist_ok=True)
                file.save(os.path.join(save_path, filename))
                user.foto_perfil = filename
                
        db.session.commit()
        flash('Empleado actualizado exitosamente.', 'success')
        return redirect(url_for('admin.dashboard'))
        
    return render_template('admin/edit_user.html', user=user)

@admin_bp.route('/view_employee_profile/<int:user_id>')
@login_required
def view_employee_profile(user_id):
    if current_user.rol != 'Admin':
        return redirect(url_for('employee.dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    # Logic duplicated from employee.dashboard to show correct stats for THIS user
    payrolls = PayrollDoc.query.filter_by(user_id=user.id).order_by(PayrollDoc.created_at.desc()).all()
    comunicados = Comunicado.query.order_by(Comunicado.fecha_publicacion.desc()).all()
    
    # 1. Calculate Hours Worked Today for the target user
    today_start = get_bogota_time().replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    logs_today = TimeLog.query.filter(TimeLog.user_id == user.id, TimeLog.timestamp >= today_start).order_by(TimeLog.timestamp).all()
    
    total_seconds = 0
    start_time = None
    
    for log in logs_today:
        if log.new_status == 'Activo':
            if start_time is None:
                start_time = log.timestamp
        else:
            if start_time:
                total_seconds += (log.timestamp - start_time).total_seconds()
                start_time = None
                
    if start_time and user.current_status == 'Activo':
         total_seconds += (get_bogota_time().replace(tzinfo=None) - start_time).total_seconds()
         
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    hours_worked_str = f"{hours}h {minutes}m"
    
    # 2. Next Payment Date
    today = date.today()
    if today.day <= 15:
        next_pay_date = date(today.year, today.month, 15)
    else:
        last_day = calendar.monthrange(today.year, today.month)[1]
        next_pay_date = date(today.year, today.month, last_day)
        
    months_es = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    next_payment_str = f"{next_pay_date.day} de {months_es[next_pay_date.month - 1]}"
    
    # 3. Last Communication
    last_comunicado_title = comunicados[0].titulo if comunicados else "Sin novedades"

    return render_template('employee/dashboard.html', 
                           payrolls=payrolls, 
                           comunicados=comunicados,
                           hours_worked=hours_worked_str,
                           next_payment=next_payment_str,
                           last_notif=last_comunicado_title,
                           user=user,
                           is_admin_view=True)

@admin_bp.route('/time_tracking')
@login_required
def time_tracking():
    if current_user.rol != 'Admin':
         return redirect(url_for('employee.dashboard'))
         
    # Get all employees
    employees = User.query.filter(User.rol != 'Admin').all()
    
    # Calculate Debt for each employee
    for emp in employees:
        emp.debt_str = calculate_fortnight_debt(emp.id)
    
    # Get recent logs (optional, could be passed to view for history tab)
    recent_logs = TimeLog.query.order_by(TimeLog.timestamp.desc()).limit(50).all()
    
    return render_template('admin/time_tracking.html', employees=employees, logs=recent_logs)

@admin_bp.route('/time_history/<int:user_id>')
@login_required
def time_history(user_id):
    if current_user.rol != 'Admin':
         return redirect(url_for('employee.dashboard'))
    
    user = User.query.get_or_404(user_id)
    # Get All logs for history
    logs = TimeLog.query.filter_by(user_id=user_id).order_by(TimeLog.timestamp.desc()).all()
    
    # Augment with duration
    processed_logs = augment_logs_with_duration(logs)
    
    return render_template('admin/time_history.html', user=user, logs=processed_logs)

from services.payroll_service import PayrollService

@admin_bp.route('/create_payroll', methods=['GET', 'POST'])
@login_required
def create_payroll():
    if current_user.rol != 'Admin':
         return redirect(url_for('employee.dashboard'))
    
    if request.method == 'POST':
        user_id = int(request.form.get('user_id') or 0)
        
        financial_data = {
            'salario_base': float(request.form.get('salario_base') or 0.0),
            'auxilio_transporte': float(request.form.get('auxilio_transporte') or 0.0),
            'bonificaciones': float(request.form.get('bonificaciones') or 0.0),
            'dias_injustificados': int(request.form.get('dias_injustificados') or 0),
            'valor_descuento_dias': float(request.form.get('valor_descuento_dias') or 0.0),
            'aporte_salud': float(request.form.get('aporte_salud') or 0.0),
            'aporte_pension': float(request.form.get('aporte_pension') or 0.0),
            'otros_descuentos': float(request.form.get('otros_descuentos') or 0.0)
        }
        
        success = PayrollService.create_payroll_record(
            user_id=user_id,
            mes=request.form.get('mes'),
            anio=int(request.form.get('anio') or 0),
            periodo=request.form.get('periodo'),
            financial_data=financial_data
        )
            
        if success:
            flash('Nómina generada exitosamente.', 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Error al generar el PDF o guardar el registro.', 'danger')
            
    users: list[User] = User.query.filter(User.rol != 'Admin').all()
    return render_template('admin/create_payroll.html', users=users)

@admin_bp.route('/crear_comunicado', methods=['GET', 'POST'])
@login_required
def crear_comunicado():
    if current_user.rol != 'Admin':
        return redirect(url_for('employee.dashboard'))
        
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        contenido = request.form.get('contenido')
        file = request.files.get('archivo')
        
        archivo_filename = None
        if file and file.filename != '':
            if file.filename.endswith('.pdf'):
                archivo_filename = secure_filename(f"comunicado_{int(datetime.now().timestamp())}_{file.filename}")
                save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'comunicados')
                os.makedirs(save_path, exist_ok=True)
                file.save(os.path.join(save_path, archivo_filename))
            else:
                flash('Solo se permiten archivos PDF.', 'danger')
                return redirect(request.url)
        
        nuevo_comunicado = Comunicado(
            titulo=titulo,
            contenido=contenido,
            archivo=archivo_filename,
            user_id=current_user.id
        )
        
        db.session.add(nuevo_comunicado)
        db.session.commit()
        
        flash('Comunicado publicado exitosamente.', 'success')
        return redirect(url_for('admin.dashboard'))
        
    return render_template('admin/crear_comunicado.html')

