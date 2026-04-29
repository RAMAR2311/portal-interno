import os
from flask import Blueprint, render_template, make_response, current_app, send_from_directory, flash, request, redirect, url_for, jsonify
from flask_login import login_required, current_user
from xhtml2pdf import pisa
from io import BytesIO
from models import PayrollDoc, TimeLog, Comunicado, db
from datetime import datetime, date, timedelta
import calendar
import pytz

employee_bp = Blueprint('employee', __name__)

@employee_bp.route('/change_status', methods=['POST'])
@login_required
def change_status():
    new_status = request.form.get('status')
    valid_statuses = ['Activo', 'En Break', 'En Almuerzo', 'Inactivo'] # Inactivo usually for logout, but kept for completeness
    
    if new_status not in valid_statuses:
        flash('Estado inválido.', 'danger')
        return redirect(url_for('employee.dashboard'))
        
    current_user.current_status = new_status
    new_log = TimeLog(user_id=current_user.id, new_status=new_status)
    db.session.add(new_log)
    db.session.commit()
    
    flash(f'Estado actualizado a: {new_status}', 'success')
    return redirect(url_for('employee.dashboard'))

@employee_bp.route('/dashboard')
@login_required
def dashboard():
    payrolls = PayrollDoc.query.filter_by(user_id=current_user.id).order_by(PayrollDoc.created_at.desc()).all()
    comunicados = Comunicado.query.filter((Comunicado.recipient_id == current_user.id) | (Comunicado.recipient_id == None)).order_by(Comunicado.fecha_publicacion.desc()).all()
    
    # 1. Calculate Hours Worked Today
    today_start = datetime.now(pytz.timezone('America/Bogota')).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    logs_today = TimeLog.query.filter(TimeLog.user_id == current_user.id, TimeLog.timestamp >= today_start).order_by(TimeLog.timestamp).all()
    
    total_seconds = 0
    start_time = None
    
    # If the user started the day 'Activo' (unlikely but possible if carry over, though simple logic assumes start from first log)
    # Actually, let's just look at transitions today.
    # If first log is NOT 'Activo', we assume they weren't working before.
    # If no logs, but current status is 'Activo' (maybe logged in yesterday and never logged out? Edge case), we count from 00:00? 
    # Let's stick to simple: iterate logs.
    
    for log in logs_today:
        if log.new_status == 'Activo':
            if start_time is None:
                start_time = log.timestamp
        else:
            # If we were active, add time
            if start_time:
                total_seconds += (log.timestamp - start_time).total_seconds()
                start_time = None
                
    # If still active right now
    if start_time and current_user.current_status == 'Activo':
         total_seconds += (datetime.now(pytz.timezone('America/Bogota')).replace(tzinfo=None) - start_time).total_seconds()
         
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    hours_worked_str = f"{hours}h {minutes}m"
    
    # 2. Next Payment Date
    today = date.today()
    if today.day <= 15:
        # Calculate 15th of this month
        next_pay_date = date(today.year, today.month, 15)
    else:
        # Calculate last day of this month
        last_day = calendar.monthrange(today.year, today.month)[1]
        next_pay_date = date(today.year, today.month, last_day)
        
    # Format date in Spanish manually or simple format
    months_es = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    next_payment_str = f"{next_pay_date.day} de {months_es[next_pay_date.month - 1]}"
    
    # 3. Last Communication
    last_comunicado_title = comunicados[0].titulo if comunicados else "Sin novedades"

    from models import WeeklySchedule
    mi_horario = WeeklySchedule.query.filter_by(user_id=current_user.id).order_by(WeeklySchedule.dia_semana).all()

    return render_template('employee/dashboard.html', 
                           payrolls=payrolls, 
                           comunicados=comunicados,
                           hours_worked=hours_worked_str,
                           next_payment=next_payment_str,
                           last_notif=last_comunicado_title,
                           mi_horario=mi_horario,
                           user=current_user)


