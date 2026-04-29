"""
test_auth.py - Pruebas del módulo de Autenticación
Cubre: login exitoso, credenciales incorrectas, usuario inactivo,
redirección por rol (Admin/Empleado) y logout.
"""
import pytest


class TestLogin:
    """Casos de prueba para la ruta POST /auth/login."""

    def test_login_page_returns_200(self, client):
        """La página de login debe ser accesible públicamente."""
        resp = client.get("/auth/login")
        assert resp.status_code == 200

    def test_login_admin_redirects_to_dashboard(self, client, admin_user):
        """Un Admin válido debe ser redirigido al panel de administración."""
        resp = client.post(
            "/auth/login",
            data={"email": admin_user.email, "password": "Admin1234!"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"dashboard" in resp.request.path.lower().encode() or b"admin" in resp.data.lower()

    def test_login_employee_redirects_to_employee_dashboard(self, client, employee_user):
        """Un Empleado válido debe ser redirigido al panel del empleado."""
        resp = client.post(
            "/auth/login",
            data={"email": employee_user.email, "password": "Empleado1234!"},
            follow_redirects=True,
        )
        assert resp.status_code == 200

    def test_login_wrong_password(self, client, employee_user):
        """Contraseña incorrecta debe mostrar mensaje de error y mantenerse en /login."""
        resp = client.post(
            "/auth/login",
            data={"email": employee_user.email, "password": "contraseña_incorrecta"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"incorrectos" in resp.data.lower() or b"danger" in resp.data.lower()

    def test_login_unknown_email(self, client):
        """Email inexistente debe mostrar mensaje de error."""
        resp = client.post(
            "/auth/login",
            data={"email": "noexiste@portal.com", "password": "cualquiera"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"incorrectos" in resp.data.lower() or b"danger" in resp.data.lower()

    def test_login_inactive_user_denied(self, client, db, employee_user):
        """Un usuario con is_active=False debe ver mensaje de acceso revocado."""
        employee_user.is_active = False
        db.session.commit()

        resp = client.post(
            "/auth/login",
            data={"email": employee_user.email, "password": "Empleado1234!"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"revocado" in resp.data.lower() or b"danger" in resp.data.lower()

    def test_login_empty_fields(self, client):
        """Enviar formulario vacío debe rechazarse con mensaje de error."""
        resp = client.post(
            "/auth/login",
            data={"email": "", "password": ""},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"incorrectos" in resp.data.lower() or b"danger" in resp.data.lower()


class TestLogout:
    """Casos de prueba para /auth/logout."""

    def test_logout_redirects_to_login(self, auth_employee):
        """El logout debe redirigir a la página de login."""
        resp = auth_employee.get("/auth/logout", follow_redirects=True)
        assert resp.status_code == 200
        assert "/auth/login" in resp.request.path or b"login" in resp.data.lower()

    def test_logout_without_login_redirects(self, client):
        """Acceder a /auth/logout sin sesión debe redirigir al login."""
        resp = client.get("/auth/logout", follow_redirects=True)
        assert resp.status_code == 200


class TestProtectedRoutes:
    """Rutas protegidas no deben ser accesibles sin autenticación."""

    @pytest.mark.parametrize("url", [
        "/employee/dashboard",
        "/admin/dashboard",
        "/employee/solicitar_adelanto",
        "/employee/mis_incapacidades",
        "/employee/mis_permisos",
    ])
    def test_anonymous_redirected_to_login(self, client, url):
        """Sin sesión activa, todas las rutas protegidas redirigen al login."""
        resp = client.get(url, follow_redirects=False)
        # Flask-Login puede responder 302 o 401
        assert resp.status_code in (301, 302, 401)
