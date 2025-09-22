import os
import random
import uuid
import json # JSON verilerini işlemek için
from flask import Blueprint, request, jsonify
from supabase import create_client, Client
import traceback

duel_bp = Blueprint('duel', __name__,url_prefix='/api/duel')


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Yardımcı Fonksiyonlar ---

# JWT'den kullanıcı ID'sini çıkarmak için yeniden kullanılabilir fonksiyon
def get_user_id_from_jwt():
    auth_header = request.headers.get('Authorization')
    if not auth_header or 'Bearer ' not in auth_header:
        return None, "Authorization header is missing or malformed"
    jwt = auth_header.split(' ')[1]
    try:
        user_res = supabase.auth.get_user(jwt)
        user_id = getattr(getattr(user_res, 'user', None), 'id', None)
        if not user_id:
            return None, "Invalid or expired token, or user ID not found"
        return user_id, None
    except Exception as e:
        print(f"Token validation error: {e}")
        return None, "Token validation failed"

# Soru çekme mantığı
def get_duel_questions(difficulty_level):
    try:
        print(f"DEBUG: Fetching questions for difficulty_level: {difficulty_level}")
        # Query the exact columns you specified: id(int), game_type_id(int), category_id(int), level(int), content(jsonb)
        query = supabase.table('game_items').select('id, game_type_id, category_id, level, content')
        if difficulty_level > 0:
            query = query.eq('level', difficulty_level)

        # Fetch matching questions
        response = query.execute()
        all_questions = response.data
        print(f"DEBUG: Found {len(all_questions) if all_questions else 0} total questions.")

        if not all_questions:
            return None, f"No questions found for difficulty level {difficulty_level}."

        # Normalize JSONB content field into Python objects (if it's returned as string)
        normalized = []
        for r in all_questions:
            item = dict(r)
            if isinstance(item.get('content'), str):
                try:
                    item['content'] = json.loads(item['content'])
                except Exception:
                    # leave as string if parsing fails
                    pass
            normalized.append(item)

        # Randomly select up to 20 questions
        selected_questions = random.sample(normalized, min(20, len(normalized)))
        print(f"DEBUG: Selected {len(selected_questions)} questions.")

        return selected_questions, None
    except Exception as e:
        print(f"ERROR in get_duel_questions: {e}")
        traceback.print_exc() # Hata izini terminale yazdır
        return None, f"Database error fetching questions: {str(e)}"

# --- Endpoint'ler ---

