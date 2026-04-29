"""
conftest.py - Configuración global de pytest para el Portal Interno
Provee fixtures reutilizables para todos los módulos de prueba.
"""
import pytest
from app import create_app
from models import db as _db, User, PayrollAdvance, Incapacidad, LeaveRequest, Survey, SurveyQuestion


# ──────────────────────────────────────────────
# Config de prueba: SQLite en memoria, sin CSRF
# ──────────────────────────────────────────────
class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = "test-secret-key"
    WTF_CSRF_ENABLED = False
    LOGIN_DISABLED = False
    UPLOAD_FOLDER = "/tmp/test_uploads"
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    SERVER_NAME = None


@pytest.fixture(scope="session")
def app():
    """Instancia de Flask configurada para pruebas (sesión completa)."""
    _app = create_app(TestConfig)
    with _app.app_context():
        _db.create_all()
        yield _app
        _db.drop_all()


@pytest.fixture(scope="function")
def db(app):
    """Base de datos limpia para cada función de prueba."""
    with app.app_context():
        yield _db
        _db.session.rollback()
        # Limpiar tablas relevantes sin recrear el esquema
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()


@pytest.fixture()
def client(app):
    """Cliente HTTP de prueba."""
    return app.test_client()


# ──────────────────────────────────────────────
# Fixtures de usuarios
# ──────────────────────────────────────────────
@pytest.fixture()
def admin_user(db):
    """Crea un usuario Administrador en la BD."""
    user = User(
        email="admin@test.com",
        rol="Admin",
        nombre="Admin Test",
        cargo="Administrador del Sistema",
        salario=5_000_000.0,
        is_active=True,
    )
    user.set_password("Admin1234!")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture()
def employee_user(db):
    """Crea un usuario Empleado en la BD."""
    user = User(
        email="empleado@test.com",
        rol="Empleado",
        nombre="Empleado Test",
        cargo="Analista",
        salario=2_000_000.0,
        is_active=True,
    )
    user.set_password("Empleado1234!")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture()
def auth_admin(client, admin_user):
    """Cliente con sesión de Admin activa."""
    client.post(
        "/auth/login",
        data={"email": admin_user.email, "password": "Admin1234!"},
        follow_redirects=True,
    )
    return client


@pytest.fixture()
def auth_employee(client, employee_user):
    """Cliente con sesión de Empleado activa."""
    client.post(
        "/auth/login",
        data={"email": employee_user.email, "password": "Empleado1234!"},
        follow_redirects=True,
    )
    return client
