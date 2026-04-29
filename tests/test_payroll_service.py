"""
test_payroll_service.py - Pruebas del servicio de nómina (PayrollService).
Cubre: cálculo de devengado/deducido/neto, validaciones de adelantos,
aprobación/rechazo de adelantos y casos límite.
"""
import pytest
from services.payroll_service import PayrollService
from models import PayrollAdvance


class TestCalculateNetPay:
    """Pruebas unitarias de PayrollService.calculate_net_pay."""

    def test_basic_calculation_no_discounts(self):
        """Sin descuentos, el neto debe ser igual al devengado."""
        dev, ded, neto = PayrollService.calculate_net_pay(
            salario_base=2_000_000,
            auxilio_transporte=162_000,
            bonificaciones=0,
            valor_descuento_dias=0,
            aporte_salud=0,
            aporte_pension=0,
            otros_descuentos=0,
        )
        assert dev == 2_162_000
        assert ded == 0
        assert neto == 2_162_000

    def test_calculation_with_all_discounts(self):
        """Cálculo completo con todos los descuentos."""
        dev, ded, neto = PayrollService.calculate_net_pay(
            salario_base=3_000_000,
            auxilio_transporte=162_000,
            bonificaciones=200_000,
            valor_descuento_dias=100_000,
            aporte_salud=120_000,  # 4 %
            aporte_pension=120_000,  # 4 %
            otros_descuentos=50_000,
        )
        expected_dev = 3_000_000 + 162_000 + 200_000  # 3_362_000
        expected_ded = 100_000 + 120_000 + 120_000 + 50_000  # 390_000
        expected_neto = expected_dev - expected_ded  # 2_972_000

        assert dev == pytest.approx(expected_dev)
        assert ded == pytest.approx(expected_ded)
        assert neto == pytest.approx(expected_neto)

    def test_neto_cannot_be_negative_structurally(self):
        """Con descuentos mayores al devengado el neto resulta negativo (caso edge)."""
        dev, ded, neto = PayrollService.calculate_net_pay(
            salario_base=1_000_000,
            auxilio_transporte=0,
            bonificaciones=0,
            valor_descuento_dias=500_000,
            aporte_salud=300_000,
            aporte_pension=300_000,
            otros_descuentos=0,
        )
        # El sistema no bloquea esto; la validación es responsabilidad del admin
        assert neto < 0

    def test_returns_three_values(self):
        """La función siempre debe retornar exactamente 3 valores."""
        result = PayrollService.calculate_net_pay(
            1_000_000, 100_000, 0, 0, 40_000, 40_000, 0
        )
        assert len(result) == 3

    def test_zero_salary(self):
        """Salario base cero con otros valores en cero produce neto cero."""
        dev, ded, neto = PayrollService.calculate_net_pay(0, 0, 0, 0, 0, 0, 0)
        assert dev == 0
        assert ded == 0
        assert neto == 0

    def test_bonificaciones_included_in_devengado(self):
        """Las bonificaciones deben aumentar el total devengado."""
        dev_sin, _, _ = PayrollService.calculate_net_pay(2_000_000, 0, 0, 0, 0, 0, 0)
        dev_con, _, _ = PayrollService.calculate_net_pay(2_000_000, 0, 500_000, 0, 0, 0, 0)
        assert dev_con - dev_sin == pytest.approx(500_000)


