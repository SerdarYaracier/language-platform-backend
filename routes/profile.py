from flask import Blueprint, jsonify, request, current_app
from extensions import supabase

profile_bp = Blueprint('profile_bp', __name__, url_prefix='/api/profile')

@profile_bp.route('/', methods=['GET'])
def get_user_profile():
    try:
        auth_header = request.headers.get('Authorization', '')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify(error='Missing or invalid Authorization header'), 401

        token = auth_header.split(' ', 1)[1].strip()
        # get_user dönüş şekline göre kontrol
        user_res = supabase.auth.get_user(token)
        user = None
        if hasattr(user_res, 'user'):
            user = user_res.user
        elif isinstance(user_res, dict):
            user = user_res.get('user') or user_res.get('data')

        if not user:
            return jsonify(error='Invalid or expired token'), 401

        # RPC çağır ve normalize et
        rpc_res = supabase.rpc('get_user_profile_details', {'p_user_id': user.id}).execute()
        profile_data = None
        if getattr(rpc_res, 'data', None):
            profile_data = rpc_res.data
        elif isinstance(rpc_res, dict):
            profile_data = rpc_res.get('data') or rpc_res.get('body') or None

        # Fallback direct query
        if not profile_data:
            current_app.logger.info('[profile] RPC returned empty, falling back to profiles table')
            direct = supabase.table('profiles').select('id, username, avatar_url, total_score, mixed_rush_highscore').eq('id', user.id).single().execute()
            if getattr(direct, 'data', None):
                return jsonify(direct.data), 200
            elif isinstance(direct, dict) and direct.get('data'):
                return jsonify(direct.get('data')), 200
            else:
                return jsonify(error='Profile not found for user'), 404

        # profile_data olabilir: liste veya tek obje
        profile_obj = profile_data[0] if isinstance(profile_data, list) and profile_data else profile_data

        # ensure total_score present
        if profile_obj.get('total_score') is None:
            try:
                ts_res = supabase.table('profiles').select('total_score').eq('id', user.id).single().execute()
                if getattr(ts_res, 'data', None):
                    profile_obj['total_score'] = ts_res.data.get('total_score')
                elif isinstance(ts_res, dict) and ts_res.get('data'):
                    profile_obj['total_score'] = (ts_res.get('data') or {}).get('total_score')
            except Exception as e:
                current_app.logger.exception('[profile] total_score fallback failed')

        # ensure avatar_url present
        if profile_obj.get('avatar_url') is None:
            try:
                av_res = supabase.table('profiles').select('avatar_url').eq('id', user.id).single().execute()
                if getattr(av_res, 'data', None):
                    profile_obj['avatar_url'] = av_res.data.get('avatar_url')
                elif isinstance(av_res, dict) and av_res.get('data'):
                    profile_obj['avatar_url'] = (av_res.get('data') or {}).get('avatar_url')
            except Exception as e:
                current_app.logger.exception('[profile] avatar_url fallback failed')

        return jsonify(profile_obj), 200

    except Exception:
        current_app.logger.exception('Unhandled error in get_user_profile')
        return jsonify(error='An internal server error occurred'), 500

