from app import create_app, db
from models import User

app = create_app()

def reset_admin():
    with app.app_context():
        admin = User.query.filter_by(email='admin@portal.com').first()
        if admin:
            admin.set_password('admin123')
            db.session.commit()
            print("Contraseña de admin@portal.com restablecida a: admin123")
        else:
            # Si no existe, lo creamos
            admin = User(
                email='admin@portal.com',
                rol='Admin',
                nombre='Super Admin',
                cargo='Administrador del Sistema'
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Usuario admin no existía. Creado con admin@portal.com / admin123")

if __name__ == '__main__':
    reset_admin()
