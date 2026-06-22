from datetime import datetime
import pytz
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def get_bogota_time():
    bogota_tz = pytz.timezone('America/Bogota')
    return datetime.now(bogota_tz).replace(tzinfo=None)

class User(UserMixin, db.Model):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(512))
    rol = db.Column(db.String(20), nullable=False)  # 'Admin', 'Empleado'
    nombre = db.Column(db.String(100), nullable=False)
    cargo = db.Column(db.String(100))
    fecha_ingreso = db.Column(db.Date)
    salario = db.Column(db.Float)
    tipo_contrato = db.Column(db.String(50))
    telefono = db.Column(db.String(20))
    
    # New Fields
    # Profile Picture
    foto_perfil = db.Column(db.String(255), nullable=True) # Filename
    
    # Social Security
    eps = db.Column(db.String(100))
    arl = db.Column(db.String(100))
    caja_compensacion = db.Column(db.String(100))
    fondo_pensiones = db.Column(db.String(100))
    cesantias = db.Column(db.String(100))
    
    # Bank Info
    entidad_bancaria = db.Column(db.String(100))
    numero_cuenta = db.Column(db.String(50))
    
    # Personal Data
    direccion = db.Column(db.String(255))
    tipo_sangre = db.Column(db.String(10))
    current_status = db.Column(db.String(20), default='Inactivo') # Activo, Inactivo, En Break, En Almuerzo
    is_active = db.Column(db.Boolean, default=True) # Reemplaza el uso erróneo de current_status para desactivar empleados
    
    # Relationships
    messages_sent = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy=True)
    messages_received = db.relationship('Message', foreign_keys='Message.recipient_id', backref='recipient', lazy=True)
    payrolls = db.relationship('PayrollDoc', backref='employee', lazy=True)
    time_logs = db.relationship('TimeLog', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Training(db.Model):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(20)) # 'video' or 'document'
    created_at = db.Column(db.DateTime, default=get_bogota_time)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationship
    uploader = db.relationship('User', backref='uploads', lazy=True)


class TimeLog(db.Model):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    new_status = db.Column(db.String(20), nullable=False)
    timestamp = db.Column(db.DateTime, default=get_bogota_time)

# Association table for Group Members
group_members = db.Table('group_members',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('group_id', db.Integer, db.ForeignKey('group.id'), primary_key=True)
)

class Group(db.Model):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=get_bogota_time)
    
    # Relationships
    members = db.relationship('User', secondary=group_members, lazy='subquery',
        backref=db.backref('groups', lazy=True))

class Message(db.Model):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=True) # New field for Group Chat
    
    content = db.Column(db.Text, nullable=True)
    filename = db.Column(db.String(255), nullable=True) # For attached files
    timestamp = db.Column(db.DateTime, index=True, default=get_bogota_time)
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime, nullable=True)


class PayrollDoc(db.Model):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    mes = db.Column(db.String(20), nullable=False)
    anio = db.Column(db.Integer, nullable=False)
    periodo = db.Column(db.String(20), nullable=False, default='Mensual') # 'Primera Quincena', 'Segunda Quincena'
    filename = db.Column(db.String(255), nullable=False) # Path to PDF
    created_at = db.Column(db.DateTime, default=get_bogota_time)
    
    # Financial Data
    salario_base = db.Column(db.Float, default=0.0)
    auxilio_transporte = db.Column(db.Float, default=0.0)
    bonificaciones = db.Column(db.Float, default=0.0)
    dias_injustificados = db.Column(db.Integer, default=0)
    valor_descuento_dias = db.Column(db.Float, default=0.0)
    aporte_salud = db.Column(db.Float, default=0.0)
    aporte_pension = db.Column(db.Float, default=0.0)
    otros_descuentos = db.Column(db.Float, default=0.0)
    neto_pagar = db.Column(db.Float, default=0.0)

class Comunicado(db.Model):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    contenido = db.Column(db.Text, nullable=False)
    archivo = db.Column(db.String(255), nullable=True) # Filename of PDF if any
    fecha_publicacion = db.Column(db.DateTime, default=get_bogota_time)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Relationship to know who posted it
    author = db.relationship('User', foreign_keys=[user_id], backref='comunicados', lazy=True)
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='comunicados_recibidos', lazy=True)

