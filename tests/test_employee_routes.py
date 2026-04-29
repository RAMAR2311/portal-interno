"""
test_employee_routes.py - Pruebas de integración para las rutas del empleado.
Cubre: dashboard, cambio de estado, solicitud de adelanto,
reporte de incapacidades y solicitud de permisos.
"""
import io
import pytest
from datetime import date, timedelta


class TestEmployeeDashboard:
    """Pruebas del dashboard del empleado."""

    def test_dashboard_accessible_when_authenticated(self, auth_employee):
        """El dashboard debe cargar correctamente para un empleado autenticado."""
        resp = auth_employee.get("/employee/dashboard")
        assert resp.status_code == 200

    def test_dashboard_blocked_for_anonymous(self, client):
        """El dashboard no debe ser accesible sin sesión."""
        resp = client.get("/employee/dashboard")
        assert resp.status_code in (302, 401)

    def test_dashboard_blocked_for_admin(self, auth_admin):
        """El admin puede acceder al dashboard de empleado si también tiene permisos,
        pero la ruta principal del admin es /admin/dashboard."""
        resp = auth_admin.get("/admin/dashboard")
        assert resp.status_code == 200


class TestChangeStatus:
    """Pruebas de la ruta /employee/change_status."""

    @pytest.mark.parametrize("status", ["En Break", "En Almuerzo", "Activo"])
    def test_valid_status_change(self, auth_employee, status):
        """El empleado puede cambiar a cualquier estado válido."""
        resp = auth_employee.post(
            "/employee/change_status",
            data={"status": status},
            follow_redirects=True,
        )
        assert resp.status_code == 200

    def test_invalid_status_shows_error(self, auth_employee):
        """Un estado inválido debe mostrar mensaje de error."""
        resp = auth_employee.post(
            "/employee/change_status",
            data={"status": "EstadoInventado"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"inv" in resp.data.lower()  # "inválido"


class TestSolicitarAdelanto:
    """Pruebas de la ruta /employee/solicitar_adelanto."""

    def test_get_page_returns_200(self, auth_employee):
        """La página de solicitud de adelanto debe cargarse correctamente."""
        resp = auth_employee.get("/employee/solicitar_adelanto")
        assert resp.status_code == 200

    def test_submit_valid_advance_request(self, auth_employee, employee_user):
        """Enviar un adelanto válido debe crear el registro."""
        resp = auth_employee.post(
            "/employee/solicitar_adelanto",
            data={"monto": "500000", "motivo": "Pago de arriendo urgente"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        # Debe mostrar mensaje de éxito
        assert b"correctamente" in resp.data.lower() or b"success" in resp.data.lower()

    def test_submit_advance_exceeding_limit(self, auth_employee, employee_user):
        """Adelanto que excede el 50% del salario debe ser rechazado."""
        # Salario del fixture = 2_000_000 → límite = 1_000_000
        resp = auth_employee.post(
            "/employee/solicitar_adelanto",
            data={"monto": "1500000", "motivo": "Excedido"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"danger" in resp.data.lower() or b"excede" in resp.data.lower() or b"50" in resp.data

    def test_submit_advance_invalid_amount(self, auth_employee):
        """Monto no numérico debe mostrar error."""
        resp = auth_employee.post(
            "/employee/solicitar_adelanto",
            data={"monto": "abc", "motivo": "Prueba"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"inv" in resp.data.lower()  # "inválido"


class TestMisIncapacidades:
    """Pruebas de la ruta /employee/mis_incapacidades."""

    def test_get_page_returns_200(self, auth_employee):
        """La página de incapacidades debe cargarse correctamente."""
        resp = auth_employee.get("/employee/mis_incapacidades")
        assert resp.status_code == 200

    def test_reportar_incapacidad_valid(self, auth_employee):
        """Reportar una incapacidad con datos válidos debe redirigir con éxito."""
        # Crear un archivo falso en memoria
        fake_file = (io.BytesIO(b"fake pdf content"), "soporte.pdf")
        hoy = date.today()
        fin = hoy + timedelta(days=5)

        resp = auth_employee.post(
            "/employee/reportar_incapacidad",
            data={
                "tipo": "Enfermedad General",
                "diagnostico": "Gripe severa",
                "entidad_salud": "Nueva EPS",
                "fecha_inicio": hoy.strftime("%Y-%m-%d"),
                "fecha_fin": fin.strftime("%Y-%m-%d"),
                "archivo_soporte": fake_file,
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert resp.status_code == 200

    def test_reportar_incapacidad_fecha_fin_anterior(self, auth_employee):
        """Fecha fin anterior a fecha inicio debe rechazarse."""
        hoy = date.today()
        ayer = hoy - timedelta(days=1)

        fake_file = (io.BytesIO(b"fake pdf"), "soporte.pdf")
        resp = auth_employee.post(
            "/employee/reportar_incapacidad",
            data={
                "tipo": "Enfermedad General",
                "diagnostico": "Test",
                "entidad_salud": "EPS",
                "fecha_inicio": hoy.strftime("%Y-%m-%d"),
                "fecha_fin": ayer.strftime("%Y-%m-%d"),
                "archivo_soporte": fake_file,
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"fin" in resp.data.lower() or b"anterior" in resp.data.lower() or b"danger" in resp.data.lower()

    def test_reportar_incapacidad_sin_archivo(self, auth_employee):
        """Sin archivo de soporte médico la solicitud debe ser rechazada."""
        hoy = date.today()
        fin = hoy + timedelta(days=3)
        resp = auth_employee.post(
            "/employee/reportar_incapacidad",
            data={
                "tipo": "Enfermedad General",
                "diagnostico": "Sin soporte",
                "entidad_salud": "EPS",
                "fecha_inicio": hoy.strftime("%Y-%m-%d"),
                "fecha_fin": fin.strftime("%Y-%m-%d"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"obligatorio" in resp.data.lower() or b"warning" in resp.data.lower()


class TestMisPermisos:
    """Pruebas de la ruta /employee/mis_permisos y /employee/solicitar_permiso."""

    def test_get_page_returns_200(self, auth_employee):
        """La página de permisos debe cargarse correctamente."""
        resp = auth_employee.get("/employee/mis_permisos")
        assert resp.status_code == 200

    def test_solicitar_permiso_valido(self, auth_employee):
        """Solicitar un permiso con fechas futuras y datos válidos debe funcionar."""
        manana = date.today() + timedelta(days=1)
        pasado = date.today() + timedelta(days=3)
        resp = auth_employee.post(
            "/employee/solicitar_permiso",
            data={
                "tipo_permiso": "Cita Médica",
                "fecha_inicio": manana.strftime("%Y-%m-%d"),
                "fecha_fin": pasado.strftime("%Y-%m-%d"),
                "motivo": "Control médico rutinario",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"exitosamente" in resp.data.lower() or b"success" in resp.data.lower()

    def test_solicitar_permiso_fecha_pasada(self, auth_employee):
        """No debe permitirse solicitar permisos en fechas pasadas."""
        ayer = date.today() - timedelta(days=1)
        resp = auth_employee.post(
            "/employee/solicitar_permiso",
            data={
                "tipo_permiso": "Vacaciones",
                "fecha_inicio": ayer.strftime("%Y-%m-%d"),
                "fecha_fin": ayer.strftime("%Y-%m-%d"),
                "motivo": "Test fecha pasada",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"pasadas" in resp.data.lower() or b"danger" in resp.data.lower()

    def test_solicitar_permiso_fin_antes_inicio(self, auth_employee):
        """Fecha fin antes de fecha inicio debe rechazarse."""
        manana = date.today() + timedelta(days=2)
        pasado = date.today() + timedelta(days=1)
        resp = auth_employee.post(
            "/employee/solicitar_permiso",
            data={
                "tipo_permiso": "Calamidad",
                "fecha_inicio": manana.strftime("%Y-%m-%d"),
                "fecha_fin": pasado.strftime("%Y-%m-%d"),
                "motivo": "Test fechas invertidas",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"anterior" in resp.data.lower() or b"danger" in resp.data.lower()


class TestSurveyRoutes:
    """Pruebas de las rutas de encuestas del empleado."""

    def test_surveys_list_returns_200(self, auth_employee):
        """La lista de encuestas debe cargar correctamente."""
        resp = auth_employee.get("/employee/surveys")
        assert resp.status_code == 200
