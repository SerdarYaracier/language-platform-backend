import os
from flask import Blueprint, jsonify, request
from supabase import create_client, Client

# Inline a small helper so we don't depend on utils.auth_helper import path
def get_user_from_request(current_request):
    auth_header = current_request.headers.get('Authorization')
    if not auth_header or ' ' not in auth_header:
        return None, (jsonify(error="Authorization header missing or malformed"), 401)
    token = auth_header.split(' ', 1)[1]
    token = token.strip()
    # tolerate JSON blob token
    if token.startswith('{'):
        try:
            import json
            parsed = json.loads(token)
            token = parsed.get('access_token') or parsed.get('accessToken') or parsed.get('token') or (parsed.get('data') or {}).get('access_token')
        except Exception:
            pass
    try:
        # Validate token with Supabase and get real user
        user_resp = supabase.auth.get_user(token)
        user = None
        if hasattr(user_resp, 'user'):
            user = user_resp.user
        elif isinstance(user_resp, dict):
            user = user_resp.get('user') or (user_resp.get('data') and user_resp['data'].get('user'))
        
        if not user:
            return None, (jsonify(error="Invalid or expired token"), 401)
        
        return user, None
    except Exception as e:
        print(f"Auth validation error: {e}")
        return None, (jsonify(error="Failed to validate token"), 401)

# Supabase client (reads env vars)
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

progress_bp = Blueprint('progress_bp', __name__, url_prefix='/api/progress')

@progress_bp.route('/submit-score', methods=['POST'])
def submit_score():
    user, err = get_user_from_request(request)
    if err: return err

    data = request.get_json()
    print(f"[submit_score] Received data: {data}")  # DEBUG: log incoming data
    
    # Be flexible with field names that frontend might send
    level = data.get('level')
    game_slug = data.get('gameSlug') or data.get('game') or data.get('gameType')
    category_slug = data.get('categorySlug') or data.get('category')
    language_code = data.get('language') or data.get('lang') or 'en'  # default to 'en'

    print(f"[submit_score] Parsed fields - level: {level}, gameSlug: {game_slug}, categorySlug: {category_slug}, language: {language_code}")  # DEBUG

    # For now, make gameSlug optional since existing frontends might not send it
    if not all([level is not None, category_slug, language_code]):
        missing_fields = []
        if level is None: missing_fields.append('level')
        if not category_slug: missing_fields.append('categorySlug/category')
        if not language_code: missing_fields.append('language/lang')
        print(f"[submit_score] Missing fields: {missing_fields}")  # DEBUG
        return jsonify(error=f"Missing required fields: {', '.join(missing_fields)}"), 400
    
    # Kazanılan puanı belirle (örneğin sabit 5 puan veya dinamik)
    points_to_add = 5 # Her doğru cevap için 5 puan

    try:
        # Kategori ID'sini bul
        category_response = supabase.table('categories').select('id').eq('slug', category_slug).single().execute()
        if not category_response.data:
            return jsonify(error=f"Category '{category_slug}' not found."), 404
        category_id = category_response.data['id']

        # DEBUG: Log user ID and what we're passing to RPC
        user_id = user.id if hasattr(user, 'id') else user.get('id')
        print(f"[submit_score] User ID: {user_id} (type: {type(user_id)})")
        print(f"[submit_score] Category ID: {category_id}")
        
        # Create a user-authenticated supabase client using the token from request
        auth_header = request.headers.get('Authorization')
        token = auth_header.split(' ', 1)[1].strip()
        if token.startswith('{'):
            try:
                import json
                parsed = json.loads(token)
                token = parsed.get('access_token') or parsed.get('accessToken') or parsed.get('token') or (parsed.get('data') or {}).get('access_token')
            except Exception:
                pass
        
        # Create authenticated client - this will have proper RLS context
        print(f"[submit_score] Creating user-authenticated client...")
        user_supabase = create_client(url, key)
        user_supabase.auth.session = {'access_token': token, 'refresh_token': '', 'user': user}  # Set user session properly
        
        print(f"[submit_score] About to call upsert_level_progress RPC with user context")

        # YENİ: user_level_progress tablosunu güncelle
        # Kullanıcının o kategori, dil ve seviyedeki skorunu artırıyoruz.
        user_supabase.rpc('upsert_level_progress', {
            'p_user_id': user_id,
            'p_category_id': category_id,
            'p_language_code': language_code,
            'p_level': int(level), # Integer'a çevirdiğimizden emin ol
            'p_score_increment': points_to_add
        }).execute()

        print(f"[submit_score] RPC upsert_level_progress completed successfully")

        # Toplam skoru dil bazlı yeniden hesapla (Profiles tablosu için)
        try:
            user_supabase.rpc('recalculate_total_score_for_user', {
                'p_user_id': user_id,
                'p_language_code': language_code
            }).execute()
            print(f"[submit_score] RPC recalculate_total_score_for_user completed successfully")
        except Exception as recalc_error:
            print(f"[submit_score] Warning: recalculate_total_score_for_user failed: {recalc_error}")
            # Don't fail the entire request if total score calculation fails
            # The level progress was successfully updated, which is the main goal

        # Madalya kontrolü vb. (bu kısım hala aynı kalabilir veya dil bazlı güncellenebilir)
        # Şimdilik sadece puanı kaydettiğimizden emin olalım.

        return jsonify(message="Score submitted and progress updated successfully."), 200

    except Exception as e:
        print(f"An error occurred in submit_score: {e}")
        return jsonify(error="An internal server error occurred."), 500

