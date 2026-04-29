import os
from datetime import datetime, timedelta, date, time
import random
from app import create_app, db
from models import (
    User, PayrollDoc, TimeLog, Comunicado, PayrollAdvance, 
    Survey, SurveyQuestion, SurveyOption, Incapacidad, 
    LeaveRequest, WeeklySchedule, CalendarEvent
)

app = create_app()

def populate():
    with app.app_context():
        print("--- Iniciando poblamiento de datos de prueba ---")
        
        # 1. Asegurar Admin
        admin = User.query.filter_by(email='admin@portal.com').first()
        if not admin:
            admin = User(
                email='admin@portal.com', rol='Admin', nombre='Super Admin',
                cargo='Administrador del Sistema', is_active=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            print("Admin creado.")

        # 2. Crear Empleados Diversos
        empleados_data = [
            {'nombre': 'Juan Pérez', 'email': 'juan@portal.com', 'cargo': 'Asesor Comercial', 'salario': 2500000},
            {'nombre': 'Maria García', 'email': 'maria@portal.com', 'cargo': 'Coordinador Comercial', 'salario': 3800000},
            {'nombre': 'Carlos Ruiz', 'email': 'carlos@portal.com', 'cargo': 'Analista de Soporte', 'salario': 2100000},
            {'nombre': 'Ana López', 'email': 'ana@portal.com', 'cargo': 'Asesor Comercial', 'salario': 2400000},
        ]
        
        empleados = []
        for data in empleados_data:
            emp = User.query.filter_by(email=data['email']).first()
            if not emp:
                emp = User(
                    email=data['email'], rol='Empleado', nombre=data['nombre'],
                    cargo=data['cargo'], salario=data['salario'], is_active=True,
                    fecha_ingreso=date(2025, 1, 1), eps='Compensar', arl='Sura',
                    entidad_bancaria='Bancolombia', numero_cuenta='123456789'
                )
                emp.set_password('empleado123')
                db.session.add(emp)
                print(f"Empleado {data['nombre']} creado.")
            empleados.append(emp)
        
        db.session.flush()

        # 3. Horarios Semanales para todos
        for emp in empleados:
            for i in range(5): # Lunes a Viernes
                if not WeeklySchedule.query.filter_by(user_id=emp.id, dia_semana=i).first():
                    sched = WeeklySchedule(
                        user_id=emp.id, dia_semana=i,
                        hora_entrada=time(8, 0), hora_salida=time(17, 0)
                    )
                    db.session.add(sched)

        # 4. Comunicados
        if not Comunicado.query.first():
            coms = [
                Comunicado(titulo='Bienvenida al nuevo portal', contenido='Estamos felices de lanzar nuestra nueva plataforma interna.', user_id=admin.id),
                Comunicado(titulo='Recordatorio: Pausas Activas', contenido='No olviden realizar sus pausas activas cada 2 horas.', user_id=admin.id),
                Comunicado(titulo='Evento Fin de Mes', contenido='Este viernes tendremos pizza en la oficina.', user_id=admin.id)
            ]
            db.session.add_all(coms)
            print("Comunicados creados.")

        # 5. Datos por empleado (Nóminas, Logs, Solicitudes)
        meses = ['Enero', 'Febrero', 'Marzo']
        for emp in empleados:
            # Nóminas
            for mes in meses:
                if not PayrollDoc.query.filter_by(user_id=emp.id, mes=mes).first():
                    pay = PayrollDoc(
                        user_id=emp.id, mes=mes, anio=2026, periodo='Mensual',
                        filename=f'test_payroll_{emp.id}_{mes}.pdf',
                        salario_base=emp.salario, neto_pagar=emp.salario * 0.92
                    )
                    db.session.add(pay)
            
            # Logs de tiempo (últimos 5 días)
            hoy = datetime.now()
            for d in range(5):
                fecha_log = hoy - timedelta(days=d)
                if fecha_log.weekday() < 5: # Solo laborables
                    log1 = TimeLog(user_id=emp.id, new_status='Activo', timestamp=fecha_log.replace(hour=8, minute=random.randint(0,10)))
                    log2 = TimeLog(user_id=emp.id, new_status='Inactivo', timestamp=fecha_log.replace(hour=17, minute=random.randint(0,5)))
                    db.session.add_all([log1, log2])

            # Adelantos
            if not PayrollAdvance.query.filter_by(user_id=emp.id).first():
                adv = PayrollAdvance(
                    user_id=emp.id, monto=500000, motivo='Gasto médico imprevisto',
                    estado='Aprobado' if random.random() > 0.5 else 'Pendiente'
                )
                db.session.add(adv)

        # 6. Una Encuesta
        if not Survey.query.first():
            surv = Survey(titulo='Clima Organizacional 2026', descripcion='Queremos saber cómo te sientes en Zenic Master Control.')
            db.session.add(surv)
            db.session.flush()
            
            q1 = SurveyQuestion(survey_id=surv.id, texto_pregunta='¿Qué tan feliz eres en tu cargo?', tipo_respuesta='Calificacion')
            q2 = SurveyQuestion(survey_id=surv.id, texto_pregunta='Danos una sugerencia de mejora.', tipo_respuesta='Texto')
            db.session.add_all([q1, q2])
            print("Encuesta creada.")

        # 7. Incapacidades y Permisos
        if not Incapacidad.query.first():
            inc = Incapacidad(
                user_id=empleados[0].id, tipo='Enfermedad General',
                fecha_inicio=date.today() - timedelta(days=10),
                fecha_fin=date.today() - timedelta(days=8),
                dias_totales=3, archivo_soporte='soporte_fake.pdf', estado='Validada'
            )
            db.session.add(inc)

        if not LeaveRequest.query.first():
            perm = LeaveRequest(
                user_id=empleados[1].id, tipo_permiso='Cita Médica',
                fecha_inicio=date.today() + timedelta(days=2),
                fecha_fin=date.today() + timedelta(days=2),
                motivo='Control de ortodoncia', estado='Pendiente'
            )
            db.session.add(perm)

        db.session.commit()
        print("\n--- ¡Poblamiento completado con éxito! ---")
        print("Credenciales Admin: admin@portal.com / admin123")
        print("Credenciales Empleado: juan@portal.com / empleado123")

if __name__ == '__main__':
    populate()
