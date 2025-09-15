from flask import Blueprint, app, jsonify, request
import random
import traceback

from .extensions import supabase
games_bp = Blueprint('games_bp', __name__, url_prefix='/api/games')

# --- SENTENCE SCRAMBLE (GET) - GÜNCELLENDİ ---
@games_bp.route("/sentence-scramble")
def get_sentence_scramble_game():
    target_lang = request.args.get('lang', 'en')
    try:
        level = int(request.args.get('level', 1))
    except Exception:
        level = 1
    category_slug = request.args.get('category') # Kategori parametresini alıyoruz

    # Yeni: frontend'den gelen seen_ids parametresi (ör. "1,2,3")
    seen_ids_str = request.args.get('seen_ids', '')
    seen_ids = []
    if seen_ids_str:
        try:
            seen_ids = [int(s.strip()) for s in seen_ids_str.split(',') if s.strip()]
        except ValueError:
            seen_ids = []

    if not category_slug:
        return jsonify(error="Category slug is required."), 400

    try:
        # Slug'dan kategori ID'sini bul
        category_response = supabase.table('categories').select('id').eq('slug', category_slug).single().execute()
        if not category_response.data:
            return jsonify(error=f"Category '{category_slug}' not found."), 404
        category_id = category_response.data['id']

        # Sorguya kategori filtresini ekliyoruz, id ve content al
        response = supabase.table('game_items').select('id, content').eq('category_id', category_id).eq('level', level).execute()
        rows = response.data or []

        # Python tarafında filtrele: seen ids'i çıkar
        if seen_ids:
            rows = [r for r in rows if r.get('id') not in seen_ids]

        if not rows:
            # no remaining questions
            return jsonify({})

        random_game_item = random.choice(rows)
        item_id = random_game_item.get('id')
        content = random_game_item.get('content', {})

        correct_sentence = content.get(target_lang)
        if not correct_sentence:
            return jsonify(error=f"Content for language '{target_lang}' not found"), 404

        words = correct_sentence.split()
        random.shuffle(words)

        game_data = {
            "id": item_id,
            "shuffled_words": words,
            "correct_sentence": correct_sentence
        }
        return jsonify(game_data)
    except Exception as e:
        print(f"An error occurred in get_sentence_scramble_game: {e}")
        return jsonify(error="An internal server error occurred."), 500

# --- SENTENCE SCRAMBLE (POST) ---
@games_bp.route("/sentence-scramble", methods=['POST'])
def add_sentence_scramble_game():
    data = request.get_json()
    if not data or not all(k in data for k in ['en', 'tr', 'ja']):
        return jsonify(error="Missing required language fields: en, tr, ja"), 400
    try:
        game_type_response = supabase.table('game_types').select('id').eq('slug', 'sentence-scramble').single().execute()
        if not game_type_response.data:
            return jsonify(error="Game type 'sentence-scramble' not found."), 404
        game_type_id = game_type_response.data['id']
        content = {
            "en": data['en'],
            "tr": data['tr'],
            "ja": data['ja']
        }
        supabase.table('game_items').insert({
            "game_type_id": game_type_id,
            "level": data.get('level', 1),
            "content": content
        }).execute()
        return jsonify(message="Sentence Scramble game added successfully!"), 201
    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify(error="An internal server error occurred."), 500


# ... dosyanın üst kısmı ve diğer fonksiyonlar aynı kalıyor ...

