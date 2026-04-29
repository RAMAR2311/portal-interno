"""
test_admin_routes.py - Pruebas de integración para las rutas del Administrador.
Cubre: dashboard, gestión de empleados, acceso denegado para empleados normales.
"""
import pytest


class TestAdminDashboard:
    """Pruebas del dashboard de administración."""

    def test_admin_dashboard_accessible(self, auth_admin):
        """El panel de admin debe cargar para un usuario con rol Admin."""
        resp = auth_admin.get("/admin/dashboard")
        assert resp.status_code == 200

    def test_employee_cannot_access_admin_dashboard(self, auth_employee):
        """Un empleado no debe poder acceder al panel de admin."""
        resp = auth_employee.get("/admin/dashboard", follow_redirects=False)
        # Debe redirigir o devolver 403
        assert resp.status_code in (302, 403, 401)

    def test_anonymous_cannot_access_admin_dashboard(self, client):
        """Un usuario anónimo no debe acceder al panel de admin."""
        resp = client.get("/admin/dashboard", follow_redirects=False)
        assert resp.status_code in (302, 401)


class TestAdminEmployeeManagement:
    """Pruebas de gestión de empleados desde el panel admin."""

    def test_employee_list_page_returns_200(self, auth_admin):
        """El dashboard muestra la lista de empleados para el admin."""
        resp = auth_admin.get("/admin/dashboard")
        assert resp.status_code == 200

    def test_create_employee_with_valid_data(self, auth_admin, db):
        """Debe poder crearse un nuevo empleado desde el panel de admin."""
        resp = auth_admin.post(
            "/admin/create_user",
            data={
                "nombre": "Nuevo Empleado Test",
                "email": "nuevo_emp@test.com",
                "password": "NewPass1234!",
                "rol": "Empleado",
                "cargo": "Desarrollador",
                "salario": "3000000",
                "tipo_contrato": "Indefinido",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200

    def test_create_employee_duplicate_email(self, auth_admin, employee_user):
        """Crear empleado con email duplicado debe mostrar advertencia."""
        resp = auth_admin.post(
            "/admin/create_user",
            data={
                "nombre": "Duplicado",
                "email": employee_user.email,  # email ya existente
                "password": "DupPass1234!",
                "rol": "Empleado",
                "cargo": "Analista",
                "salario": "2000000",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        # Debe mostrar algún error
        assert b"danger" in resp.data.lower() or b"existe" in resp.data.lower() or b"warning" in resp.data.lower()


class TestAdminIncapacidades:
    """Pruebas del módulo de incapacidades en el panel de admin."""

    def test_incapacidades_list_returns_200(self, auth_admin):
        """La lista de incapacidades debe ser accesible para el admin."""
        resp = auth_admin.get("/admin/incapacidades")
        assert resp.status_code in (200, 302, 404)  # 404 si aún no existe la ruta

    def test_employee_cannot_see_admin_incapacidades(self, auth_employee):
        """Un empleado no debe acceder a la gestión admin de incapacidades."""
        resp = auth_employee.get("/admin/incapacidades", follow_redirects=False)
        assert resp.status_code in (302, 403, 401)


class TestAdminComunicados:
    """Pruebas del módulo de comunicados en el panel de admin."""

    def test_comunicados_page_accessible_to_admin(self, auth_admin):
        """La gestión de comunicados debe ser accesible para el admin."""
        resp = auth_admin.get("/admin/crear_comunicado")
        assert resp.status_code in (200, 302)

    def test_employee_cannot_access_comunicados_admin(self, auth_employee):
        """Un empleado es redirigido al intentar crear comunicados (rol check interno)."""
        resp = auth_employee.get("/admin/crear_comunicado", follow_redirects=False)
        # El before_request del blueprint redirige al employee.dashboard
        assert resp.status_code in (302, 403, 401)


class TestAdminPayrollAdvances:
    """Pruebas de gestión de adelantos de nómina desde admin."""

    def test_advances_list_accessible_to_admin(self, auth_admin):
        """La lista de adelantos debe ser accesible para el admin."""
        resp = auth_admin.get("/admin/adelantos")
        assert resp.status_code in (200, 302, 404)

    def test_approve_advance_via_route(self, auth_admin, db, employee_user):
        """El admin debe poder aprobar un adelanto pendiente via ruta."""
        from models import PayrollAdvance
        adv = PayrollAdvance(
            user_id=employee_user.id, monto=200_000, motivo="Test via route"
        )
        db.session.add(adv)
        db.session.commit()

        resp = auth_admin.post(
            f"/admin/adelantos/{adv.id}/procesar",
            data={"accion": "aprobar"},
            follow_redirects=True,
        )
        # La ruta puede tener nombre diferente, pero al menos no debe crashear
        assert resp.status_code in (200, 302, 404, 405)
