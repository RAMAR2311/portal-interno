from app import create_app, db
from models import User, WeeklySchedule
from datetime import time
import os

app = create_app()

def seed_test_data():
    with app.app_context():
        # Create Employee
        emp = User.query.filter_by(email='employee@portal.com').first()
        if not emp:
            emp = User(
                email='employee@portal.com',
                rol='Empleado',
                nombre='Test Employee',
                cargo='Asesor Comercial',
                salario=2000000,
                is_active=True
            )
            emp.set_password('employee123')
            db.session.add(emp)
            db.session.commit()
            print("Employee user created: employee@portal.com / employee123")
        else:
            print("Employee user already exists")

        # Set Schedule for Employee (M-F 9:00 - 18:00)
        for i in range(5):
            sched = WeeklySchedule.query.filter_by(user_id=emp.id, dia_semana=i).first()
            if not sched:
                sched = WeeklySchedule(
                    user_id=emp.id,
                    dia_semana=i,
                    hora_entrada=time(9, 0),
                    hora_salida=time(18, 0),
                    es_dia_laboral=True
                )
                db.session.add(sched)
        db.session.commit()
        print("Schedule seeded for employee.")

if __name__ == '__main__':
    seed_test_data()
