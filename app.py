import eventlet
eventlet.monkey_patch()

from flask import Flask, redirect, url_for
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
from config import Config
from models import db, User
from extensions import socketio

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate = Migrate(app, db)
    login_manager = LoginManager(app)
    login_manager.login_view = 'auth.login'
    socketio.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Blueprint Registration (Importing here to avoid circular dependencies)
    from routes.auth import auth_bp
    from routes.admin import admin_bp
    from routes.employee import employee_bp
    from routes.chat import chat_bp
    from routes.calendar import calendar_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(employee_bp, url_prefix='/employee')
    app.register_blueprint(chat_bp, url_prefix='/chat')
    app.register_blueprint(calendar_bp, url_prefix='/calendar')
    
    from routes.training import training_bp
    app.register_blueprint(training_bp, url_prefix='/training')

    # Root route redirect
    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    @app.context_processor
    def inject_unread_count():
        if current_user.is_authenticated:
            # Import Message here to avoid circular dependencies if any, though model is safe
            from models import Message
            unread_count = Message.query.filter_by(recipient_id=current_user.id, is_read=False).count()
            return dict(unread_count=unread_count)
        return dict(unread_count=0)

    # Global Error Handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('500.html'), 500

    return app

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Create a default admin if none exists
        if not User.query.filter_by(email='admin@portal.com').first():
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
            
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