@employee_bp.route('/download_certificate')
@login_required
def download_certificate():
    # Helper to convert HTML to PDF
    def create_pdf(pdf_data):
        pdf = BytesIO()
        pisa_status = pisa.CreatePDF(BytesIO(pdf_data.encode('utf-8')), dest=pdf)
        if pisa_status.err:
            return None
        return pdf.getvalue()

    # Data for the certificate
    context = {
        'nombre': current_user.nombre,
        'cargo': current_user.cargo,
        'fecha_ingreso': current_user.fecha_ingreso.strftime('%d of %B, %Y'), # Format as needed
        'salario': f"${current_user.salario:,.2f}",
        'tipo_contrato': current_user.tipo_contrato
    }
    
    # Render HTML template for PDF
    html_content = render_template('employee/certificate_template.html', **context)
    
    pdf_content = create_pdf(html_content)
    
    if pdf_content:
        response = make_response(pdf_content)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=Certificado_Laboral_{current_user.nombre}.pdf'
        return response
    
    flash("Error generando el certificado.", "danger")
    return redirect(url_for('employee.dashboard'))

@employee_bp.route('/download_payroll/<int:doc_id>')
@login_required
def download_payroll(doc_id):
    doc = PayrollDoc.query.get_or_404(doc_id)
    if doc.user_id != current_user.id and current_user.rol != 'Admin':
        flash("Acceso denegado.", "danger")
        return redirect(url_for('employee.dashboard'))
    
    directory = os.path.join(current_app.config['UPLOAD_FOLDER'], 'payrolls')
    return send_from_directory(directory, doc.filename, as_attachment=True)

@employee_bp.route('/download_comunicado/<int:comunicado_id>')
@login_required
def download_comunicado(comunicado_id):
    comunicado = Comunicado.query.get_or_404(comunicado_id)
    
    if not comunicado.archivo:
        flash("No hay archivo adjunto.", "warning")
        return redirect(url_for('employee.dashboard'))
    
    directory = os.path.join(current_app.config['UPLOAD_FOLDER'], 'comunicados')
    return send_from_directory(directory, comunicado.archivo, as_attachment=False)

@employee_bp.route('/download_incapacidad/<int:id>')
@login_required
def download_incapacidad(id):
    inc = Incapacidad.query.get_or_404(id)
    if inc.user_id != current_user.id and current_user.rol != 'Admin':
        flash("Acceso denegado.", "danger")
        return redirect(url_for('employee.mis_incapacidades'))
    
    directory = os.path.join(current_app.config['UPLOAD_FOLDER'], 'incapacidades')
    return send_from_directory(directory, inc.archivo_soporte, as_attachment=False)


from services.payroll_service import PayrollService
from models import PayrollAdvance

@employee_bp.route('/solicitar_adelanto', methods=['GET', 'POST'])
@login_required
def solicitar_adelanto():
    if request.method == 'POST':
        monto_str = request.form.get('monto', '0')
        motivo = request.form.get('motivo', '')
        
        try:
            monto = float(monto_str)
        except ValueError:
            flash("Monto inválido.", "danger")
            return redirect(url_for('employee.solicitar_adelanto'))
            
        success, msg = PayrollService.request_advance(current_user.id, monto, motivo)
        if success:
            flash(msg, "success")
            return redirect(url_for('employee.solicitar_adelanto'))
        else:
            flash(msg, "danger")
            
    advances = PayrollAdvance.query.filter_by(user_id=current_user.id).order_by(PayrollAdvance.fecha_solicitud.desc()).all()
    max_monto = (current_user.salario * 0.5) if current_user.salario else 0
    return render_template('employee/solicitud_adelanto.html', max_monto=max_monto, advances=advances)


from sqlalchemy.orm import joinedload
from models import Survey, SurveyQuestion, SurveyResponse, SurveyAnswer

@employee_bp.route('/surveys')
@login_required
def list_surveys():
    # Only active surveys that user hasn't answered
    answered_subquery = db.session.query(SurveyResponse.survey_id).filter(SurveyResponse.user_id == current_user.id).subquery()
    
    pending_surveys = Survey.query.filter(
        Survey.esta_activa == True,
        ~Survey.id.in_(answered_subquery)
    ).order_by(Survey.creado_en.desc()).all()
    
    answered_surveys = Survey.query.join(SurveyResponse).filter(
        SurveyResponse.user_id == current_user.id
    ).order_by(SurveyResponse.respondido_en.desc()).all()
    
    return render_template('employee/surveys_list.html', pending=pending_surveys, answered=answered_surveys)

