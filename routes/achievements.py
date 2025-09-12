from flask import Blueprint, jsonify, request
from extensions import supabase

achievements_bp = Blueprint('achievements_bp', __name__, url_prefix='/api/achievements')

@achievements_bp.route('/', methods=['GET'])
def get_user_achievements():
    try:
        auth_header = request.headers.get('Authorization')
        jwt = auth_header.split(" ")[1]
        user = supabase.auth.get_user(jwt).user
        if not user: return jsonify(error="Invalid user"), 401

        # Kazanılan madalyaları, madalya bilgileriyle birleştirerek çek
        response = supabase.table('user_achievements').select('earned_at, achievements(*)').eq('user_id', user.id).execute()

        return jsonify(response.data)
    except Exception as e:
        print(f"Error in get_user_achievements: {e}")
        return jsonify(error="An internal server error occurred"), 500