# --- IMAGE MATCH (GET) - GÜNCELLENDİ ---
@games_bp.route("/image-match")
def get_image_match_game():
    target_lang = request.args.get('lang', 'en')
    try:
        level = int(request.args.get('level', 1))
    except Exception:
        level = 1
    category_slug = request.args.get('category')

    # YENİ: Frontend'den gelen "görülmüş soru ID'leri" listesini al
    seen_ids_str = request.args.get('seen_ids', '')
    seen_ids = []
    if seen_ids_str:
        try:
            # Gelen "1,2,3" formatındaki string'i [1, 2, 3] listesine çevir
            seen_ids = [int(id_str) for id_str in seen_ids_str.split(',') if id_str.strip()]
        except ValueError:
            seen_ids = []  # Hatalı formatı görmezden gel

    if not category_slug:
        return jsonify(error="Category slug is required."), 400

    try:
        category_response = supabase.table('categories').select('id').eq('slug', category_slug).execute()
        if not category_response.data:
            return jsonify(error=f"Category '{category_slug}' not found."), 404
        category_id = category_response.data[0]['id']

        # Sorguyu oluşturalım. Artık ID'yi de seçiyoruz.
        query = supabase.table('game_items').select('id, content').eq('category_id', category_id).eq('level', level)

        # Debug: show the built clause and query type
        print(f"[debug] image-match query prepared: category_id={category_id}, level={level}, seen_ids={seen_ids}")
        try:
            response = query.execute()
        except Exception as inner_e:
            print(f"[debug] query.execute() failed: {inner_e}")
            traceback.print_exc()
            raise
        
        rows = response.data or []

        # Python tarafında filtrele
        if seen_ids:
            rows = [r for r in rows if r.get('id') not in seen_ids]

        if not rows:
            return jsonify({})

        # Kalan sorulardan rastgele birini seç
        random_game_item = random.choice(rows)
        item_id = random_game_item.get('id')
        content = random_game_item.get('content')
        
        image_url = content.get('image_url')
        options = content.get('options', {}).get(target_lang)
        answer = content.get('answer', {}).get(target_lang)
        
        if not all([image_url, options, answer]):
            return jsonify(error=f"Content for language '{target_lang}' is incomplete."), 404
            
        random.shuffle(options)
        
        game_data = { 
            "id": item_id, # YENİ: Frontend'in bu soruyu hatırlaması için ID'sini de gönderiyoruz
            "image_url": image_url, 
            "options": options, 
            "answer": answer 
        }
        return jsonify(game_data)

    except Exception as e:
        print(f"An error occurred in get_image_match_game: {e}")
        traceback.print_exc()
        return jsonify(error="An internal server error occurred."), 500

# ... geri kalan kod aynı kalıyor ...



# --- OYUN 3: FILL IN THE BLANK ---
@games_bp.route("/fill-in-the-blank")
def get_fill_in_the_blank_game():
    target_lang = request.args.get('lang', 'en')
    try:
        level = int(request.args.get('level', 1))
    except Exception:
        level = 1
    category_slug = request.args.get('category')

    # Yeni: frontend'den gelen seen_ids parametresi (ör. "1,2,3")
    seen_ids_str = request.args.get('seen_ids', '')
    seen_ids = []
    if seen_ids_str:
        try:
            seen_ids = [int(s.strip()) for s in seen_ids_str.split(',') if s.strip()]
        except ValueError:
            seen_ids = []

    if not category_slug:
        return jsonify(error="Category slug is required."), 400

    try:
        category_response = supabase.table('categories').select('id').eq('slug', category_slug).single().execute()
        if not category_response.data:
            return jsonify(error=f"Category '{category_slug}' not found."), 404
        category_id = category_response.data['id']

        # id ve content alıyoruz
        response = supabase.table('game_items').select('id, content').eq('category_id', category_id).eq('level', level).execute()
        rows = response.data or []

        # Python tarafında filtrele: seen ids'i çıkar
        if seen_ids:
            rows = [r for r in rows if r.get('id') not in seen_ids]

        if not rows:
            # no remaining questions
            return jsonify({})

        random_item = random.choice(rows)
        item_id = random_item.get('id')
        content = random_item.get('content', {})

        sentence_parts = content.get('sentence_parts', {}).get(target_lang)
        options = content.get('options', {}).get(target_lang)
        answer = content.get('answer', {}).get(target_lang)

        if not all([sentence_parts, options, answer]):
            return jsonify(error=f"Content for language '{target_lang}' is incomplete"), 404

        random.shuffle(options)
        game_data = {
            "id": item_id,
            "sentence_parts": sentence_parts,
            "options": options,
            "answer": answer
        }
        return jsonify(game_data)

    except Exception as e:
        print(f"An error occurred in get_fill_in_the_blank_game: {e}")
        traceback.print_exc()
        return jsonify(error="An internal server error occurred."), 500
    

@games_bp.route("/<game_slug>/categories")
def get_categories_for_game(game_slug):
    """Belirli bir oyuna ait kategorileri listeler."""
    try:
        # 1. URL'den gelen slug'a göre oyunun ID'sini bul
        game_type_response = supabase.table('game_types').select('id').eq('slug', game_slug).single().execute()
        if not game_type_response.data:
            return jsonify(error=f"Game type '{game_slug}' not found."), 404
        game_type_id = game_type_response.data['id']

        # 2. Bulunan oyun ID'sine sahip tüm kategorileri çek
        # Bu sorgu, doğrudan categories tablosunu kullandığı için daha verimlidir.
        categories_response = supabase.table('categories').select('id, slug, name').eq('game_type_id', game_type_id).execute()

        return jsonify(categories_response.data)
        
    except Exception as e:
        print(f"An error occurred in get_categories_for_game: {e}")
        return jsonify(error="An internal server error occurred."), 500
    

