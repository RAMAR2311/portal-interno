import os
from flask import Blueprint, render_template, make_response, current_app, send_from_directory, flash, request, redirect, url_for
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
    comunicados = Comunicado.query.order_by(Comunicado.fecha_publicacion.desc()).all()
    
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



    return render_template('employee/dashboard.html', 
                           payrolls=payrolls, 
                           comunicados=comunicados,
                           hours_worked=hours_worked_str,
                           next_payment=next_payment_str,
                           last_notif=last_comunicado_title,
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
    if doc.user_id != current_user.id:
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

