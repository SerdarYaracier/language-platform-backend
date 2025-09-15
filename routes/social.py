from flask import Blueprint, jsonify, request
from extensions import supabase

social_bp = Blueprint('social_bp', __name__, url_prefix='/api/social')

# --- YARDIMCI FONKSİYON: Kullanıcıyı Token ile Doğrulama ---
def get_user_from_request(current_request):
    auth_header = current_request.headers.get('Authorization')
    if not auth_header or 'Bearer ' not in auth_header:
        return None, (jsonify(error="Authorization header missing or malformed"), 401)
    
    jwt = auth_header.split(" ")[1]
    try:
        user_response = supabase.auth.get_user(jwt)
        if user_response.user:
            return user_response.user, None
        else:
            return None, (jsonify(error="Invalid or expired token"), 401)
    except Exception as e:
        return None, (jsonify(error=f"Token validation failed: {e}"), 401)

# --- API ENDPOINTS ---

@social_bp.route('/friends', methods=['GET'])
def get_friends_and_requests():
    """Kullanıcının arkadaşlarını, gelen ve gönderilen isteklerini listeler."""
    user, err = get_user_from_request(request)
    if err: return err
    
    try:
        # 1. Kullanıcının dahil olduğu tüm arkadaşlık ilişkilerini çek
        friendships_res = supabase.table('friendships').select('*').or_(f'user1_id.eq.{user.id},user2_id.eq.{user.id}').execute()
        
        if not friendships_res.data:
            return jsonify({ "friends": [], "incoming_requests": [], "sent_requests": [] })

        # 2. Bu ilişkilerdeki diğer tüm kullanıcıların ID'lerini topla
        other_user_ids = set()
        for f in friendships_res.data:
            if f['user1_id'] == user.id:
                other_user_ids.add(f['user2_id'])
            else:
                other_user_ids.add(f['user1_id'])
        
        # 3. Bu ID'lere ait profil bilgilerini tek seferde, verimli bir şekilde çek
        profiles_map = {}
        if other_user_ids:
            profiles_res = supabase.table('profiles').select('id, username, avatar_url').in_('id', list(other_user_ids)).execute()
            profiles_map = {p['id']: p for p in profiles_res.data}

        # 4. Gelen veriyi frontend'in beklediği formata Python içinde dönüştür
        result = {
            "friends": [],
            "incoming_requests": [],
            "sent_requests": []
        }
        for f in friendships_res.data:
            if f['status'] == 'accepted':
                friend_id = f['user2_id'] if f['user1_id'] == user.id else f['user1_id']
                if friend_id in profiles_map:
                    result['friends'].append(profiles_map[friend_id])
            
            elif f['status'] == 'pending':
                if f['user2_id'] == user.id: # İstek bana gelmiş
                    if f['user1_id'] in profiles_map:
                        requester_profile = profiles_map[f['user1_id']]
                        # Frontend'in yanıt verebilmesi için friendship_id'yi ekleyelim
                        requester_profile['friendship_id'] = f['id']
                        result['incoming_requests'].append(requester_profile)
                else: # İsteği ben göndermişim
                    if f['user2_id'] in profiles_map:
                        result['sent_requests'].append(profiles_map[f['user2_id']])

        return jsonify(result)

    except Exception as e:
        print(f"!!! CRITICAL Error in get_friends_and_requests: {e}")
        return jsonify(error="An internal server error occurred while fetching friends data."), 500

@social_bp.route('/friends/request', methods=['POST', 'OPTIONS'])
def send_friend_request():
    """Bir kullanıcıya arkadaşlık isteği gönderir."""
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    user, err = get_user_from_request(request)
    if err: return err
    
    data = request.get_json()
    receiver_id = data.get('receiver_id')
    if not receiver_id:
        return jsonify(error="Receiver ID is required"), 400

    try:
        # Veritabanındaki 'create_friend_request' fonksiyonunu çağıralım.
        # Bu fonksiyon kendi içinde güvenlik kontrollerini (kendine istek atma, mevcut ilişki) yapar.
        supabase.rpc('create_friend_request', {'p_receiver_id': receiver_id}).execute()
        return jsonify(message="Friend request sent successfully!"), 201
    except Exception as e:
        # Veritabanından gelen özel hata mesajlarını yakala
        error_message = str(e)
        if "custom postgres error" in error_message:
            details = error_message.split('"message":"')[-1].split('"')[0]
            return jsonify(error=details), 409 # 409 Conflict daha uygun
        return jsonify(error=f"An internal server error occurred: {e}"), 500

@social_bp.route('/friends/accept', methods=['POST', 'OPTIONS'])
def accept_friend_request():
    """Gelen bir arkadaşlık isteğini kabul eder."""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    user, err = get_user_from_request(request)
    if err: return err

    # Accept JSON or form-encoded data; be tolerant of different key names
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}
    # Some frontends might send 'id' or 'friend_id'
    friendship_id = data.get('friendship_id') or data.get('friend_id') or data.get('id')
    # If still missing, try query params / form
    if not friendship_id:
        friendship_id = request.form.get('friendship_id') or request.args.get('friendship_id') or request.args.get('id')
    if not friendship_id:
        print(f"accept_friend_request: missing payload. headers={dict(request.headers)}, args={request.args}, form={request.form}")
        return jsonify(error="Friendship ID is required"), 400

    try:
        # RLS politikası, sadece isteği alanın (user2_id) bu güncellemeyi yapabilmesini sağlar.
        supabase.table('friendships').update({'status': 'accepted'}).eq('id', friendship_id).eq('user2_id', user.id).execute()
        return jsonify(message="Friend request accepted."), 200
    except Exception as e:
        return jsonify(error=f"An internal server error occurred: {e}"), 500