# 1. Duel Oluşturma (Meydan Okuma) ve İlk Oyuncunun Oynaması
@duel_bp.route('/create-duel', methods=['POST'])
def create_and_play_duel():
    user_id, error = get_user_id_from_jwt()
    if error:
        return jsonify(error=error), 401

    data = request.get_json()
    challenged_id = data.get('challenged_id')
    difficulty_level = data.get('difficulty_level') # 1-5 veya 0 (ALL)
    challenger_score = data.get('challenger_score')
    challenger_time_taken = data.get('challenger_time_taken')
    challenger_answers = data.get('challenger_answers') # Cevaplar daha sonra kontrol için tutulabilir
    frontend_questions = data.get('questions', [])  # Frontend'ten gelen sorular

    if not all([challenged_id, difficulty_level is not None, challenger_score is not None, challenger_time_taken is not None, challenger_answers is not None]):
        return jsonify(error="Missing required duel parameters"), 400
    
    # Kendi kendine meydan okumayı engelle
    if str(user_id) == str(challenged_id):
        return jsonify(error="Cannot challenge yourself"), 400

    if not (0 <= difficulty_level <= 5):
        return jsonify(error="Invalid difficulty level. Must be 0-5."), 400

    try:
        # Eğer frontend sorular gönderiyorsa onları kullan, yoksa backend'te rastgele seç
        if frontend_questions and len(frontend_questions) >= 20:
            print(f"DEBUG: Using {len(frontend_questions)} questions from frontend")
            selected_questions = frontend_questions[:20]  # İlk 20 soruyu al
            
            # Frontend'ten gelen soruları normalize et (sadece gerekli alanlar)
            normalized_questions = []
            for q in selected_questions:
                # Frontend'te nested (game_item) veya flat yapı olabilir
                if 'game_item' in q:
                    item = {
                        'id': q['game_item']['id'],
                        'game_type_id': q['game_item']['game_type_id'],
                        'category_id': q['game_item']['category_id'],
                        'level': q['game_item']['level'],
                        'content': q['game_item']['content']
                    }
                else:
                    item = {
                        'id': q['id'],
                        'game_type_id': q['game_type_id'],
                        'category_id': q['category_id'],
                        'level': q['level'],
                        'content': q['content']
                    }
                normalized_questions.append(item)
            selected_questions = normalized_questions
        else:
            print(f"DEBUG: Frontend questions insufficient ({len(frontend_questions)}), generating new ones")
            # 1. Duel için 20 rastgele soru çek
            selected_questions, q_error = get_duel_questions(difficulty_level)
            if q_error:
                return jsonify(error=q_error), 500
            
            if len(selected_questions) < 20:
                 return jsonify(error=f"Not enough questions ({len(selected_questions)}) for difficulty level {difficulty_level}"), 500


        # 2. Yeni bir duel kaydı oluştur
        duel_data = {
            'challenger_id': str(user_id), # Supabase UUID'yi string bekler
            'challenged_id': str(challenged_id),
            'difficulty_level': difficulty_level,
            'status': 'challenger_completed', # Challenger ilk oynamayı tamamladığı için
            'challenger_score': challenger_score,
            'challenger_time_taken': challenger_time_taken,
            'challenger_completed_at': 'now()' # Supabase'in 'now()' fonksiyonunu kullan
        }
        
        insert_duel_response = supabase.table('duels').insert(duel_data).execute()
        new_duel = insert_duel_response.data[0]
        duel_id = new_duel['id']

        # 3. Seçilen soruları duel_questions tablosuna kaydet
        questions_to_insert = []
        for i, q in enumerate(selected_questions):
            questions_to_insert.append({
                'duel_id': duel_id,
                'game_item_id': q['id'], # game_items.id BIGINT olduğu için doğrudan kullan
                'question_order': i + 1
            })
        
        supabase.table('duel_questions').insert(questions_to_insert).execute()

        # TODO: Challenger'ın verdiği cevapları kaydetmek için ayrı bir tablo (duel_answers) düşünebiliriz.
        # Şimdilik sadece puan ve süre kaydediliyor.

        # Challenger'a da aynı soruları döndür (frontend tutarsızlığını önlemek için)
        formatted_questions = []
        for q in selected_questions:
            formatted_questions.append({
                "game_item": {
                    "id": q['id'],
                    "game_type_id": q['game_type_id'], 
                    "category_id": q['category_id'],
                    "level": q['level'],
                    "content": q['content']
                }
            })

        return jsonify({
            "message": "Duel created and challenger's score recorded successfully",
            "duel_id": duel_id,
            "challenger_score": challenger_score,
            "difficulty_level": difficulty_level,
            "questions": formatted_questions  # Challenger'ın kullanması gereken sorular
        }), 201

    except Exception as e:
        print(f"Error creating or playing duel: {e}")
        traceback.print_exc()
        return jsonify(error="An internal server error occurred"), 500


# 2. Bekleyen ve Tamamlanmış Duelleri Listeleme
@duel_bp.route('/my-duels', methods=['GET'])
def get_my_duels():
    user_id, error = get_user_id_from_jwt()
    if error:
        return jsonify(error=error), 401

    try:
        # Hem challenger hem de challenged olduğumuz duelleri çek
        # profiles tablosundan username ve avatar_url'i de çekmek için join kullanıyoruz
        response = supabase.table('duels').select(
            '*, challenger:challenger_id(username, avatar_url), challenged:challenged_id(username, avatar_url)'
        ).or_(f'challenger_id.eq.{user_id},challenged_id.eq.{user_id}').order('created_at', desc=True).execute()
        
        duels_data = response.data

        # Duelleri bekleyen ve tamamlanmış olarak ayrıştırabiliriz (isteğe bağlı)
        pending_challenges_for_me = [] # Bana gelen ve benim oynamam gereken dueller
        my_sent_challenges = []       # Benim gönderdiğim ve cevap bekleyenler
        completed_duels = []          # Bitmiş dueller

        for duel in duels_data:
            if duel['status'] == 'completed':
                completed_duels.append(duel)
            elif duel['challenger_id'] == str(user_id) and duel['status'] == 'challenger_completed':
                my_sent_challenges.append(duel) # Benim başlattığım ve karşı tarafın oynamasını bekleyenler
            elif duel['challenged_id'] == str(user_id) and duel['status'] == 'challenger_completed':
                pending_challenges_for_me.append(duel) # Bana gelen ve benim oynamam gerekenler
            # 'pending' status'u challenger'ın daha oynamadığı durumlar için, şu an kullanılmıyor.

        return jsonify({
            "pending_challenges_for_me": pending_challenges_for_me,
            "my_sent_challenges": my_sent_challenges,
            "completed_duels": completed_duels
        }), 200

    except Exception as e:
        print(f"Error fetching duels: {e}")
        traceback.print_exc()
        return jsonify(error="An internal server error occurred"), 500


