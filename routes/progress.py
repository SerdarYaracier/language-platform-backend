from flask import Blueprint, jsonify, request
from extensions import supabase

progress_bp = Blueprint('progress_bp', __name__, url_prefix='/api/progress')

POINTS_MAP = { 1: 5, 2: 7, 3: 10, 4: 15, 5: 17 }

# Artık GAME_SCORE_COLUMNS haritasına ihtiyacımız yok.

# submit_score fonksiyonunun doğru olduğundan emin olalım
@progress_bp.route('/submit-score', methods=['POST'])
def submit_score():
    try:
        # ... kullanıcı doğrulama ve veri alma kısmı ...
        # Örnek: Kullanıcı kimliğini request veya oturumdan alın
        user_id = request.json.get('user_id')
        if not user_id:
            return jsonify(error="user_id is required"), 400

        # 1. Kategori bazlı skoru güncelle
        supabase.rpc('upsert_category_progress', { ... }).execute()

        # 2. Toplam skoru "YAZICI" fonksiyon ile baştan hesapla
        # 3. Madalyaları kontrol et
        supabase.rpc('check_and_award_achievements_for_user', {
            'p_user_id': user_id
        }).execute()
        # 3. Madalyaları kontrol et
        supabase.rpc('check_and_award_achievements_for_user', {
            'p_user_id': user_id
        }).execute()

        return jsonify(message="Score updated successfully"), 200
    except Exception as e:
        # ... hata yönetimi ...
        print(f"Error in submit_score: {e}")
        return jsonify(error=str(e)), 500