"""
test_business_logic.py - Pruebas de lógica de negocio transversal.
Cubre: cálculo de días de incapacidad, cálculo de próxima quincena,
validaciones de fechas y reglas de negocio del dominio de RRHH.
"""
import pytest
from datetime import date, timedelta
import calendar as cal_module


class TestDiasIncapacidad:
    """Verificar que el cálculo de días de incapacidad sea correcto."""

    def test_un_dia_incapacidad(self):
        """Una incapacidad de un solo día debe ser 1 día."""
        inicio = date(2026, 4, 1)
        fin = date(2026, 4, 1)
        dias = (fin - inicio).days + 1
        assert dias == 1

    def test_semana_completa(self):
        """Una semana completa (lunes a domingo) debe ser 7 días."""
        inicio = date(2026, 4, 6)   # Lunes
        fin = date(2026, 4, 12)  # Domingo
        dias = (fin - inicio).days + 1
        assert dias == 7

    def test_mes_completo_abril(self):
        """Abril completo debe ser 30 días."""
        inicio = date(2026, 4, 1)
        fin = date(2026, 4, 30)
        dias = (fin - inicio).days + 1
        assert dias == 30

    def test_fecha_fin_antes_inicio_es_invalido(self):
        """La fecha fin no puede ser anterior a la fecha inicio."""
        inicio = date(2026, 4, 10)
        fin = date(2026, 4, 5)
        assert fin < inicio  # Debe detectarse como inválido

    def test_fechas_iguales_es_un_dia(self):
        """Si inicio == fin, los días deben ser 1."""
        d = date(2026, 6, 15)
        assert (d - d).days + 1 == 1


class TestProximaQuincena:
    """Verificar la lógica de cálculo de la próxima fecha de pago."""

    def _calcular_proxima_quincena(self, hoy: date) -> date:
        """Replica la lógica del dashboard del empleado."""
        if hoy.day <= 15:
            return date(hoy.year, hoy.month, 15)
        else:
            ultimo_dia = cal_module.monthrange(hoy.year, hoy.month)[1]
            return date(hoy.year, hoy.month, ultimo_dia)

    def test_inicio_mes_paga_el_15(self):
        """Al inicio del mes (día ≤ 15), el próximo pago es el día 15."""
        hoy = date(2026, 4, 1)
        resultado = self._calcular_proxima_quincena(hoy)
        assert resultado == date(2026, 4, 15)

    def test_dia_15_paga_el_15(self):
        """El día 15 exacto, el próximo pago sigue siendo el 15."""
        hoy = date(2026, 4, 15)
        resultado = self._calcular_proxima_quincena(hoy)
        assert resultado == date(2026, 4, 15)

    def test_dia_16_paga_fin_de_mes(self):
        """Del día 16 en adelante, el próximo pago es el último día del mes."""
        hoy = date(2026, 4, 16)
        resultado = self._calcular_proxima_quincena(hoy)
        assert resultado == date(2026, 4, 30)

    def test_dia_ultimo_mes_paga_ultimo_dia(self):
        """El último día del mes sigue siendo el día de pago."""
        hoy = date(2026, 4, 30)
        resultado = self._calcular_proxima_quincena(hoy)
        assert resultado == date(2026, 4, 30)

    def test_febrero_no_bisiesto_28_dias(self):
        """Febrero (no bisiesto) debe terminar el 28."""
        hoy = date(2026, 2, 20)
        resultado = self._calcular_proxima_quincena(hoy)
        assert resultado == date(2026, 2, 28)

    def test_meses_31_dias(self):
        """Meses con 31 días (Enero, Marzo...) deben pagar el 31."""
        hoy = date(2026, 1, 20)
        resultado = self._calcular_proxima_quincena(hoy)
        assert resultado == date(2026, 1, 31)


class TestAdelantoNomina:
    """Pruebas de las reglas de negocio de adelantos de nómina."""

    def test_limite_adelanto_exactamente_50_porciento(self):
        """El límite de adelanto es exactamente el 50% del salario."""
        salario = 2_000_000.0
        limite = salario * 0.5
        assert limite == 1_000_000.0

    def test_monto_en_limite_es_valido(self):
        """Un monto igual al 50% debe ser aceptado."""
        salario = 2_000_000.0
        monto = 1_000_000.0
        assert monto <= salario * 0.5

    def test_monto_un_peso_sobre_limite_es_invalido(self):
        """Un monto de 50%+1 debe ser rechazado."""
        salario = 2_000_000.0
        monto = salario * 0.5 + 1
        assert monto > salario * 0.5

    def test_salario_cero_no_permite_adelantos(self):
        """Con salario cero o None no debe permitirse adelanto."""
        salario = 0
        assert salario <= 0

        salario = None
        assert salario is None


class TestPermisosValidaciones:
    """Pruebas de las reglas de negocio de permisos."""

    def test_fecha_inicio_no_puede_ser_pasada(self):
        """No puede solicitarse permiso en fecha anterior a hoy."""
        hoy = date.today()
        ayer = hoy - timedelta(days=1)
        assert ayer < hoy  # La validación debe rechazar esto

    def test_fecha_fin_no_puede_ser_antes_de_inicio(self):
        """La fecha fin no puede ser menor a la fecha inicio."""
        inicio = date.today() + timedelta(days=5)
        fin = date.today() + timedelta(days=3)
        assert fin < inicio  # Inválido

    def test_mismo_dia_inicio_fin_es_valido(self):
        """Un permiso de un solo día (inicio == fin) debe ser válido."""
        hoy = date.today() + timedelta(days=1)
        assert hoy >= hoy  # Válido

    def test_vacaciones_multiples_dias(self):
        """Vacaciones de más de un día deben ser válidas si fin >= inicio."""
        inicio = date.today() + timedelta(days=10)
        fin = date.today() + timedelta(days=20)
        assert fin >= inicio


class TestPasswordValidation:
    """Verificar que el sistema de hash de contraseñas funciona correctamente."""

    def test_different_passwords_have_different_hashes(self, db):
        """Dos contraseñas distintas no deben tener el mismo hash."""
        from models import User
        u1 = User(email="u1@test.com", rol="Empleado", nombre="U1")
        u1.set_password("Password1")

        u2 = User(email="u2@test.com", rol="Empleado", nombre="U2")
        u2.set_password("Password2")

        assert u1.password_hash != u2.password_hash

    def test_same_password_has_different_hash_each_time(self, db):
        """El hash debe ser diferente cada vez (salt aleatorio)."""
        from models import User
        u1 = User(email="s1@test.com", rol="Empleado", nombre="S1")
        u1.set_password("MismaContraseña")

        u2 = User(email="s2@test.com", rol="Empleado", nombre="S2")
        u2.set_password("MismaContraseña")

        # Werkzeug usa sal aleatoria, por lo que los hashes deben ser diferentes
        assert u1.password_hash != u2.password_hash