# 3. Bir Duel'in Sorularını Çekme (Challenged Oynayacak)
@duel_bp.route('/duel-questions/<uuid:duel_id>', methods=['GET'])
def get_duel_game_questions(duel_id):
    user_id, error = get_user_id_from_jwt()
    if error:
        return jsonify(error=error), 401

    try:
        # Kullanıcının bu duel'in bir parçası olup olmadığını kontrol et
        duel_check_response = supabase.table('duels').select('id, challenger_id, challenged_id, status').eq('id', str(duel_id)).single().execute()
        duel_check_data = duel_check_response.data

        if not duel_check_data:
            return jsonify(error="Duel not found"), 404

        if str(user_id) not in [duel_check_data['challenger_id'], duel_check_data['challenged_id']]:
            return jsonify(error="You are not authorized to access this duel"), 403
        
        # Eğer challenged oynayacaksa, challenger'ın tamamladığından emin ol
        if str(user_id) == duel_check_data['challenged_id'] and duel_check_data['status'] != 'challenger_completed':
            return jsonify(error="Challenger has not completed this duel yet"), 400

        # Duel'in sorularını ve detaylarını çek
        response = supabase.table('duel_questions').select(
            'id, question_order, game_item:game_item_id(id, game_type_id, category_id, level, content)'
        ).eq('duel_id', str(duel_id)).order('question_order', desc=False).execute()

        questions_data = response.data
        if not questions_data:
            return jsonify(error="No questions found for this duel"), 404
        
        # Frontend'e sadece gerekli soru verilerini gönder
        formatted_questions = []
        for dq in questions_data:
            if dq['game_item']:
                formatted_questions.append({
                    "duel_question_id": dq['id'], # duel_questions tablosundaki id
                    "game_item_id": dq['game_item']['id'], # game_items tablosundaki id
                    "question_order": dq['question_order'],
                    "game_type_id": dq['game_item']['game_type_id'],
                    "category_id": dq['game_item']['category_id'],
                    "level": dq['game_item']['level'],
                    "content": dq['game_item']['content']
                    # NOT: Normalde doğru cevabı göndermeyiz. Cevap kontrolü backend'de yapılır.
                    # Frontend'e sadece gösterilecek verileri gönderiyoruz.
                })

        return jsonify(questions=formatted_questions), 200

    except Exception as e:
        print(f"Error fetching duel questions for game: {e}")
        traceback.print_exc()
        return jsonify(error="An internal server error occurred"), 500


# 4. Duel Sonucunu Kaydetme ve Tamamlama (Challenged Oynadıktan Sonra)
@duel_bp.route('/submit-duel-result/<uuid:duel_id>', methods=['POST'])
def submit_duel_result(duel_id):
    user_id, error = get_user_id_from_jwt()
    if error:
        return jsonify(error=error), 401

    data = request.get_json()
    player_score = data.get('score')
    player_time_taken = data.get('time_taken')
    player_answers = data.get('answers') # Cevaplar daha sonra kontrol için tutulabilir

    if not all([player_score is not None, player_time_taken is not None, player_answers is not None]):
        return jsonify(error="Missing required result parameters"), 400

    try:
        # Duel'i çek
        duel_response = supabase.table('duels').select('*').eq('id', str(duel_id)).single().execute()
        duel = duel_response.data

        if not duel:
            return jsonify(error="Duel not found"), 404
        
        # Kullanıcının challenged_id olup olmadığını ve status'un uygunluğunu kontrol et
        if str(user_id) != duel['challenged_id'] or duel['status'] != 'challenger_completed':
            return jsonify(error="You are not the challenged player for this duel, or duel is not in the correct status"), 403

        # Challenged oyuncunun sonuçlarını güncelle
        update_data = {
            'challenged_score': player_score,
            'challenged_time_taken': player_time_taken,
            'challenged_completed_at': 'now()',
            'status': 'completed' # Duel tamamlandı
        }

        # Kazananı belirle
        winner_id = None
        if duel['challenger_score'] > player_score:
            winner_id = duel['challenger_id']
        elif player_score > duel['challenger_score']:
            winner_id = str(user_id)
        else: # Puanlar eşitse, süreye bak
            if duel['challenger_time_taken'] < player_time_taken:
                winner_id = duel['challenger_id']
            elif player_time_taken < duel['challenger_time_taken']:
                winner_id = str(user_id)
            # Beraberlik durumu için winner_id null kalabilir veya farklı bir durum atanabilir

        update_data['winner_id'] = winner_id

        supabase.table('duels').update(update_data).eq('id', str(duel_id)).execute()

        return jsonify({
            "message": "Duel result submitted and duel completed",
            "duel_id": duel_id,
            "your_score": player_score,
            "challenger_score": duel['challenger_score'],
            "winner_id": winner_id
        }), 200

    except Exception as e:
        print(f"Error submitting duel result: {e}")
        traceback.print_exc()
        return jsonify(error="An internal server error occurred"), 500

