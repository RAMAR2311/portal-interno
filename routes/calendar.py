from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user
from models import db, CalendarEvent, User
from datetime import datetime, timezone
import dateutil.parser
import pytz

calendar_bp = Blueprint('calendar', __name__)

def get_bogota_time():
    return datetime.now(pytz.timezone('America/Bogota'))

@calendar_bp.route('/')
@login_required
def index():
    users = User.query.filter(User.current_status != 'Inactivo').all() # simple filter
    # Or just all users except self? 
    all_users = User.query.filter(User.id != current_user.id).all()
    return render_template('calendar/index.html', users=all_users)

@calendar_bp.route('/api/events', methods=['GET'])
@login_required
def get_events():
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    target_user_id = request.args.get('user_id', type=int)
    
    if not start_str or not end_str:
        return jsonify({'error': 'Missing start/end dates'}), 400
        
    try:
        # FullCalendar sends ISO strings. 
        # We need to make sure we parse them correctly relative to our DB storage (naive bogota usually)
        # But FullCalendar sends UTC often? Let's check. 
        # Usually it sends '2023-10-01T00:00:00-05:00' if configured matching browser.
        start_date = dateutil.parser.isoparse(start_str)
        end_date = dateutil.parser.isoparse(end_str)
        
        # Strip tz for DB comparison if DB is naive
        # Our get_bogota_time returns aware, but saving to DB often strips it if column is DateTime without timezone in some drivers
        # Assuming DB is naive (standard flask-sqlalchemy default usually)
        # Convert to Bogota then strip?
        # Actually simplest is to rely on what models.py does. 
        # models.py uses `default=get_bogota_time`. 
        
        # Let's ensure strict comparison
        if start_date.tzinfo:
            start_date = start_date.astimezone(pytz.timezone('America/Bogota')).replace(tzinfo=None)
        if end_date.tzinfo:
            end_date = end_date.astimezone(pytz.timezone('America/Bogota')).replace(tzinfo=None)
            
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400

    query = CalendarEvent.query.filter(
        CalendarEvent.start >= start_date,
        CalendarEvent.end <= end_date
    )
    
    if target_user_id:
        query = query.filter_by(user_id=target_user_id)
        # Privacy Logic: If looking at someone else
        is_owner = (current_user.id == target_user_id)
    else:
        # Defaults to current user? Or error? Or all?
        # Specification says "Si yo consulto el calendario de otro..." implies default is mine
        # Let's default to current user if not specified
        query = query.filter_by(user_id=current_user.id)
        is_owner = True
        
    events = query.all()
    results = []
    
    for event in events:
        # Privacy Redaction
        # If I am not the owner AND (Event is Private OR Privacy Rule applies to everything?)
        # Specification: "Si yo... y el evento es is_private=True o simplemente no soy el dueño..."
        # Wait, "o simplemente no soy el dueño" suggests I ALWAYS see generic "Ocupado" for others?
        # "el title debe devolverse genéricamente como 'Ocupado' y la descripción oculta."
        
        if is_owner:
            results.append({
                'id': event.id,
                'title': event.title,
                'start': event.start.isoformat(),
                'end': event.end.isoformat(),
                'type': event.type,
                'description': event.description,
                'is_private': event.is_private,
                'extendedProps': {
                    'is_mine': True
                }
            })
        else:
            # Viewing someone else
            if event.is_private:
                # Private events definitely obscured
                title = "Ocupado (Privado)"
            else:
                 # Public events from others -> Spec says "o simplemente no soy el dueño" -> "Ocupado"
                 # Let's follow spec strictly: "Solo el dueño ve los detalles reales."
                 title = "Ocupado"
                 
            results.append({
                'id': event.id,
                'title': title,
                'start': event.start.isoformat(),
                'end': event.end.isoformat(),
                'type': 'Ocupado', # Ovwrrite type? Or keep 'Reunión' vs 'Fuera'? 
                # "el title debe devolverse ... como Ocupado ... descripción oculta"
                # Type might be useful to know IF they are 'Fuera de Oficina' vs just 'Reunión'?
                # Let's hide type too to be safe/generic as requested, OR maybe show 'Fuera de Oficina' is useful info?
                # User prompted: "mostrar disponibilidad... para saber cuándo pueden hablar"
                # Knowing 'Fuera de Oficina' is vital. Knowing 'Reunión' vs 'Ocupado' is less vital.
                # Let's preserve type if it is 'Fuera de Oficina', otherwise 'Ocupado'.
                
                'type': event.type if event.type == 'Fuera de Oficina' else 'Ocupado',
                'description': '', # Hidden
                'is_private': event.is_private,
                'color': '#6c757d', # Gray
                'extendedProps': {
                    'is_mine': False
                }
            })

    return jsonify(results)

@calendar_bp.route('/api/events', methods=['POST'])
@login_required
def create_event():
    data = request.get_json()
    title = data.get('title')
    start_str = data.get('start')
    end_str = data.get('end')
    type_ = data.get('type')
    description = data.get('description', '')
    is_private = data.get('is_private', False)
    
    if not title or not start_str or not end_str or not type_:
        return jsonify({'error': 'Missing required fields'}), 400
        
    try:
        start = dateutil.parser.isoparse(start_str)
        end = dateutil.parser.isoparse(end_str)
        
        # Normalize to naive Bogota
        if start.tzinfo: start = start.astimezone(pytz.timezone('America/Bogota')).replace(tzinfo=None)
        if end.tzinfo: end = end.astimezone(pytz.timezone('America/Bogota')).replace(tzinfo=None)
        
        if end <= start:
            return jsonify({'error': 'La fecha de fin debe ser posterior a la de inicio'}), 400
            
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400
        
    new_event = CalendarEvent(
        user_id=current_user.id,
        title=title,
        start=start,
        end=end,
        type=type_,
        description=description,
        is_private=is_private
    )
    
    db.session.add(new_event)
    db.session.commit()
    
    return jsonify({'success': True, 'id': new_event.id})

@calendar_bp.route('/api/events/<int:event_id>', methods=['PUT'])
@login_required
def update_event(event_id):
    event = CalendarEvent.query.get_or_404(event_id)
    
    if event.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
        
    data = request.get_json()
    
    # Update fields if present
    if 'title' in data: event.title = data['title']
    if 'type' in data: event.type = data['type']
    if 'description' in data: event.description = data['description']
    if 'is_private' in data: event.is_private = data['is_private']
    
    if 'start' in data and 'end' in data:
        try:
            start = dateutil.parser.isoparse(data['start'])
            end = dateutil.parser.isoparse(data['end'])
             # Normalize
            if start.tzinfo: start = start.astimezone(pytz.timezone('America/Bogota')).replace(tzinfo=None)
            if end.tzinfo: end = end.astimezone(pytz.timezone('America/Bogota')).replace(tzinfo=None)
            
            if end <= start:
                return jsonify({'error': 'End date must be after start date'}), 400
                
            event.start = start
            event.end = end
        except ValueError:
             return jsonify({'error': 'Invalid date format'}), 400
             
    db.session.commit()
    return jsonify({'success': True})

@calendar_bp.route('/api/events/<int:event_id>', methods=['DELETE'])
@login_required
def delete_event(event_id):
    event = CalendarEvent.query.get_or_404(event_id)
    
    if event.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
        
    db.session.delete(event)
    db.session.commit()
    return jsonify({'success': True})
