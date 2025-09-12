from flask import Blueprint, jsonify, request
from extensions import supabase

progress_bp = Blueprint('progress_bp', __name__, url_prefix='/api/progress')

POINTS_MAP = {1: 5, 2: 7, 3: 10, 4: 15, 5: 17}


def _get_user_from_auth_header(req):
    auth_header = req.headers.get('Authorization')
    if not auth_header or ' ' not in auth_header:
        return None, (jsonify(error="Authorization header missing or malformed"), 401)
    token = auth_header.split(' ', 1)[1]
    # tolerate JSON blob token (frontend bug) like '{"access_token":"..."}'
    token = token.strip()
    if token.startswith('{'):
        try:
            import json
            parsed = json.loads(token)
            token = parsed.get('access_token') or parsed.get('accessToken') or parsed.get('token') or (parsed.get('data') or {}).get('access_token')
            print(f"[progress] extracted token from JSON blob: {'yes' if token else 'no'}")
        except Exception as e:
            print(f"[progress] failed to parse token JSON: {e}")
    try:
        user_resp = supabase.auth.get_user(token)
    except Exception as e:
        print(f"[progress] supabase.auth.get_user exception: {e}")
        return None, (jsonify(error="Failed to validate token"), 401)

    user = None
    if hasattr(user_resp, 'user'):
        user = user_resp.user
    elif isinstance(user_resp, dict):
        user = user_resp.get('user') or (user_resp.get('data') and user_resp['data'].get('user'))

    if not user:
        return None, (jsonify(error="Invalid or expired token"), 401)

    return user, None


@progress_bp.route('/submit-score', methods=['POST'])
def submit_score():
    user, err = _get_user_from_auth_header(request)
    if err:
        return err

    try:
        data = request.get_json() or {}
        level = data.get('level')
        category_slug = data.get('categorySlug') or data.get('category')

        if level is None or not category_slug:
            return jsonify(error="Missing required fields: level, categorySlug"), 400

        points_to_add = POINTS_MAP.get(int(level), 0)

        # Find category id
        cat_res = supabase.table('categories').select('id').eq('slug', category_slug).execute()
        if not cat_res.data:
            return jsonify(error=f"Category '{category_slug}' not found"), 404
        category_id = cat_res.data[0]['id']

        # Use Supabase RPCs - let them handle the complexity
        supabase.rpc('upsert_category_progress', {
            'p_user_id': user.id,
            'p_category_id': category_id,
            'p_score_increment': points_to_add
        }).execute()
        
        supabase.rpc('recalculate_total_score_for_user', {'p_user_id': user.id}).execute()
        supabase.rpc('check_and_award_achievements_for_user', {'p_user_id': user.id}).execute()

        return jsonify(message="Score updated successfully"), 200

    except Exception as e:
        print(f"Error in submit_score: {e}")
        return jsonify(error="Internal server error"), 500


@progress_bp.route('/submit-mixed-rush-question', methods=['POST'])
def submit_mixed_rush_question():
    """Tek bir Mixed Rush sorusu için puan ekleme (level + categorySlug gerekli)"""
    user, err = _get_user_from_auth_header(request)
    if err:
        return err

    try:
        data = request.get_json() or {}
        level = data.get('level')
        category_slug = data.get('categorySlug') or data.get('category')
        
        if level is None or not category_slug:
            return jsonify(error="Missing required fields: level, categorySlug"), 400

        points_to_add = POINTS_MAP.get(int(level), 0)
        
        # Find category id
        cat_res = supabase.table('categories').select('id').eq('slug', category_slug).execute()
        if not cat_res.data:
            return jsonify(error=f"Category '{category_slug}' not found"), 404
        category_id = cat_res.data[0]['id']

        # Use Supabase RPCs - simple and reliable
        supabase.rpc('upsert_category_progress', {
            'p_user_id': user.id,
            'p_category_id': category_id,
            'p_score_increment': points_to_add
        }).execute()
        
        supabase.rpc('recalculate_total_score_for_user', {'p_user_id': user.id}).execute()
        supabase.rpc('check_and_award_achievements_for_user', {'p_user_id': user.id}).execute()

        return jsonify(message=f"Mixed Rush question scored: +{points_to_add} points"), 200

    except Exception as e:
        print(f"Error in submit_mixed_rush_question: {e}")
        return jsonify(error="Internal server error"), 500


@progress_bp.route('/submit-mixed-rush-final', methods=['POST'])
def submit_mixed_rush_final():
    """Mixed Rush oyunu bitiminde final score kaydetme"""
    user, err = _get_user_from_auth_header(request)
    if err:
        return err

    try:
        data = request.get_json() or {}
        final_score = data.get('score') or data.get('finalScore')
        
        if final_score is None:
            return jsonify(error="Missing required field: score"), 400

        final_score = int(final_score)
        if final_score < 0:
            return jsonify(error="Score cannot be negative"), 400

        # Use the existing RPC - much simpler and more reliable!
        result = supabase.rpc('update_mixed_rush_highscore', {
            'p_user_id': user.id,
            'p_new_score': final_score
        }).execute()
        
        # The RPC handles the GREATEST logic, we just need to return appropriate message
        return jsonify(message=f"Mixed Rush final score: {final_score}"), 200

    except Exception as e:
        print(f"Error in submit_mixed_rush_final: {e}")
        return jsonify(error="Internal server error"), 500


@progress_bp.route('/submit-mixed-rush-score', methods=['POST'])
def submit_mixed_rush_score():
    """Geriye uyumluluk için - eski frontend'i destekler"""
    user, err = _get_user_from_auth_header(request)
    if err:
        return err

    try:
        data = request.get_json() or {}
        level = data.get('level')
        category_slug = data.get('categorySlug') or data.get('category')
        
        # Eğer level ve category varsa, bireysel soru puanlaması
        if level is not None and category_slug:
            return submit_mixed_rush_question()
        
        # Değilse final score
        final_score = data.get('score')
        if final_score is None:
            return jsonify(error="Missing required field: 'score'"), 400

        # 1. Veritabanındaki hazır ve optimize edilmiş RPC fonksiyonunu kullanarak en yüksek skoru güncelle.
        supabase.rpc('update_mixed_rush_highscore', {
            'p_user_id': user.id,
            'p_new_score': int(final_score)
        }).execute()
        
        # --- KRİTİK DEĞİŞİKLİK BURADA ---
        # 2. YENİ: Skor güncellendikten sonra madalya kontrolünü tetikle.
        # Bu, 'mixed_rush_highscore' trigger türüne sahip madalyaların kazanılmasını sağlar.
        supabase.rpc('check_and_award_achievements_for_user', {
            'p_user_id': user.id
        }).execute()

        return jsonify(message="Mixed Rush highscore updated successfully"), 200

    except Exception as e:
        print(f"Error in submit_mixed_rush_score: {e}")
        return jsonify(error="Internal server error"), 500