@social_bp.route('/friends/reject', methods=['POST', 'OPTIONS'])
def reject_friend_request():
    """Gelen bir isteği reddeder veya bir arkadaşlığı sonlandırır."""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    user, err = get_user_from_request(request)
    if err: return err

    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}
    friendship_id = data.get('friendship_id') or data.get('friend_id') or data.get('id')
    if not friendship_id:
        friendship_id = request.form.get('friendship_id') or request.args.get('friendship_id') or request.args.get('id')
    if not friendship_id:
        print(f"reject_friend_request: missing payload. headers={dict(request.headers)}, args={request.args}, form={request.form}")
        return jsonify(error="Friendship ID is required"), 400
    
    try:
        # RLS politikası, sadece ilgili kullanıcıların bu satırı silebilmesini sağlar.
        supabase.table('friendships').delete().eq('id', friendship_id).execute()
        return jsonify(message="Friendship rejected or removed."), 200
    except Exception as e:
        return jsonify(error=f"An internal server error occurred: {e}"), 500


@social_bp.route('/friends/decline', methods=['POST', 'OPTIONS'])
def decline_friend_request_compat():
    """Compatibility route for older frontends using /friends/decline"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    # Reuse reject logic by delegating to the same behavior
    return reject_friend_request()


@social_bp.route('/users/search', methods=['GET', 'OPTIONS'])
def users_search():
    """Search users by username used by Friends modal. Handles CORS preflight."""
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    user, err = get_user_from_request(request)
    if err: return err

    query = request.args.get('query', '')
    if not query or len(query) < 2:
        return jsonify([]), 200

    try:
        # get all profiles matching the query (limit a bit higher then filter)
        search_res = supabase.table('profiles').select('id, username, avatar_url').ilike('username', f'%{query}%').limit(20).execute()
        candidates = search_res.data or []

        # get existing friendship ids to exclude
        friendships_res = supabase.table('friendships').select('user1_id, user2_id').or_(f'user1_id.eq.{user.id},user2_id.eq.{user.id}').execute()
        exclude_ids = {user.id}
        if friendships_res and getattr(friendships_res, 'data', None):
            for fr in friendships_res.data:
                if fr.get('user1_id'):
                    exclude_ids.add(fr['user1_id'])
                if fr.get('user2_id'):
                    exclude_ids.add(fr['user2_id'])

        results = []
        for p in candidates:
            pid = p.get('id')
            if not pid or pid in exclude_ids:
                continue
            results.append({'id': pid, 'username': p.get('username'), 'avatar_url': p.get('avatar_url')})
            if len(results) >= 10:
                break

        return jsonify(results), 200
    except Exception as e:
        print(f"users_search error: {e}")
        return jsonify([]), 200


@social_bp.route('/friends/add', methods=['POST', 'OPTIONS'])
def friends_add_compat():
    """Compatibility endpoint for older frontends calling /friends/add
    Handles preflight and provides direct friend request functionality.
    """
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    user, err = get_user_from_request(request)
    if err: return err
    
    data = request.get_json() or {}
    # Support either 'username' or 'receiver_id' coming from older frontends
    receiver_id = data.get('receiver_id') or data.get('username')
    
    if not receiver_id:
        return jsonify(error="Receiver ID or username is required"), 400

    try:
        # Check if receiver_id looks like a UUID (contains hyphens) or is a username
        if '-' not in str(receiver_id) or len(str(receiver_id)) < 32:
            # This looks like a username, convert to ID
            print(f"Converting username '{receiver_id}' to ID...")
            profile_res = supabase.table('profiles').select('id').eq('username', receiver_id).single().execute()
            if not profile_res.data:
                return jsonify(error="User not found"), 404
            receiver_id = profile_res.data['id']
            print(f"Found user ID: {receiver_id}")

        # Prevent sending request to self
        if str(user.id) == str(receiver_id):
            return jsonify(error="Cannot send friend request to yourself."), 400

        # Check for an existing friendship in either direction between these two IDs
        existing_res1 = supabase.table('friendships').select('id, user1_id, user2_id, status')
        existing_res1 = existing_res1.eq('user1_id', user.id).eq('user2_id', receiver_id).execute()

        existing_res2 = supabase.table('friendships').select('id, user1_id, user2_id, status')
        existing_res2 = existing_res2.eq('user1_id', receiver_id).eq('user2_id', user.id).execute()

        existing_rows = []
        if getattr(existing_res1, 'data', None):
            existing_rows.extend(existing_res1.data)
        if getattr(existing_res2, 'data', None):
            existing_rows.extend(existing_res2.data)

        if existing_rows:
            # If a row exists that contains both IDs (in some order), return conflict
            for row in existing_rows:
                ids = {str(row.get('user1_id')), str(row.get('user2_id'))}
                if {str(user.id), str(receiver_id)} == ids:
                    status = row.get('status')
                    if status == 'accepted':
                        return jsonify(error="You are already friends."), 409
                    else:
                        return jsonify(error="A friend request already exists."), 409

        # Insert the pending friendship row directly (server-side action)
        print(f"Inserting friendship from {user.id} to {receiver_id}")
        insert_res = supabase.table('friendships').insert({
            'user1_id': user.id,
            'user2_id': receiver_id,
            'status': 'pending'
        }).execute()

        # If insert returned errors, surface them
        if getattr(insert_res, 'error', None):
            raise Exception(insert_res.error)

        return jsonify(message="Friend request sent successfully!"), 201
        
    except Exception as e:
        error_message = str(e)
        if "custom postgres error" in error_message:
            details = error_message.split('"message":"')[-1].split('"')[0]
            return jsonify(error=details), 409
        print(f"!!! CRITICAL Error in friends_add_compat: {e}")
        return jsonify(error=f"An internal server error occurred: {e}"), 500