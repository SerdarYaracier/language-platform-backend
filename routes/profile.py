from flask import Blueprint, jsonify, request
from extensions import supabase

profile_bp = Blueprint('profile_bp', __name__, url_prefix='/api/profile')

# GİRİŞ YAPMIŞ KULLANICININ KENDİ PROFİLİ
@profile_bp.route('/', methods=['GET'])
def get_user_profile():
    """Giriş yapmış kullanıcının kendi tam profilini getirir."""
    try:
        # 1. Kullanıcıyı doğrula
        auth_header = request.headers.get('Authorization')
        if not auth_header or 'Bearer ' not in auth_header:
            return jsonify(error="Authorization header is missing or malformed"), 401
        
        jwt = auth_header.split(" ")[1]
        user_res = supabase.auth.get_user(jwt)
        
        if user_res.user is None:
            return jsonify(error="Invalid or expired token"), 401
        
        user_id = user_res.user.id
        
        # 2. Veritabanı fonksiyonunu çağır
        response = supabase.rpc('get_full_profile_by_id', {'p_user_id': user_id}).execute()

        if not response.data or not response.data[0].get('profile'):
            return jsonify(error="Profile not found for current user"), 404

        return jsonify(response.data[0])
        
    except Exception as e:
        print(f"Error in get_user_profile: {e}")
        return jsonify(error="An internal server error occurred"), 500

# HERKESE AÇIK PROFİL (LİDERLİK TABLOSU İÇİN)
@profile_bp.route('/<username>', methods=['GET'])
def get_public_profile(username):
    """Username'e göre bir kullanıcının herkese açık tam profilini getirir."""
    try:
        # 1. Önce username'den user_id'yi bul
        user_id_res = supabase.table('profiles').select('id').eq('username', username).single().execute()
        if not user_id_res.data:
            return jsonify(error=f"Profile not found for username: {username}"), 404
        
        user_id = user_id_res.data['id']
        
        # 2. Veritabanı fonksiyonunu çağır
        response = supabase.rpc('get_full_profile_by_id', {'p_user_id': user_id}).execute()

        if not response.data or not response.data[0].get('profile'):
            return jsonify(error="Profile data incomplete for user"), 404

        return jsonify(response.data[0])
    except Exception as e:
        print(f"Error in get_public_profile: {e}")
        return jsonify(error="An internal server error occurred"), 500