# TODO: İptal etme, arkadaş arama gibi ek endpoint'ler eklenebilir.s

# 5. Yeni Duel İçin Soruları Çekme (Challenger oyuna başlamadan önce)
# NOT: Bu endpoint duel oluşturulmadan önce sorulara preview için kullanılır
# Gerçek duel'de her iki oyuncu da duel_questions tablosundan aynı soruları alır
@duel_bp.route('/generate-questions', methods=['POST'])
def generate_questions_for_duel():
    user_id, error = get_user_id_from_jwt()
    if error:
        return jsonify(error=error), 401

    data = request.get_json()
    difficulty_level = data.get('difficulty_level')
    duel_id = data.get('duel_id')  # Eğer duel zaten oluşturulmuşsa

    if difficulty_level is None:
        return jsonify(error="Difficulty level is required."), 400
    
    try:
        difficulty_level = int(difficulty_level)
        if not (0 <= difficulty_level <= 5):
            return jsonify(error="Invalid difficulty level. Must be 0-5."), 400
    except ValueError:
        return jsonify(error="Difficulty level must be an integer."), 400
    
    try:
        # Eğer duel_id verilmişse, o duel'in sabitlenmiş sorularını döndür
        if duel_id:
            print(f"DEBUG: Fetching questions for existing duel: {duel_id}")
            # Duel'in sorularını duel_questions tablosundan çek
            response = supabase.table('duel_questions').select(
                'id, question_order, game_item:game_item_id(id, game_type_id, category_id, level, content)'
            ).eq('duel_id', str(duel_id)).order('question_order', desc=False).execute()
            
            questions_data = response.data
            if not questions_data:
                return jsonify(error="No questions found for this duel"), 404
            
            formatted_questions = []
            for dq in questions_data:
                if dq['game_item']:
                    formatted_questions.append({
                        "game_item": {
                            "id": dq['game_item']['id'],
                            "game_type_id": dq['game_item']['game_type_id'],
                            "category_id": dq['game_item']['category_id'],
                            "level": dq['game_item']['level'],
                            "content": dq['game_item']['content']
                        }
                    })
            
            print(f"DEBUG: Returning {len(formatted_questions)} questions from existing duel")
            return jsonify(questions=formatted_questions), 200
        
        # Eğer duel_id yoksa, preview için rastgele sorular döndür
        # UYARI: Bu sorular duel oluşturulduğunda farklı olabilir!
        print(f"DEBUG: Generating preview questions for difficulty {difficulty_level}")
        selected_questions, q_error = get_duel_questions(difficulty_level)
        if q_error:
            return jsonify(error=q_error), 500
        
        if len(selected_questions) < 20:
            return jsonify(error=f"Not enough questions ({len(selected_questions)}) for difficulty level {difficulty_level}. Need 20."), 500

        formatted_questions = []
        for q in selected_questions:
            formatted_questions.append({
                "game_item": {
                    "id": q['id'],               # id'yi int olarak bırak
                    "game_type_id": q['game_type_id'], # game_type_id'yi int olarak bırak
                    "category_id": q['category_id'], # category_id'yi de uygun tipte bırak (int veya UUID string)
                    "level": q['level'],
                    "content": q['content']
                }
            })
        
        print(f"DEBUG: Returning {len(formatted_questions)} preview questions")
        return jsonify({
            "questions": formatted_questions,
            "warning": "These are preview questions. Actual duel questions will be fixed when duel is created."
        }), 200

    except Exception as e:
        print(f"Error generating questions for duel: {e}")
        traceback.print_exc()
        return jsonify(error=f"An internal server error occurred: {str(e)}"), 500