# --- ÖZEL OYUN MODLARI ---
@games_bp.route("/mixed-rush/random-question")
def get_mixed_rush_question():
    """
    Mixed Rush modu için veritabanından rastgele,
    herhangi bir türde bir oyun sorusu çeker.
    """
    try:
        # Veritabanında oluşturduğumuz özel RPC fonksiyonunu çağırıyoruz
        response = supabase.rpc('get_random_game_item').execute()

        if not response.data:
            return jsonify(error="No game items found in the database."), 404
        
        # Fonksiyon tek bir sonuç döndürür, onu alıyoruz
        game_data = response.data[0]

        # Frontend'in beklediği formata dönüştürüyoruz
        # Ensure we include the `level` so Mixed Rush frontend can send per-question scoring
        question_level = game_data.get('game_level') or game_data.get('level') or 1
        formatted_data = {
            "type": game_data.get('game_type'),
            "data": game_data.get('game_content'),
            "level": int(question_level)
        }
        
        # Fonksiyondan dönen 'content' JSON'ı, diğer oyunların beklediği
        # 'data' anahtarı altına yerleştiriyoruz.
        if formatted_data['type'] == 'sentence-scramble':
            correct_sentence = formatted_data['data'].get(request.args.get('lang', 'en'))
            if not correct_sentence:
                return jsonify(error="Content language missing"), 404
            words = correct_sentence.split()
            random.shuffle(words)
            formatted_data['data'] = { "shuffled_words": words, "correct_sentence": correct_sentence }
        
        elif formatted_data['type'] == 'image-match':
            lang = request.args.get('lang', 'en')
            options = (formatted_data['data'].get('options') or {}).get(lang)
            answer = (formatted_data['data'].get('answer') or {}).get(lang)
            if not all([options, answer, formatted_data['data'].get('image_url')]):
                return jsonify(error=f"Content for language '{lang}' is incomplete for image-match."), 404
            random.shuffle(options)
            formatted_data['data'] = {
                "image_url": formatted_data['data']['image_url'],
                "options": options,
                "answer": answer
            }
        
        elif formatted_data['type'] == 'fill-in-the-blank':
            lang = request.args.get('lang', 'en')
            options = (formatted_data['data'].get('options') or {}).get(lang)
            sentence_parts = (formatted_data['data'].get('sentence_parts') or {}).get(lang)
            answer = (formatted_data['data'].get('answer') or {}).get(lang)
            if not all([sentence_parts, options, answer]):
                return jsonify(error=f"Content for language '{lang}' is incomplete for fill-in-the-blank."), 404
            random.shuffle(options)
            formatted_data['data'] = {
                "sentence_parts": sentence_parts,
                "options": options,
                "answer": answer
            }

        return jsonify(formatted_data)

    except Exception as e:
        print(f"An error occurred in get_mixed_rush_question: {e}")
        return jsonify(error="An internal server error occurred."), 500   
    
@games_bp.route("/<game_slug>/<category_slug>/levels")
def get_levels_for_category(game_slug, category_slug):
    """Belirli bir oyun ve kategori için mevcut olan tüm seviyeleri listeler."""
    try:
        # Oyun ve kategori ID'lerini bul
        game_type_response = supabase.table('game_types').select('id').eq('slug', game_slug).single().execute()
        category_response = supabase.table('categories').select('id').eq('slug', category_slug).single().execute()

        if not game_type_response.data or not category_response.data:
            return jsonify(error="Game or Category not found"), 404
        
        game_type_id = game_type_response.data['id']
        category_id = category_response.data['id']

        # game_items tablosundan bu oyuna ve kategoriye ait olan tüm benzersiz seviyeleri çek
        # DISTINCT, tekrar eden seviye numaralarını (1, 1, 1, 1) engeller ve sadece [1] döndürür.
        levels_response = supabase.table('game_items').select('level', count='exact').eq('game_type_id', game_type_id).eq('category_id', category_id).execute()
        
        # Gelen veriden sadece seviye numaralarını alıp, benzersiz bir liste oluşturuyoruz
        if levels_response.data:
            unique_levels = sorted(list(set([item['level'] for item in levels_response.data])))
            return jsonify(unique_levels)
        else:
            return jsonify([])

    except Exception as e:
        print(f"An error occurred in get_levels_for_category: {e}")
        return jsonify(error="An internal server error occurred."), 500