class TestRequestAdvance:
    """Pruebas de PayrollService.request_advance."""

    def test_request_advance_success(self, db, employee_user):
        """Un empleado con salario puede solicitar adelanto dentro del 50%."""
        ok, msg = PayrollService.request_advance(
            employee_user.id, monto=500_000, motivo="Emergencia"
        )
        assert ok is True
        assert "correctamente" in msg.lower()

    def test_request_advance_exceeds_50_percent(self, db, employee_user):
        """Adelanto mayor al 50% del salario debe ser rechazado."""
        # Salario del empleado = 2_000_000 → límite = 1_000_000
        ok, msg = PayrollService.request_advance(
            employee_user.id, monto=1_500_000, motivo="Excedido"
        )
        assert ok is False
        assert "50%" in msg or "excede" in msg.lower()

    def test_request_advance_no_salary(self, db):
        """Un empleado sin salario registrado debe ser rechazado."""
        from models import User
        sin_salario = User(
            email="sinsalario@test.com", rol="Empleado",
            nombre="Sin Salario", salario=None, is_active=True
        )
        sin_salario.set_password("Pass1234")
        db.session.add(sin_salario)
        db.session.commit()

        ok, msg = PayrollService.request_advance(sin_salario.id, 100_000, "Test")
        assert ok is False
        assert "salario" in msg.lower()

    def test_request_advance_duplicate_pending(self, db, employee_user):
        """No debe permitirse una segunda solicitud si ya hay una pendiente."""
        PayrollService.request_advance(employee_user.id, 200_000, "Primera")
        ok, msg = PayrollService.request_advance(employee_user.id, 100_000, "Segunda")
        assert ok is False
        assert "pendiente" in msg.lower()

    def test_request_advance_nonexistent_user(self, db):
        """Solicitar adelanto para un ID inexistente debe fallar."""
        ok, msg = PayrollService.request_advance(99999, 100_000, "No existe")
        assert ok is False
        assert "usuario" in msg.lower() or "encontrado" in msg.lower()


class TestProcessAdvance:
    """Pruebas de PayrollService.process_advance."""

    def test_approve_advance(self, db, employee_user, admin_user):
        """Un admin puede aprobar una solicitud pendiente."""
        adv = PayrollAdvance(
            user_id=employee_user.id, monto=300_000, motivo="Test"
        )
        db.session.add(adv)
        db.session.commit()

        ok, msg = PayrollService.process_advance(adv.id, admin_user.id, "aprobar")
        assert ok is True
        updated = PayrollAdvance.query.get(adv.id)
        assert updated.estado == "Aprobado"
        assert updated.revisado_por == admin_user.id

    def test_reject_advance(self, db, employee_user, admin_user):
        """Un admin puede rechazar una solicitud pendiente."""
        adv = PayrollAdvance(
            user_id=employee_user.id, monto=300_000, motivo="Test"
        )
        db.session.add(adv)
        db.session.commit()

        ok, msg = PayrollService.process_advance(adv.id, admin_user.id, "rechazar")
        assert ok is True
        updated = PayrollAdvance.query.get(adv.id)
        assert updated.estado == "Rechazado"

    def test_cannot_process_already_approved(self, db, employee_user, admin_user):
        """No debe procesarse una solicitud que ya fue aprobada."""
        adv = PayrollAdvance(
            user_id=employee_user.id, monto=300_000, motivo="Test",
            estado="Aprobado"
        )
        db.session.add(adv)
        db.session.commit()

        ok, msg = PayrollService.process_advance(adv.id, admin_user.id, "rechazar")
        assert ok is False
        assert "procesada" in msg.lower() or "aprobado" in msg.lower()

    def test_invalid_action_rejected(self, db, employee_user, admin_user):
        """Una acción inválida (no 'aprobar'/'rechazar') debe fallar."""
        adv = PayrollAdvance(
            user_id=employee_user.id, monto=200_000, motivo="Test"
        )
        db.session.add(adv)
        db.session.commit()

        ok, msg = PayrollService.process_advance(adv.id, admin_user.id, "eliminar")
        assert ok is False
        assert "inválida" in msg.lower() or "invalida" in msg.lower()

    def test_process_nonexistent_advance(self, db, admin_user):
        """Procesar un ID de adelanto inexistente debe fallar."""
        ok, msg = PayrollService.process_advance(99999, admin_user.id, "aprobar")
        assert ok is False
        assert "encontrada" in msg.lower() or "no encontrado" in msg.lower()