@progress_bp.route('/submit-mixed-rush-score', methods=['POST'])
def submit_mixed_rush_score():
    print(f"[submit_mixed_rush_score] Function called - checking user...")  # DEBUG: very early
    user, err = get_user_from_request(request)
    if err: 
        print(f"[submit_mixed_rush_score] User auth failed: {err}")  # DEBUG
        return err

    data = request.get_json()
    print(f"[submit_mixed_rush_score] Received data: {data}")  # DEBUG: log incoming data
    
    final_score = data.get('score')
    language_code = data.get('language') or data.get('lang') or 'en'  # Be flexible with field names

    print(f"[submit_mixed_rush_score] Parsed fields - score: {final_score}, language: {language_code}")  # DEBUG

    if not all([final_score is not None, language_code]):
        missing_fields = []
        if final_score is None: missing_fields.append('score')
        if not language_code: missing_fields.append('language/lang')
        print(f"[submit_mixed_rush_score] Missing fields: {missing_fields}")  # DEBUG
        return jsonify(error=f"Missing required fields: {', '.join(missing_fields)}"), 400
    
    try:
        # Use same user ID extraction pattern as submit_score
        user_id = user.id if hasattr(user, 'id') else user.get('id')
        print(f"[submit_mixed_rush_score] User ID: {user_id} (type: {type(user_id)})")
        print(f"[submit_mixed_rush_score] About to call update_mixed_rush_highscore RPC")
        
        # Create user-authenticated client like in submit_score
        auth_header = request.headers.get('Authorization')
        token = auth_header.split(' ', 1)[1].strip()
        if token.startswith('{'):
            try:
                import json
                parsed = json.loads(token)
                token = parsed.get('access_token') or parsed.get('accessToken') or parsed.get('token') or (parsed.get('data') or {}).get('access_token')
            except Exception:
                pass
        
        user_supabase = create_client(url, key)
        user_supabase.auth.session = {'access_token': token, 'refresh_token': '', 'user': user}
        
        user_supabase.rpc('update_mixed_rush_highscore', {
            'p_user_id': user_id,
            'p_language_code': language_code,
            'p_new_score': int(final_score)
        }).execute()
        
        print(f"[submit_mixed_rush_score] RPC update_mixed_rush_highscore completed successfully")
        return jsonify(message="Mixed Rush highscore updated successfully."), 200
    except Exception as e:
        print(f"An error occurred in submit_mixed_rush_score: {e}")
        return jsonify(error="An internal server error occurred."), 500