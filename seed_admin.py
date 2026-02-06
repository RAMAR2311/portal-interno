from app import create_app, db
from models import User
import os

app = create_app()

def seed_admin():
    with app.app_context():
        # Create a default admin if none exists
        if not User.query.filter_by(email='admin@portal.com').first():
            try:
                admin = User(
                    email='admin@portal.com',
                    rol='Admin',
                    nombre='Super Admin',
                    cargo='Administrador del Sistema'
                )
                admin.set_password('admin123')
                db.session.add(admin)
                db.session.commit()
                print("Admin user created: admin@portal.com / admin123")
            except Exception as e:
                db.session.rollback()
                print(f"Error creating admin: {e}")
        else:
            print("Admin user already exists")

if __name__ == '__main__':
    seed_admin()
