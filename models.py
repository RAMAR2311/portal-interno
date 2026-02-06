from datetime import datetime
import pytz
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def get_bogota_time():
    bogota_tz = pytz.timezone('America/Bogota')
    return datetime.now(bogota_tz)

class User(UserMixin, db.Model):
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
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=get_bogota_time)
    
    # Relationships
    members = db.relationship('User', secondary=group_members, lazy='subquery',
        backref=db.backref('groups', lazy=True))

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=True) # New field for Group Chat
    
    content = db.Column(db.Text, nullable=True)
    filename = db.Column(db.String(255), nullable=True) # For attached files
    timestamp = db.Column(db.DateTime, index=True, default=get_bogota_time)
    is_read = db.Column(db.Boolean, default=False)


class PayrollDoc(db.Model):
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
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    contenido = db.Column(db.Text, nullable=False)
    archivo = db.Column(db.String(255), nullable=True) # Filename of PDF if any
    fecha_publicacion = db.Column(db.DateTime, default=get_bogota_time)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationship to know who posted it
    author = db.relationship('User', backref='comunicados', lazy=True)

# Association table for Event Attendees
event_attendees = db.Table('event_attendees',
    db.Column('event_id', db.Integer, db.ForeignKey('calendar_event.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

class CalendarEvent(db.Model):
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

