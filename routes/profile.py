from flask import Blueprint, jsonify, request
from extensions import supabase
from supabase import create_client
import os

def get_user_from_request(request):
    """Extracts user from JWT in Authorization header, returns (user, error_response)"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or 'Bearer ' not in auth_header:
        return None, (jsonify(error="Authorization header is missing or malformed"), 401)
    jwt = auth_header.split(" ")[1]
    user_res = supabase.auth.get_user(jwt)
    if user_res.user is None:
        return None, (jsonify(error="Invalid or expired token"), 401)
    return user_res.user, None

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
    

# YENİ: Avatar URL'ini güncelleyen endpoint
# Compatibility route for older frontend upload path
@profile_bp.route('/upload-avatar', methods=['POST', 'OPTIONS'])
def upload_avatar():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    # Auth kontrolü
    auth_header = request.headers.get('Authorization')
    if not auth_header or 'Bearer ' not in auth_header:
        return jsonify(error="Authorization header is missing or malformed"), 401
    jwt = auth_header.split(' ')[1]
    try:
        user_res = supabase.auth.get_user(jwt)
    except Exception as e:
        print(f"token validation error: {e}")
        return jsonify(error="Token validation failed"), 401
    if not getattr(user_res, 'user', None):
        return jsonify(error="Invalid or expired token"), 401

    # Dosya kontrolü
    if 'file' not in request.files:
        return jsonify(error="file is required"), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify(error="No file selected"), 400

    try:
        import uuid
        # Dosya uzantısını al
        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'png'
        # Unique filename oluştur
        filename = f"avatars/{user_res.user.id}/{uuid.uuid4().hex}.{ext}"
        
        # Dosya nesnesini hazırla (dosya nesnesini doğrudan gönderiyoruz, bytes yerine)
        # rewind stream to start in case it was read earlier
        try:
            file.stream.seek(0)
        except Exception:
            pass
        file_obj = file.stream

        # Kullanıcının JWT'si ile yeni bir Supabase client oluştur
        user_supabase = create_client(
            os.environ.get("SUPABASE_URL"), 
            os.environ.get("SUPABASE_KEY")
        )
        # JWT'yi headers ile set et
        user_supabase.postgrest.auth(jwt)
        
        # Storage client için headers manuel olarak set et
        user_supabase.storage._client.headers["Authorization"] = f"Bearer {jwt}"

        # User context ile storage'a yükle
        # Some storage clients expect a file-like object, not raw bytes
        content_type = file.mimetype or None
        try:
            if content_type:
                upload_res = user_supabase.storage.from_('profiles').upload(filename, file_obj, {'content-type': content_type})
            else:
                upload_res = user_supabase.storage.from_('profiles').upload(filename, file_obj)
        except TypeError:
            # Fallback: older/newer client versions might expect raw bytes; read bytes and retry
            file.stream.seek(0)
            file_bytes = file.read()
            upload_res = user_supabase.storage.from_('profiles').upload(filename, file_bytes)
        print(f"Upload response: {upload_res}")
        
        # Public URL al
        public_url_res = user_supabase.storage.from_('profiles').get_public_url(filename)
        avatar_url = public_url_res['publicURL'] if isinstance(public_url_res, dict) else str(public_url_res)
        
        # Profile'ı güncelle
        supabase.table('profiles').update({'avatar_url': avatar_url}).eq('id', user_res.user.id).execute()
        
        return jsonify(avatar_url=avatar_url), 200
        
    except Exception as e:
        import traceback
        print(f"upload_avatar error: {e}")
        traceback.print_exc()
        return jsonify(error="An internal server error occurred"), 500