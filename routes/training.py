import os
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import db, Training

training_bp = Blueprint('training', __name__)

ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi', 'pdf', 'pptx', 'ppt', 'doc', 'docx'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_type(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    if ext in ['mp4', 'mov', 'avi']:
        return 'video'
    return 'document'

@training_bp.route('/')
@login_required
def index():
    trainings = Training.query.order_by(Training.created_at.desc()).all()
    return render_template('training/index.html', trainings=trainings)

@training_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    # Admin Check
    if current_user.rol != 'Admin':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('training.index'))

    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No se seleccionó ningún archivo', 'danger')
            return redirect(request.url)
            
        file = request.files['file']
        title = request.form.get('title')
        description = request.form.get('description')

        if file.filename == '':
            flash('No se seleccionó ningún archivo', 'danger')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Add timestamp to filename to prevent duplicates
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_")
            filename = timestamp + filename
            
            # Ensure directory exists
            upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'trainings')
            os.makedirs(upload_dir, exist_ok=True)
            
            file.save(os.path.join(upload_dir, filename))
            
            file_type = get_file_type(filename)
            
            new_training = Training(
                title=title,
                description=description,
                filename=filename,
                file_type=file_type,
                user_id=current_user.id
            )
            
            db.session.add(new_training)
            db.session.commit()
            
            flash('Capacitación subida exitosamente.', 'success')
            return redirect(url_for('training.index'))
        else:
            flash('Tipo de archivo no permitido', 'danger')

    return render_template('training/upload.html')

@training_bp.route('/view/<int:id>')
@login_required
def view(id):
    training = Training.query.get_or_404(id)
    return render_template('training/view.html', training=training)

@training_bp.route('/download/<int:id>')
@login_required
def download(id):
    training = Training.query.get_or_404(id)
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'trainings')
    return send_from_directory(upload_dir, training.filename, as_attachment=True)