# Association table for Event Attendees
event_attendees = db.Table('event_attendees',
    db.Column('event_id', db.Integer, db.ForeignKey('calendar_event.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

class CalendarEvent(db.Model):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    start = db.Column(db.DateTime, nullable=False, index=True)
    end = db.Column(db.DateTime, nullable=False, index=True)
    type = db.Column(db.String(50), nullable=False) # 'Reunión', 'Ocupado', 'Fuera de Oficina', 'Recordatorio'
    description = db.Column(db.Text, nullable=True)
    is_private = db.Column(db.Boolean, default=False)
    
    # Relationship
    user = db.relationship('User', backref='events', lazy=True)
    attendees = db.relationship('User', secondary=event_attendees, lazy='subquery',
        backref=db.backref('attending_events', lazy=True))

class PayrollAdvance(db.Model):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    monto = db.Column(db.Numeric(12, 2), nullable=False)
    motivo = db.Column(db.Text, nullable=False)
    fecha_solicitud = db.Column(db.DateTime, default=get_bogota_time)
    estado = db.Column(db.String(20), default='Pendiente') # 'Pendiente', 'Aprobado', 'Rechazado'
    fecha_revision = db.Column(db.DateTime, nullable=True)
    revisado_por = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    # Note: Explicit foreign keys mapped to prevent AmbiguousForeignKeyError
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('payroll_advances', lazy=True))
    admin_reviewer = db.relationship('User', foreign_keys=[revisado_por], lazy=True)


class Survey(db.Model):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    creado_en = db.Column(db.DateTime, default=get_bogota_time)
    esta_activa = db.Column(db.Boolean, default=True)

    questions = db.relationship('SurveyQuestion', backref='survey', lazy=True, cascade='all, delete-orphan')
    responses = db.relationship('SurveyResponse', backref='survey', lazy=True, cascade='all, delete-orphan')

class SurveyQuestion(db.Model):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey('survey.id'), nullable=False)
    texto_pregunta = db.Column(db.String(500), nullable=False)
    tipo_respuesta = db.Column(db.String(50), nullable=False) # 'Texto', 'Opcion Multiple', 'Calificacion'

    options = db.relationship('SurveyOption', backref='question', lazy=True, cascade='all, delete-orphan')

class SurveyOption(db.Model):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('survey_question.id'), nullable=False)
    texto_opcion = db.Column(db.String(200), nullable=False)

class SurveyResponse(db.Model):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey('survey.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    respondido_en = db.Column(db.DateTime, default=get_bogota_time)

    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('survey_responses', lazy=True))
    answers = db.relationship('SurveyAnswer', backref='response', lazy=True, cascade='all, delete-orphan')

class SurveyAnswer(db.Model):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    id = db.Column(db.Integer, primary_key=True)
    response_id = db.Column(db.Integer, db.ForeignKey('survey_response.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('survey_question.id'), nullable=False)
    respuesta_texto = db.Column(db.Text, nullable=True)

    question = db.relationship('SurveyQuestion', foreign_keys=[question_id])

class ActivePause(db.Model):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    url_video = db.Column(db.String(255), nullable=True)
    duracion_minutos = db.Column(db.Integer, nullable=False, default=5)
    creado_en = db.Column(db.DateTime, default=get_bogota_time)

class PauseAssignment(db.Model):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    id = db.Column(db.Integer, primary_key=True)
    pause_id = db.Column(db.Integer, db.ForeignKey('active_pause.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    programado_para = db.Column(db.DateTime, nullable=True)
    completado = db.Column(db.Boolean, default=False)
    fecha_completado = db.Column(db.DateTime, nullable=True)

    # Relationships
    pause = db.relationship('ActivePause', backref='assignments', lazy=True)
    user = db.relationship('User', foreign_keys=[user_id], backref='pauses_assigned', lazy=True)

class Incapacidad(db.Model):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tipo = db.Column(db.String(50), nullable=False) # Enfermedad General, Accidente Laboral, Licencia
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date, nullable=False)
    dias_totales = db.Column(db.Integer, nullable=False)
    diagnostico = db.Column(db.String(255), nullable=True)
    entidad_salud = db.Column(db.String(100), nullable=True) # EPS o ARL
    archivo_soporte = db.Column(db.String(255), nullable=False)
    fecha_reporte = db.Column(db.DateTime, default=get_bogota_time)
    estado = db.Column(db.String(20), default='Pendiente') # Pendiente, Validada, Rechazada
    comentarios_admin = db.Column(db.Text, nullable=True)
    
    # Relationship
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('incapacidades', lazy=True))

class WeeklySchedule(db.Model):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    dia_semana = db.Column(db.Integer, nullable=False) # 0=Lunes, 1=Martes... 6=Domingo
    hora_entrada = db.Column(db.Time, nullable=True)
    hora_salida = db.Column(db.Time, nullable=True)
    es_dia_laboral = db.Column(db.Boolean, default=True)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'dia_semana', name='uq_user_dia_semana'),
    )

class LeaveRequest(db.Model):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tipo_permiso = db.Column(db.String(50), nullable=False) # Vacaciones, Cita Médica, Calamidad, Otro
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date, nullable=False)
    motivo = db.Column(db.Text, nullable=False)
    estado = db.Column(db.String(20), default='Pendiente') # Pendiente, Aprobado, Rechazado
    fecha_solicitud = db.Column(db.DateTime, default=get_bogota_time)
    aprobado_por = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('leave_requests', lazy=True))
    aprobador = db.relationship('User', foreign_keys=[aprobado_por])



