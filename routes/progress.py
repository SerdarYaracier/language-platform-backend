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

    try:
        data = request.get_json() or {}
        print(f"[submit_score] Received payload: {data}")
        level = data.get('level')
        game_slug = data.get('gameSlug') or data.get('game') or data.get('gameType')
        category_slug = data.get('categorySlug') or data.get('category')
        language_code = data.get('language') or data.get('lang') or 'en'
        points_to_add = data.get('points', 5)

        missing = []
        if level is None:
            missing.append('level')
        if not category_slug:
            missing.append('categorySlug')
        if missing:
            print(f"[submit_score] Missing fields: {missing}")
            return jsonify(error=f"Missing required fields: {', '.join(missing)}"), 400

        cat_res = supabase.table('categories').select('id').eq('slug', category_slug).single().execute()
        if not cat_res.data:
            return jsonify(error=f"Category with slug '{category_slug}' not found."), 404
        category_id = cat_res.data['id']

        # 1. Seviye bazlı skoru güncelle
        supabase.rpc('upsert_level_progress', {
            'p_user_id': user.id,
            'p_category_id': int(category_id),
            'p_language_code': language_code,
            'p_level': int(level),
            'p_score_increment': int(points_to_add)
        }).execute()

        # 2. Toplam skoru yeniden hesapla (SADECE KULLANICI ID'si gönderiliyor)
        # `profiles.total_score` INTEGER olduğu için dil bazlı parametreye gerek yok.
        supabase.rpc('recalculate_total_score_for_user', {
            'p_user_id': user.id
        }).execute()

        # 3. Madalyaları kontrol et
        # Eğer `check_and_award_achievements_for_user` fonksiyonunuz varsa, bu çağrı kalabilir.
        # supabase.rpc('check_and_award_achievements_for_user', {'p_user_id': user.id}).execute()

        return jsonify(message="Score updated successfully"), 200

    except Exception as e:
        print(f"Error in submit_score: {e}")
        import traceback
        traceback.print_exc()
        return jsonify(error="An internal server error occurred."), 500

@progress_bp.route('/submit-mixed-rush-score', methods=['POST'])
def submit_mixed_rush_score():
    print(f"[submit_mixed_rush_score] Function called - checking user...")
    user, err = get_user_from_request(request)
    if err: 
        print(f"[submit_mixed_rush_score] User auth failed: {err}")
        return err

    data = request.get_json()
    print(f"[submit_mixed_rush_score] Received data: {data}")
    
    final_score = data.get('score')
    # language_code burada artık doğrudan kullanılmayacak, ancak frontend'den gelmesi problem değil
    # language_code = data.get('language') or data.get('lang') or 'en' 

    print(f"[submit_mixed_rush_score] Parsed fields - score: {final_score}") # language_code'u logdan çıkarabiliriz

    if final_score is None: # Sadece skoru kontrol ediyoruz
        print(f"[submit_mixed_rush_score] Missing field: score")
        return jsonify(error=f"Missing required field: score"), 400
    
    try:
        user_id = user.id if hasattr(user, 'id') else user.get('id')
        print(f"[submit_mixed_rush_score] User ID: {user_id} (type: {type(user_id)})")
        print(f"[submit_mixed_rush_score] About to call update_mixed_rush_highscore RPC")
        
        # Eğer bu kısımda problem yaşanıyorsa, `user_supabase` yerine global `supabase` client kullanmayı deneyebiliriz.
        # Ancak RLS politikaları nedeniyle `user_supabase` ile devam etmek genellikle daha güvenlidir.
        auth_header = request.headers.get('Authorization')
        token = auth_header.split(' ', 1)[1].strip()
        if token.startswith('{'):
            try:
                import json
                parsed = json.loads(token)
                token = parsed.get('access_token') or parsed.get('accessToken') or parsed.get('token') or (parsed.get('data') or {}).get('access_token')
            except Exception:
                pass
        
        user_supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
        user_supabase.auth.session = {'access_token': token, 'refresh_token': '', 'user': user}
        
        try:
            mixed_rush_result = user_supabase.rpc('update_mixed_rush_highscore', {
                'p_user_id': user_id,
                # 'p_language_code': language_code, # BU SATIR SİLİNMELİ
                'p_new_score': int(final_score)
            }).execute()
            
            print(f"[submit_mixed_rush_score] RPC update_mixed_rush_highscore completed successfully")
            print(f"[submit_mixed_rush_score] Mixed rush result: {mixed_rush_result.data}")
            
            # Doğrulama için profiles tablosundan `mixed_rush_highscore` değerini çek
            profile_check = user_supabase.table('profiles').select('mixed_rush_highscore').eq('id', user_id).execute()
            if profile_check.data:
                current_mixed_rush_highscore = profile_check.data[0]['mixed_rush_highscore']
                print(f"[submit_mixed_rush_score] Verified mixed rush highscore: {current_mixed_rush_highscore}")
                
            return jsonify(message="Mixed Rush highscore updated successfully."), 200
            
        except Exception as mixed_rush_error:
            print(f"[submit_mixed_rush_score] ERROR: update_mixed_rush_highscore failed: {mixed_rush_error}")
            print(f"[submit_mixed_rush_score] Error type: {type(mixed_rush_error)}")
            if hasattr(mixed_rush_error, 'message'):
                print(f"[submit_mixed_rush_score] Error message: {mixed_rush_error.message}")
            return jsonify(error="Failed to update Mixed Rush highscore"), 500
            
    except Exception as e:
        print(f"An error occurred in submit_mixed_rush_score: {e}")
        import traceback
        traceback.print_exc()
        return jsonify(error="An internal server error occurred."), 500