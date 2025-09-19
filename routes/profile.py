from flask import Blueprint, jsonify, request
from extensions import supabase
from supabase import create_client
import os
import traceback
import uuid

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

        # Supabase RPC'leri liste içinde tek bir dict döndürür
        if not response.data or not response.data[0]:
            return jsonify(error="Profile not found or data incomplete for current user"), 404
        
        # RPC'den dönen veriyi doğrudan JSON olarak gönder
        # Bu, profile, game_scores ve achievements'ı içeren bir JSON objesi olacaktır.
        return jsonify(response.data[0])
        
    except Exception as e:
        print(f"Error in get_user_profile: {e}")
        import traceback
        traceback.print_exc()
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

        if not response.data or not response.data[0]:
            return jsonify(error="Profile data incomplete for user"), 404

        # RPC'den dönen veriyi doğrudan JSON olarak gönder
        return jsonify(response.data[0])
    except Exception as e:
        print(f"Error in get_public_profile: {e}")
        import traceback
        traceback.print_exc()
        return jsonify(error="An internal server error occurred"), 500
    

# YENİ: Avatar URL'ini güncelleyen endpoint
# Compatibility route for older frontend upload path
@profile_bp.route('/upload-avatar', methods=['POST', 'OPTIONS'])
@profile_bp.route('/avatar', methods=['POST', 'OPTIONS'])
def upload_avatar():
    # Basit OPTIONS (CORS preflight) desteği
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    # --- Debug: incoming request metadata (temporary; remove in prod if noisy) ---
    try:
        print("---- upload-avatar request start ----")
        print("Content-Type:", request.content_type)
        print("Headers:", dict(request.headers))
        print("Form keys:", list(request.form.keys()))
        print("Files keys:", list(request.files.keys()))
        print("Has JSON:", request.is_json)
        print("JSON (silent):", request.get_json(silent=True))
        print("---- upload-avatar request end ----")
    except Exception as _:
        # swallow debug print errors
        pass

    # Auth header required
    auth_header = request.headers.get('Authorization') or request.headers.get('authorization')
    if not auth_header or 'Bearer ' not in auth_header:
        return jsonify(error="Authorization header is missing or malformed"), 401
    jwt = auth_header.split(' ')[1]

    # Validate token and get user id (robust to supabase client return shapes)
    try:
        user_res = supabase.auth.get_user(jwt)
        # supabase-py versions differ; try to pull user id from known shapes
        user_id = None
        # shape: result.data.user
        try:
            user_id = (user_res.get('data') or {}).get('user', {}).get('id')
        except Exception:
            pass
        # fallback shape: user_res.user.id
        if not user_id:
            try:
                user_obj = getattr(user_res, 'user', None) or getattr(user_res, 'data', {}).get('user', None)
                user_id = getattr(user_obj, 'id', None) if user_obj else None
            except Exception:
                user_id = None
        if not user_id:
            return jsonify(error="Invalid or expired token, or user ID not found"), 401
    except Exception as e:
        print(f"Token validation error: {e}")
        traceback.print_exc()
        return jsonify(error="Token validation failed"), 401

    # 1) JSON path: placeholder/external URL update
    if request.is_json:
        body = request.get_json(silent=True) or {}
        if 'avatar_url' in body:
            new_avatar_url = body.get('avatar_url')
            if not new_avatar_url:
                return jsonify(error="avatar_url is empty"), 400
            try:
                supabase.table('profiles').update({'avatar_url': new_avatar_url}).eq('id', user_id).execute()
                return jsonify(avatar_url=new_avatar_url), 200
            except Exception as e:
                print(f"Update avatar_url from static URL failed: {e}")
                traceback.print_exc()
                return jsonify(error="Failed to update avatar URL"), 500

    # 2) Multipart/form-data path: uploaded file
    # Accept several possible field names
    file_field = None
    for candidate in ('file', 'avatar', 'image', 'upload'):
        if candidate in request.files:
            file_field = candidate
            break

    if file_field:
        file = request.files.get(file_field)
        if not file or file.filename == '':
            return jsonify(error="No file selected"), 400

        try:
            # Normalize filename / extension
            ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'png'
            # Build path in storage (do NOT duplicate bucket name)
            # When using supabase.storage.from_('avatars'), the upload path should be relative to the bucket.
            storage_path = f"{user_id}/{uuid.uuid4().hex}.{ext}"

            # Ensure stream at start and read bytes
            try:
                file.stream.seek(0)
            except Exception:
                pass
            file_bytes = file.read()
            content_type = file.mimetype or 'application/octet-stream'

            # Upload to Supabase Storage - do the upload as the authenticated user
            # Create a user-scoped client and set the Authorization header so RLS policies see the correct user
            try:
                user_supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
                # Set Authorization header for storage requests to the user's JWT
                try:
                    user_supabase.storage._client.headers["Authorization"] = f"Bearer {jwt}"
                except Exception:
                    # older/newer client shapes
                    try:
                        user_supabase.postgrest._client.headers["Authorization"] = f"Bearer {jwt}"
                    except Exception:
                        pass

                upload_res = user_supabase.storage.from_('avatars').upload(
                    storage_path,
                    file_bytes,
                    file_options={'content-type': content_type, 'x-upsert': 'true'}
                )
            except Exception as upload_exc:
                print("Supabase upload failed:", upload_exc)
                raise
            print("Supabase upload response:", upload_res)

            # Get public URL - return shape varies by supabase-py version
            public_url_res = supabase.storage.from_('avatars').get_public_url(storage_path)
            avatar_url = None
            # normalize common shapes
            try:
                if isinstance(public_url_res, dict):
                    avatar_url = public_url_res.get('publicUrl') or public_url_res.get('public_url') or public_url_res.get('url')
                else:
                    # Some client versions return an object with .get('publicUrl') or a simple string
                    avatar_url = str(public_url_res)
            except Exception:
                avatar_url = str(public_url_res)

            if not avatar_url:
                # Last resort: try to construct URL from known bucket base (if you host under a fixed domain)
                # WARNING: adjust this to match your Supabase project if needed, or prefer explicit get_public_url result.
                try:
                    supabase_base = supabase.storage.base_url if hasattr(supabase.storage, 'base_url') else None
                    if supabase_base:
                        avatar_url = f"{supabase_base}/object/public/avatars/{storage_path}"
                except Exception:
                    avatar_url = None

            if not avatar_url:
                print("Warning: could not determine public avatar URL from supabase response:", public_url_res)

            # Update profile table
            supabase.table('profiles').update({'avatar_url': avatar_url}).eq('id', user_id).execute()

            return jsonify(avatar_url=avatar_url), 200

        except Exception as e:
            traceback.print_exc()
            print(f"File upload and avatar update error: {e}")
            return jsonify(error="An internal server error occurred during avatar upload"), 500

    # No JSON avatar_url and no files
    return jsonify(error="No avatar_url or file provided"), 400