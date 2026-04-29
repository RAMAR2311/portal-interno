from io import BytesIO
from datetime import datetime
import pytz
from flask import render_template, current_app
from xhtml2pdf import pisa
from models import db, PayrollDoc, User, PayrollAdvance
from werkzeug.utils import secure_filename
import os

class PayrollService:
    @staticmethod
    def calculate_net_pay(
        salario_base: float,
        auxilio_transporte: float,
        bonificaciones: float,
        valor_descuento_dias: float,
        aporte_salud: float,
        aporte_pension: float,
        otros_descuentos: float
    ) -> tuple[float, float, float]:
        """
        Calcula el total devengado, total deducido y neto a pagar.
        Returns: (total_devengado, total_deducido, neto_pagar)
        """
        total_devengado = salario_base + auxilio_transporte + bonificaciones
        total_deducido = valor_descuento_dias + aporte_salud + aporte_pension + otros_descuentos
        neto_pagar = total_devengado - total_deducido
        return total_devengado, total_deducido, neto_pagar

    @staticmethod
    def generate_payroll_pdf(context: dict) -> bytes | None:
        """
        Genera el PDF de la nómina usando xhtml2pdf.
        """
        # Estilos específicos para xhtml2pdf (movidos aquí para limpiar el linter del IDE)
        pdf_styles = """
        <style>
        @page {
            size: letter;
            margin: 2cm;
            @frame footer_frame {
                -pdf-frame-content: footerContent;
                bottom: 1cm;
                margin-left: 2cm;
                margin-right: 2cm;
                height: 1cm;
            }
        }
        </style>
        """
        context['pdf_styles'] = pdf_styles
        html_content = render_template('admin/pdf_template.html', **context)
        
        pdf = BytesIO()
        pisa_status = pisa.CreatePDF(BytesIO(html_content.encode('utf-8')), dest=pdf)
        
        if pisa_status.err:
            return None
        return pdf.getvalue()

    @staticmethod
    def create_payroll_record(
        user_id: int,
        mes: str,
        anio: int,
        periodo: str,
        financial_data: dict,
        bonus_details: dict = None
    ) -> bool:
        """
        Crea el registro de nómina en la base de datos y guarda el archivo PDF.
        """
        user = User.query.get(user_id)
        if not user:
            return False

        # Calculate totals
        total_devengado, total_deducido, neto_pagar = PayrollService.calculate_net_pay(
            financial_data['salario_base'],
            financial_data['auxilio_transporte'],
            financial_data['bonificaciones'],
            financial_data['valor_descuento_dias'],
            financial_data['aporte_salud'],
            financial_data['aporte_pension'],
            financial_data['otros_descuentos']
        )

        # Prepare context for PDF
        context = {
            'user': user,
            'mes': mes,
            'anio': anio,
            'periodo': periodo,
            **financial_data,
            'total_devengado': total_devengado,
            'total_deducido': total_deducido,
            'neto_pagar': neto_pagar,
            'generated_at': datetime.now(pytz.timezone('America/Bogota'))
        }

        # Add bonus details
        if bonus_details:
            context.update(bonus_details)
        else:
            context.update({'bono_contratos': 0.0, 'bono_diagnosticos': 0.0, 'bonificaciones_adicionales': financial_data.get('bonificaciones', 0.0)})

        # Generate PDF
        pdf_content = PayrollService.generate_payroll_pdf(context)
        if not pdf_content:
            return False

        # Save PDF File
        periodo_slug = "Q1" if periodo == "Primera Quincena" else "Q2"
        filename = secure_filename(f"payroll_{user_id}_{mes}_{periodo_slug}_{anio}_{int(datetime.now().timestamp())}.pdf")
        save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'payrolls')
        os.makedirs(save_path, exist_ok=True)
        
        with open(os.path.join(save_path, filename), 'wb') as f:
            f.write(pdf_content)

        # Save to DB
        new_payroll = PayrollDoc(
            user_id=user_id,
            mes=mes,
            anio=anio,
            periodo=periodo,
            filename=filename,
            **financial_data,
            neto_pagar=neto_pagar
        )
        db.session.add(new_payroll)
        db.session.commit()
        
        return True

    @staticmethod
    def request_advance(user_id: int, monto: float, motivo: str) -> tuple[bool, str]:
        user = User.query.get(user_id)
        if not user:
            return False, "Usuario no encontrado."
            
        if user.salario is None or user.salario <= 0:
            return False, "Usuario no tiene salario base registrado."
            
        if monto > (user.salario * 0.5):
            return False, "El monto excede el 50% de su salario base."
            
        pending_adv = PayrollAdvance.query.filter_by(user_id=user_id, estado='Pendiente').first()
        if pending_adv:
            return False, "Ya tienes una solicitud de adelanto pendiente."
            
        try:
            adv = PayrollAdvance(
                user_id=user_id,
                monto=monto,
                motivo=motivo
            )
            db.session.add(adv)
            db.session.commit()
            return True, "Adelanto solicitado correctamente."
        except Exception as e:
            db.session.rollback()
            return False, str(e)
            
    @staticmethod
    def process_advance(advance_id: int, admin_id: int, action: str) -> tuple[bool, str]:
        adv = PayrollAdvance.query.get(advance_id)
        if not adv:
            return False, "Solicitud no encontrada."
            
        if adv.estado != 'Pendiente':
            return False, f"La solicitud ya fue procesada ({adv.estado})."
            
        if action == 'aprobar':
            adv.estado = 'Aprobado'
        elif action == 'rechazar':
            adv.estado = 'Rechazado'
        else:
            return False, "Acción inválida."
            
        adv.fecha_revision = datetime.now(pytz.timezone('America/Bogota')).replace(tzinfo=None)
        adv.revisado_por = admin_id
        
        try:
            db.session.commit()
            return True, f"Solicitud {adv.estado.lower()} correctamente."
        except Exception as e:
            db.session.rollback()
            return False, str(e)
