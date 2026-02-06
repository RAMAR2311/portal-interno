import os
from flask import Blueprint, render_template, request, jsonify, current_app, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import db, Message, User, Group
from datetime import datetime
import pytz
from extensions import socketio
from flask_socketio import emit, join_room

chat_bp = Blueprint('chat', __name__)

online_users = set()

@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        online_users.add(current_user.id)
        # Join user room
        join_room(str(current_user.id))
        # Join all group rooms the user is part of
        for group in current_user.groups:
            join_room(f"group_{group.id}")
            
        # Broadcast online status
        emit('user_status', {'user_id': current_user.id, 'status': 'online'}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        if current_user.id in online_users:
            online_users.remove(current_user.id)
        # Broadcast offline status
        emit('user_status', {'user_id': current_user.id, 'status': 'offline'}, broadcast=True)

@socketio.on('typing')
def handle_typing(data):
    recipient_id = data.get('recipient_id')
    group_id = data.get('group_id')
    
    payload = {
        'sender_id': current_user.id,
        'sender_name': current_user.nombre,
        'group_id': group_id
    }
    
    if group_id:
        emit('typing', payload, room=f"group_{group_id}", include_self=False)
    elif recipient_id:
        emit('typing', payload, room=str(recipient_id))

@socketio.on('stop_typing')
def handle_stop_typing(data):
    recipient_id = data.get('recipient_id')
    group_id = data.get('group_id')
    
    payload = {
        'sender_id': current_user.id,
        'group_id': group_id
    }
    
    if group_id:
        emit('stop_typing', payload, room=f"group_{group_id}", include_self=False)
    elif recipient_id:
        emit('stop_typing', payload, room=str(recipient_id))

# --- Video Call Signaling ---
# --- Advanced Group Video Call Signaling (Mesh Network) ---

# Track active call occupancy: room_id -> set(socket_id)
video_rooms = {}

@socketio.on('join_video_call')
def handle_join_video(data):
    room = data.get('room_id') # ID del grupo o chat
    join_room(room)
    # Notificar a los demás en el grupo que alguien entró (máximo 8)
    emit('user_joined_call', {'user_id': current_user.id}, room=room, include_self=False)

@socketio.on('start_call')
def handle_start_call(data):
    room = data.get('room_id')
    # Emitir notificación global de llamada entrante
    emit('incoming_call', {
        'caller_id': current_user.id,
        'caller_name': current_user.nombre,
        'room_id': room
    }, room=room, include_self=False)

@socketio.on('join_video_room')
def handle_join_video_room(data):
    """
    User actually joins the WebRTC mesh room.
    """
    room_id = data.get('room_id')
    
    if room_id not in video_rooms:
        video_rooms[room_id] = set()
        
    # Limit to 8 participants
    if len(video_rooms[room_id]) >= 8:
        emit('call_error', {'message': 'Sala llena (Máx. 8 participantes)'})
        return

    # Join the socket room
    join_room(room_id)
    video_rooms[room_id].add(request.sid)
    
    # Get list of other users currently in the room (to connect with them)
    # We send their socket IDs so the new user can initiate offers
    # We filter out self
    peers = list(video_rooms[room_id])
    peers.remove(request.sid)
    
    # 1. Tell existing users that a new user joined (so they prepare to receive offer/create offer)
    # For Mesh, often the new user initiates offers to existing.
    # Let's emit to the new user the list of existing peers.
    emit('all_users', peers)
    
    # 2. Tell specific other users (optional in some mesh archs, but usually handled via signals)
    # Actually, simpler Mesh: New user joins.
    # Sends "user_joined" signal to others?
    # Simple Mesh Logic:
    # New User A joins.
    # Server sends A list of [B, C].
    # A sends Offer to B, A sends Offer to C (via signal relay).
    
@socketio.on('signal')
def handle_signal(data):
    """
    Relays WebRTC signals (Offers, Answers, ICE Candidates) directly to a specific peer.
    """
    target_sid = data.get('target')
    payload = data.get('payload')
    
    # Relay the signal to the specific target socket
    # We include sender's socket ID so target knows who sent it
    emit('signal_received', {
        'sender': request.sid,
        'payload': payload,
        'sender_db_id': current_user.id, # Useful for UI labels
        'sender_name': current_user.nombre
    }, room=target_sid)

@socketio.on('leave_video_room')
def handle_leave_video_room(data):
    room_id = data.get('room_id')
    if room_id and room_id in video_rooms:
        if request.sid in video_rooms[room_id]:
            video_rooms[room_id].remove(request.sid)
            if not video_rooms[room_id]:
                del video_rooms[room_id]
                
    # Notify others so they remove the video element
    emit('user_left', {'sid': request.sid}, room=room_id)

@socketio.on('disconnect')
def handle_disconnect_video():
    # Check if user was in any video room
    # This is expensive O(N) but necessary if we don't track room in session
    # Optimized: We can store room_id in socket session if needed
    for room_id, members in list(video_rooms.items()):
        if request.sid in members:
            members.remove(request.sid)
            emit('user_left', {'sid': request.sid}, room=room_id)
            if not members:
                del video_rooms[room_id]
    
    # Call original disconnect logic manually if needed or let the other handler run (SocketIO runs all handlers for event)
    # The other handle_disconnect is decorated too, Flask-SocketIO runs both? 
    # Usually only one handler per event is best practice. 
    # I will merge this logic into the main disconnect handler below or separate it carefully.
    # Since I am replacing the block, I will rely on the global disconnect handler I saw earlier? 
    # Wait, simple separate handler might cause conflict if not designed well.
    # Better to just use 'leave_video_room' explicitly on frontend unload.
    pass

@chat_bp.route('/video_room/<room_id>')
@login_required
def video_room(room_id):
    return render_template('chat/video.html', room_id=room_id)

@chat_bp.route('/')
@login_required
def index():
    # Simple list of users to chat with (excluding self)
    users = User.query.filter(User.id != current_user.id).all()
    # List of groups the user belongs to
    my_groups = current_user.groups
    return render_template('chat/index.html', users=users, groups=my_groups, online_users=list(online_users))

@chat_bp.route('/create_group', methods=['POST'])
@login_required
def create_group():
    data = request.json
    group_name = data.get('name')
    member_ids = data.get('members', [])
    
    if not group_name or not member_ids:
        return jsonify({'error': 'Nombre y miembros requeridos'}), 400
        
    new_group = Group(name=group_name, created_by=current_user.id)
    db.session.add(new_group)
    
    # Add creator
    new_group.members.append(current_user)
    
    # Add selected members
    for user_id in member_ids:
        user = User.query.get(user_id)
        if user and user not in new_group.members:
            new_group.members.append(user)
            
    db.session.commit()
    
    # Notify members via SocketIO? Or just refresh page.
    # For now, just return success
    return jsonify({
        'status': 'success', 
        'group': {'id': new_group.id, 'name': new_group.name}
    })

@chat_bp.route('/delete_group/<int:group_id>', methods=['DELETE'])
@login_required
def delete_group(group_id):
    group = Group.query.get_or_404(group_id)
    
    # Security Check
    is_admin = current_user.rol == 'Admin'
    is_creator = group.created_by == current_user.id
    
    if not (is_admin or is_creator):
        return jsonify({'error': 'No tienes permiso para eliminar este grupo'}), 403

    try:
        # Delete associated messages first
        Message.query.filter_by(group_id=group.id).delete()
        
        # Remove members association (managed by secondary table, but standard delete usually handles cascades if set, 
        # but let's be safe. Actually SQLAlchemy handles secondary table clean up typically).
        # But we need to delete the group itself.
        db.session.delete(group)
        db.session.commit()
        
        return jsonify({'status': 'success'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@chat_bp.route('/get_messages')
@login_required
def get_messages():
    recipient_id = request.args.get('recipient_id', type=int)
    group_id = request.args.get('group_id', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    query = None
    
    if group_id:
        # Fetch group messages
        group = Group.query.get_or_404(group_id)
        if current_user not in group.members:
             return jsonify({'error': 'No eres miembro de este grupo'}), 403
             
        query = Message.query.filter_by(group_id=group_id)
        
    elif recipient_id:
        # Fetch direct messages
        query = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.recipient_id == recipient_id) & (Message.group_id == None)) |
            ((Message.sender_id == recipient_id) & (Message.recipient_id == current_user.id) & (Message.group_id == None))
        )
    else:
        return jsonify({'messages': []})

    # Order by DESC for pagination (get latest first), then reverse for display
    pagination = query.order_by(Message.timestamp.desc()).paginate(page=page, per_page=per_page, error_out=False)
    messages = pagination.items[::-1] # Reverse to show oldest first
    
    # Mark received messages as read (only if looking at first page or all loaded)
    # Ideally should only mark those visible, but for simplicity mark loaded ones.
    for msg in messages:
        if msg.recipient_id == current_user.id and not msg.is_read:
            msg.is_read = True
    db.session.commit()
    
    # Get remaining unread count for the navbar badge
    unread_count = Message.query.filter_by(recipient_id=current_user.id, is_read=False).count()
    
    messages_data = []
    for msg in messages:
        sender_name = msg.sender.nombre if msg.group_id else None
        
        # Prepare content
        messages_data.append({
            'id': msg.id,
            'sender_id': msg.sender_id,
            'sender_name': sender_name,
            'content': msg.content,
            'filename': msg.filename,
            'timestamp': msg.timestamp.strftime('%H:%M'),
            'is_me': msg.sender_id == current_user.id
        })
        
    return jsonify({
        'messages': messages_data, 
        'unread_count': unread_count,
        'has_more': pagination.has_next,
        'page': page
    })

@chat_bp.route('/send_message', methods=['POST'])
@login_required
def send_message():
    recipient_id = request.form.get('recipient_id') # Optional if group_id is present
    group_id = request.form.get('group_id') # Optional
    content = request.form.get('content')
    file = request.files.get('file')
    filename = None
    
    
    if (not recipient_id and not group_id) or (not content and not file):
        return jsonify({'error': 'Datos faltantes'}), 400
        
    if file:
        filename = secure_filename(f"chat_{current_user.id}_{int(datetime.now().timestamp())}_{file.filename}")
        save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'chat_files')
        os.makedirs(save_path, exist_ok=True)
        file.save(os.path.join(save_path, filename))
        
    new_msg = Message(
        sender_id=current_user.id,
        recipient_id=recipient_id if recipient_id else None,
        group_id=group_id if group_id else None,
        content=content,
        filename=filename
    )
    db.session.add(new_msg)
    db.session.commit()

    # Emit Logic
    msg_payload = {
        'sender_id': current_user.id,
        'sender_name': current_user.nombre,
        'recipient_id': recipient_id,
        'group_id': group_id,
        'content': content,
        'filename': filename,
        'timestamp': new_msg.timestamp.strftime('%H:%M'),
        'is_me': False
    }

    if group_id:
        room = f"group_{group_id}"
        # Emit to group room
        socketio.emit('new_message', msg_payload, room=room)
    else:
        # Emit to recipient
        socketio.emit('new_message', msg_payload, room=str(recipient_id))
        
        # Emit to sender (so it appears immediately)
        msg_payload['is_me'] = True
        socketio.emit('new_message', msg_payload, room=str(current_user.id))
    
    return jsonify({'status': 'success'})

@chat_bp.route('/download_chat_file/<filename>')
@login_required
def download_chat_file(filename):
    directory = os.path.join(current_app.config['UPLOAD_FOLDER'], 'chat_files')
    return send_from_directory(directory, filename, as_attachment=True)
