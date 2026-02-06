from io import BytesIO
from datetime import datetime
import pytz
from flask import render_template, current_app
from xhtml2pdf import pisa
from models import db, PayrollDoc, User
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
        financial_data: dict
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