@employee_bp.route('/surveys/take/<int:survey_id>', methods=['GET', 'POST'])
@login_required
def take_survey(survey_id):
    survey = Survey.query.options(joinedload(Survey.questions).joinedload(SurveyQuestion.options)).get_or_404(survey_id)
    
    if not survey.esta_activa:
        flash("Esta encuesta ya no está activa.", "warning")
        return redirect(url_for('employee.list_surveys'))
        
    existing_response = SurveyResponse.query.filter_by(survey_id=survey_id, user_id=current_user.id).first()
    if existing_response:
        flash("Ya has respondido esta encuesta.", "warning")
        return redirect(url_for('employee.list_surveys'))
        
    if request.method == 'POST':
        try:
            response = SurveyResponse(survey_id=survey.id, user_id=current_user.id)
            db.session.add(response)
            db.session.flush()
            
            for q in survey.questions:
                ans_val = request.form.get(f'question_{q.id}')
                if ans_val:
                    answer = SurveyAnswer(response_id=response.id, question_id=q.id, respuesta_texto=ans_val)
                    db.session.add(answer)
                    
            db.session.commit()
            flash("Encuesta enviada exitosamente. ¡Gracias!", "success")
            return redirect(url_for('employee.list_surveys'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error al guardar respuestas: {str(e)}", "danger")
    return render_template('employee/take_survey.html', survey=survey)

# --- RUTAS PARA PAUSAS ACTIVAS ---
from models import PauseAssignment

@employee_bp.route('/pausas/finalizar/<int:assignment_id>', methods=['POST'])
@login_required
def finalizar_pausa(assignment_id):
    asignacion = PauseAssignment.query.get_or_404(assignment_id)
    
    # Validar que sea el usuario correcto
    if asignacion.user_id != current_user.id:
        return jsonify({'error': 'No autorizado'}), 403
        
    # Cambiar estado de asignación
    asignacion.completado = True
    asignacion.fecha_completado = datetime.now(pytz.timezone('America/Bogota')).replace(tzinfo=None)
    
    # Rastrear jornada laboral (De "En Pausa Activa" a "Activo")
    if current_user.current_status == 'En Pausa Activa':
        current_user.current_status = 'Activo'
        new_log = TimeLog(user_id=current_user.id, new_status='Activo')
        db.session.add(new_log)
        
    db.session.commit()
    
    return jsonify({'status': 'success', 'message': 'Pausa finalizada correctamente'})

@employee_bp.route('/pausas/iniciar/<int:assignment_id>', methods=['POST'])
@login_required
def iniciar_pausa(assignment_id):
    asignacion = PauseAssignment.query.get_or_404(assignment_id)
    if asignacion.user_id != current_user.id:
        return jsonify({'error': 'No autorizado'}), 403

    if current_user.current_status == 'Activo':
        current_user.current_status = 'En Pausa Activa'
        new_log = TimeLog(user_id=current_user.id, new_status='En Pausa Activa')
        db.session.add(new_log)
        db.session.commit()

    return jsonify({'status': 'success'})

# --- FUNCION AUXILIAR PARA ARCHIVOS ---
from werkzeug.utils import secure_filename

def guardar_archivo_incapacidad(file, user_id):
    allowed_extensions = {'.pdf', '.png', '.jpg', '.jpeg'}
    ext = os.path.splitext(file.filename)[1].lower()
    
    if ext not in allowed_extensions:
        return False, None
        
    timestamp = int(datetime.now().timestamp())
    filename = secure_filename(f"incapacidad_{user_id}_{timestamp}{ext}")
    
    save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'incapacidades')
    os.makedirs(save_path, exist_ok=True)
    
    file.save(os.path.join(save_path, filename))
    return True, filename

# --- RUTAS DE INCAPACIDADES ---
from models import Incapacidad

@employee_bp.route('/mis_incapacidades')
@login_required
def mis_incapacidades():
    incapacidades = Incapacidad.query.filter_by(user_id=current_user.id).order_by(Incapacidad.fecha_reporte.desc()).all()
    return render_template('employee/incapacidad_form.html', incapacidades=incapacidades)

@employee_bp.route('/reportar_incapacidad', methods=['POST'])
@login_required
def reportar_incapacidad():
    tipo = request.form.get('tipo')
    diagnostico = request.form.get('diagnostico')
    entidad_salud = request.form.get('entidad_salud')
    fecha_inicio_str = request.form.get('fecha_inicio')
    fecha_fin_str = request.form.get('fecha_fin')
    archivo = request.files.get('archivo_soporte')
    
    try:
        fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
        fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Formato de fecha inválido.', 'danger')
        return redirect(url_for('employee.mis_incapacidades'))
        
    if fecha_fin < fecha_inicio:
        flash('La fecha de fin no puede ser anterior a la fecha de inicio.', 'danger')
        return redirect(url_for('employee.mis_incapacidades'))
        
    dias_totales = (fecha_fin - fecha_inicio).days + 1
    
    if not archivo or archivo.filename == '':
        flash('El soporte médico es obligatorio.', 'warning')
        return redirect(url_for('employee.mis_incapacidades'))
        
    exito, filename = guardar_archivo_incapacidad(archivo, current_user.id)
    if not exito:
        flash('Formato de archivo no permitido. Sube PDF o imágenes.', 'danger')
        return redirect(url_for('employee.mis_incapacidades'))
        
    nueva_incapacidad = Incapacidad(
        user_id=current_user.id,
        tipo=tipo,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        dias_totales=dias_totales,
        diagnostico=diagnostico,
        entidad_salud=entidad_salud,
        archivo_soporte=filename
    )
    
    db.session.add(nueva_incapacidad)
    db.session.commit()
    
    # Emitir notificación en tiempo real a los administradores
    from extensions import socketio
    socketio.emit('new_incapacidad', {
        'empleado': current_user.nombre,
        'tipo': tipo,
        'dias': dias_totales
    }, room='admin_room')
    
    flash('Incapacidad reportada exitosamente.', 'success')
    return redirect(url_for('employee.mis_incapacidades'))

# --- RUTAS DE PERMISOS / LEAVE REQUESTS ---
from models import LeaveRequest

@employee_bp.route('/mis_permisos')
@login_required
def mis_permisos():
    permisos = LeaveRequest.query.filter_by(user_id=current_user.id).order_by(LeaveRequest.fecha_solicitud.desc()).all()
    return render_template('employee/permisos_form.html', permisos=permisos)

@employee_bp.route('/solicitar_permiso', methods=['POST'])
@login_required
def solicitar_permiso():
    tipo_permiso = request.form.get('tipo_permiso')
    fecha_inicio_str = request.form.get('fecha_inicio')
    fecha_fin_str = request.form.get('fecha_fin')
    motivo = request.form.get('motivo')
    
    import pytz
    from datetime import datetime, date
    
    try:
        fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
        fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
    except Exception:
        flash('Formato de fecha inválido.', 'danger')
        return redirect(url_for('employee.mis_permisos'))
        
    hoy = datetime.now(pytz.timezone('America/Bogota')).date()
    
    if fecha_inicio < hoy:
        flash('No puedes solicitar permisos en fechas pasadas.', 'danger')
        return redirect(url_for('employee.mis_permisos'))
        
    if fecha_fin < fecha_inicio:
        flash('La fecha de fin no puede ser anterior a la de inicio.', 'danger')
        return redirect(url_for('employee.mis_permisos'))
        
    nuevo_permiso = LeaveRequest(
        user_id=current_user.id,
        tipo_permiso=tipo_permiso,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        motivo=motivo
    )
    db.session.add(nuevo_permiso)
    db.session.commit()
    
    from extensions import socketio
    socketio.emit('new_leave_request', {
        'empleado': current_user.nombre,
        'tipo': tipo_permiso
    }, room='admin_room')
    
    flash('Permiso solicitado exitosamente.', 'success')
    return redirect(url_for('employee.mis_permisos'))



