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
    # Authenticate
    user, err = _get_user_from_auth_header(request)
    if err:
        return err

    try:
        data = request.get_json() or {}
        print(f"[progress] submit-score request json: {data}")
        print(f"[progress] Authorization header sample: {str(request.headers.get('Authorization'))[:80]}")
        level = data.get('level')
        # accept several possible param names from frontend
        category_slug = data.get('categorySlug') or data.get('category') or data.get('category_slug') or data.get('categoryId')

        if level is None or not category_slug:
            return jsonify(error="Missing required fields: level, categorySlug"), 400

        try:
            points_to_add = POINTS_MAP.get(int(level), 0)
        except Exception:
            points_to_add = 0

        # Find category id
        try:
            cat_res = supabase.table('categories').select('id').eq('slug', category_slug).execute()
        except Exception as e:
            print(f"[progress] category lookup failed: {e}")
            return jsonify(error="Failed to lookup category"), 500

        if not getattr(cat_res, 'data', None):
            return jsonify(error=f"Category with slug '{category_slug}' not found."), 404
        category_id = cat_res.data[0]['id']

        # upsert category progress (best-effort)
        try:
            upsert_res = supabase.rpc('upsert_category_progress', {
                'p_user_id': user.id,
                'p_category_id': category_id,
                'p_score_increment': points_to_add
            }).execute()
            print(f"[progress] upsert_category_progress: {upsert_res}")
        except Exception as e:
            print(f"[progress] upsert_category_progress failed: {e}")

        # Bir kategoriye puan eklendikten hemen sonra...
        try:
            recalc_res = supabase.rpc('recalculate_total_score_for_user', {
                'p_user_id': user.id
            }).execute()
            print(f"[progress] recalculate_total_score_for_user: {recalc_res}")
        except Exception as e:
            print(f"[progress] recalculate_total_score_for_user failed: {e}")

        # check and award achievements (best-effort)
        try:
            ach_res = supabase.rpc('check_and_award_achievements_for_user', {'p_user_id': user.id}).execute()
            print(f"[progress] check_and_award_achievements_for_user: {ach_res}")
        except Exception as e:
            print(f"[progress] achievements RPC failed: {e}")

        return jsonify(message="Score updated successfully"), 200

    except Exception as e:
        print(f"Error in submit_score: {e}")
        return jsonify(error="An internal server error occurred"), 500