from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user
from flask_login import login_required, current_user
from models import db, CalendarEvent, User
from sqlalchemy import or_
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
        # If looking at someone specific, show events where they are owner OR attendee
        query = query.filter(or_(
            CalendarEvent.user_id == target_user_id,
            CalendarEvent.attendees.any(id=target_user_id)
        ))
        # Privacy Logic: If looking at someone else
        is_owner = (current_user.id == target_user_id)
    else:
        # Defaults to current user. Show events where I am owner OR attendee
        query = query.filter(or_(
            CalendarEvent.user_id == current_user.id,
            CalendarEvent.attendees.any(id=current_user.id)
        ))
        is_owner = True
        
    events = query.all()
    results = []
    
    for event in events:
        # Visibility Logic
        # I can see details if:
        # 1. I am the creator
        # 2. I am an attendee
        # 3. I am looking at my own calendar (implied by 1 & 2 usually, but handled by filter)
        # 4. It's public and looking at someone else (Shows Ocupado but obscured title? No, obscured title unless private)
        
        am_i_creator = (event.user_id == current_user.id)
        am_i_attendee = (current_user in event.attendees)
        can_see_details = am_i_creator or am_i_attendee
        
        # Prepare attendees list for frontend
        attendees_data = [{'id': u.id, 'nombre': u.nombre} for u in event.attendees]

        if can_see_details:
            results.append({
                'id': event.id,
                'title': event.title,
                'start': event.start.isoformat(),
                'end': event.end.isoformat(),
                'type': event.type,
                'description': event.description,
                'is_private': event.is_private,
                'extendedProps': {
                    'is_mine': am_i_creator, # Only creator can edit fully usually
                    'notes': 'You are an attendee' if am_i_attendee and not am_i_creator else '',
                    'attendees': attendees_data
                }
            })
        else:
            # Viewing someone else's event where I am NOT involved
            if event.is_private:
                title = "Ocupado (Privado)"
            else:
                title = "Ocupado"
                 
            results.append({
                'id': event.id,
                'title': title,
                'start': event.start.isoformat(),
                'end': event.end.isoformat(),
                'type': event.type if event.type == 'Fuera de Oficina' else 'Ocupado',
                'description': '', # Hidden
                'is_private': event.is_private,
                'color': '#6c757d', # Gray
                'extendedProps': {
                    'is_mine': False,
                    'attendees': [] # Hide attendees too? Yes for privacy
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
    
    # Handle Attendees
    attendee_ids = data.get('attendees', [])
    if attendee_ids:
        users = User.query.filter(User.id.in_(attendee_ids)).all()
        new_event.attendees = users
    
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
    
    if 'attendees' in data:
        attendee_ids = data['attendees']
        users = User.query.filter(User.id.in_(attendee_ids)).all()
        event.attendees = users
             
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
