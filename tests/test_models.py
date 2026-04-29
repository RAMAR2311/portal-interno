"""
test_models.py - Pruebas unitarias de los modelos de base de datos.
Cubre: hashing de contraseñas, creación de registros, restricciones
de unicidad y relaciones entre modelos.
"""
import pytest
from datetime import date
from models import (
    User, PayrollDoc, PayrollAdvance, Incapacidad,
    LeaveRequest, Survey, SurveyQuestion, SurveyOption,
    CalendarEvent, Message, Group,
)
from datetime import datetime


class TestUserModel:
    """Pruebas del modelo User."""

    def test_password_hashing_is_not_plain_text(self, db):
        """El hash nunca debe almacenar la contraseña en texto plano."""
        user = User(email="hash@test.com", rol="Empleado", nombre="Hash User")
        user.set_password("SuperSeguro123!")
        assert user.password_hash != "SuperSeguro123!"

    def test_check_password_correct(self, db):
        """check_password debe retornar True para la contraseña correcta."""
        user = User(email="check@test.com", rol="Empleado", nombre="Check User")
        user.set_password("MiClave789")
        assert user.check_password("MiClave789") is True

    def test_check_password_wrong(self, db):
        """check_password debe retornar False para contraseña incorrecta."""
        user = User(email="wrong@test.com", rol="Empleado", nombre="Wrong User")
        user.set_password("Original456")
        assert user.check_password("Incorrecta") is False

    def test_unique_email_constraint(self, db, employee_user):
        """No deben existir dos usuarios con el mismo email."""
        from sqlalchemy.exc import IntegrityError
        duplicado = User(email=employee_user.email, rol="Empleado", nombre="Duplicado")
        duplicado.set_password("Pass1234")
        db.session.add(duplicado)
        with pytest.raises(IntegrityError):
            db.session.commit()

    def test_user_default_status_is_inactive(self, db):
        """El estado por defecto de un usuario nuevo debe ser 'Inactivo'."""
        user = User(email="nuevo@test.com", rol="Empleado", nombre="Nuevo")
        user.set_password("Temp1234")
        db.session.add(user)
        db.session.commit()
        assert user.current_status == "Inactivo"

    def test_user_is_active_by_default(self, db):
        """Un usuario nuevo debe tener is_active=True por defecto."""
        user = User(email="activo@test.com", rol="Empleado", nombre="Activo")
        user.set_password("Temp1234")
        db.session.add(user)
        db.session.commit()
        assert user.is_active is True


class TestPayrollAdvanceModel:
    """Pruebas del modelo PayrollAdvance."""

    def test_create_advance_record(self, db, employee_user):
        """Debe poder crearse un adelanto de nómina correctamente."""
        adv = PayrollAdvance(
            user_id=employee_user.id,
            monto=500_000,
            motivo="Urgencia médica",
        )
        db.session.add(adv)
        db.session.commit()

        saved = PayrollAdvance.query.get(adv.id)
        assert saved is not None
        assert saved.estado == "Pendiente"
        assert float(saved.monto) == 500_000.0

    def test_advance_default_state_is_pending(self, db, employee_user):
        """El estado inicial de un adelanto debe ser 'Pendiente'."""
        adv = PayrollAdvance(
            user_id=employee_user.id, monto=100_000, motivo="Test"
        )
        db.session.add(adv)
        db.session.commit()
        assert adv.estado == "Pendiente"


class TestIncapacidadModel:
    """Pruebas del modelo Incapacidad."""

    def test_create_incapacidad(self, db, employee_user):
        """Debe guardarse una incapacidad con campos obligatorios."""
        inc = Incapacidad(
            user_id=employee_user.id,
            tipo="Enfermedad General",
            fecha_inicio=date(2026, 4, 1),
            fecha_fin=date(2026, 4, 5),
            dias_totales=5,
            archivo_soporte="soporte_test.pdf",
        )
        db.session.add(inc)
        db.session.commit()
        assert inc.id is not None
        assert inc.estado == "Pendiente"

    def test_dias_totales_calculation(self, db):
        """Verificar cálculo manual de días totales."""
        inicio = date(2026, 4, 1)
        fin = date(2026, 4, 10)
        dias = (fin - inicio).days + 1
        assert dias == 10


class TestLeaveRequestModel:
    """Pruebas del modelo LeaveRequest (permisos)."""

    def test_create_leave_request(self, db, employee_user):
        """Debe poder crearse una solicitud de permiso."""
        lr = LeaveRequest(
            user_id=employee_user.id,
            tipo_permiso="Vacaciones",
            fecha_inicio=date(2026, 5, 1),
            fecha_fin=date(2026, 5, 10),
            motivo="Descanso anual programado",
        )
        db.session.add(lr)
        db.session.commit()
        assert lr.id is not None
        assert lr.estado == "Pendiente"

    def test_leave_default_state_pending(self, db, employee_user):
        """El estado por defecto del permiso debe ser 'Pendiente'."""
        lr = LeaveRequest(
            user_id=employee_user.id,
            tipo_permiso="Cita Médica",
            fecha_inicio=date(2026, 6, 1),
            fecha_fin=date(2026, 6, 1),
            motivo="Control médico",
        )
        db.session.add(lr)
        db.session.commit()
        assert lr.estado == "Pendiente"


class TestSurveyModel:
    """Pruebas del modelo Survey y sus relaciones."""

    def test_create_survey_with_questions(self, db):
        """Debe poder crearse una encuesta con preguntas anidadas."""
        survey = Survey(titulo="Satisfacción Q1", descripcion="Encuesta trimestral")
        db.session.add(survey)
        db.session.flush()

        q = SurveyQuestion(
            survey_id=survey.id,
            texto_pregunta="¿Cómo califica el ambiente laboral?",
            tipo_respuesta="Calificacion",
        )
        db.session.add(q)
        db.session.commit()

        saved = Survey.query.get(survey.id)
        assert len(saved.questions) == 1
        assert saved.esta_activa is True

    def test_survey_cascade_delete_questions(self, db):
        """Eliminar una encuesta debe eliminar sus preguntas en cascada."""
        survey = Survey(titulo="Para Borrar", descripcion="")
        db.session.add(survey)
        db.session.flush()

        q = SurveyQuestion(
            survey_id=survey.id,
            texto_pregunta="Pregunta temporal",
            tipo_respuesta="Texto",
        )
        db.session.add(q)
        db.session.commit()
        q_id = q.id

        db.session.delete(survey)
        db.session.commit()

        assert SurveyQuestion.query.get(q_id) is None


class TestMessageModel:
    """Pruebas del modelo Message."""

    def test_create_direct_message(self, db, admin_user, employee_user):
        """Debe poder enviarse un mensaje directo entre usuarios."""
        msg = Message(
            sender_id=admin_user.id,
            recipient_id=employee_user.id,
            content="Hola, este es un mensaje de prueba.",
        )
        db.session.add(msg)
        db.session.commit()
        assert msg.id is not None
        assert msg.is_read is False

    def test_message_is_unread_by_default(self, db, admin_user, employee_user):
        """Un mensaje nuevo debe estar marcado como no leído."""
        msg = Message(
            sender_id=employee_user.id,
            recipient_id=admin_user.id,
            content="Consulta urgente.",
        )
        db.session.add(msg)
        db.session.commit()
        assert msg.is_read is False
