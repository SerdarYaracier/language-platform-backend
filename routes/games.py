from flask import Blueprint, app, jsonify, request
import random

from .extensions import supabase
games_bp = Blueprint('games_bp', __name__, url_prefix='/api/games')

# --- SENTENCE SCRAMBLE (GET) - GÜNCELLENDİ ---
@games_bp.route("/sentence-scramble")
def get_sentence_scramble_game():
    target_lang = request.args.get('lang', 'en')
    level = request.args.get('level', 1)
    category_slug = request.args.get('category') # Kategori parametresini alıyoruz

    if not category_slug:
        return jsonify(error="Category slug is required."), 400

    try:
        # Slug'dan kategori ID'sini bul
        category_response = supabase.table('categories').select('id').eq('slug', category_slug).single().execute()
        if not category_response.data:
            return jsonify(error=f"Category '{category_slug}' not found."), 404
        category_id = category_response.data['id']

        # Sorguya kategori filtresini ekliyoruz
        response = supabase.table('game_items').select('content').eq('category_id', category_id).eq('level', level).execute()
        
        if not response.data:
            return jsonify(error=f"No game content found for this category"), 404
            
        random_game_item = random.choice(response.data)['content']
        correct_sentence = random_game_item.get(target_lang)
        if not correct_sentence:
            return jsonify(error=f"Content for language '{target_lang}' not found"), 404
        words = correct_sentence.split()
        random.shuffle(words)
        game_data = { "shuffled_words": words, "correct_sentence": correct_sentence }
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


# --- IMAGE MATCH (GET) ---
@games_bp.route("/image-match")
def get_image_match_game():
    target_lang = request.args.get('lang', 'en')
    level = request.args.get('level', 1)
    category_slug = request.args.get('category')

    if not category_slug:
        return jsonify(error="Category slug is required."), 400

    try:
        # ÖNCE KATEGORİYİ GÜVENLİ BİR ŞEKİLDE ALIYORUZ
        category_response = supabase.table('categories').select('id').eq('slug', category_slug).execute()
        
        # EĞER KATEGORİ BULUNAMAZSA, HATA DÖNDÜRÜYORUZ
        if not category_response.data:
            return jsonify(error=f"Category '{category_slug}' not found."), 404
        
        category_id = category_response.data[0]['id']

        # Artık sorguyu kategori ID'sine göre yapıyoruz
        response = supabase.table('game_items').select('content').eq('category_id', category_id).eq('level', level).execute()
        
        if not response.data:
            return jsonify(error=f"No game content found for this category"), 404

        # Fonksiyonun geri kalanı...
        random_game_item = random.choice(response.data)['content']
        image_url = random_game_item.get('image_url')
        options = random_game_item.get('options', {}).get(target_lang)
        answer = random_game_item.get('answer', {}).get(target_lang)
        if not all([image_url, options, answer]):
            return jsonify(error=f"Content for language '{target_lang}' is incomplete for the selected game item."), 404
        random.shuffle(options)
        game_data = { "image_url": image_url, "options": options, "answer": answer }
        return jsonify(game_data)

    except Exception as e:
        print(f"An error occurred in get_image_match_game: {e}")
        return jsonify(error="An internal server error occurred."), 500

# --- IMAGE MATCH (POST) ---
@games_bp.route("/image-match", methods=['POST'])
def add_image_match_game():
    data = request.get_json()
    if not data or not all(k in data for k in ['image_url', 'options', 'answer']):
        return jsonify(error="Missing required fields: image_url, options, answer"), 400
    try:
        game_type_response = supabase.table('game_types').select('id').eq('slug', 'image-match').single().execute()
        if not game_type_response.data:
            return jsonify(error="Game type 'image-match' not found."), 404
        game_type_id = game_type_response.data['id']
        content = {
            "image_url": data['image_url'],
            "options": data['options'],
            "answer": data['answer']
        }
        supabase.table('game_items').insert({
            "game_type_id": game_type_id,
            "level": data.get('level', 1),
            "content": content
        }).execute()
        return jsonify(message="Image Match game added successfully!"), 201
    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify(error="An internal server error occurred."), 500

# --- OYUN 3: FILL IN THE BLANK ---
@games_bp.route("/fill-in-the-blank")
def get_fill_in_the_blank_game():
    target_lang = request.args.get('lang', 'en')
    level = request.args.get('level', 1)
    category_slug = request.args.get('category') # Kategori parametresini alıyoruz

    if not category_slug:
        return jsonify(error="Category slug is required."), 400
        
    try:
        category_response = supabase.table('categories').select('id').eq('slug', category_slug).single().execute()
        if not category_response.data:
            return jsonify(error=f"Category '{category_slug}' not found."), 404
        category_id = category_response.data['id']
        
        # Sorguya kategori filtresini ekliyoruz
        response = supabase.table('game_items').select('content').eq('category_id', category_id).eq('level', level).execute()

        if not response.data:
            return jsonify(error=f"No game content found for this category"), 404

        random_game_item = random.choice(response.data)['content']
        sentence_parts = random_game_item.get('sentence_parts', {}).get(target_lang)
        options = random_game_item.get('options', {}).get(target_lang)
        answer = random_game_item.get('answer', {}).get(target_lang)
        if not all([sentence_parts, options, answer]):
            return jsonify(error=f"Content for language '{target_lang}' is incomplete"), 404
        random.shuffle(options)
        game_data = { "sentence_parts": sentence_parts, "options": options, "answer": answer }
        return jsonify(game_data)
    except Exception as e:
        print(f"An error occurred in get_fill_in_the_blank_game: {e}")
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
        formatted_data = {
            "type": game_data.get('game_type'),
            "data": game_data.get('game_content')
        }
        
        # Fonksiyondan dönen 'content' JSON'ı, diğer oyunların beklediği
        # 'data' anahtarı altına yerleştiriyoruz.
        if formatted_data['type'] == 'sentence-scramble':
            correct_sentence = formatted_data['data'].get(request.args.get('lang', 'en'))
            words = correct_sentence.split()
            random.shuffle(words)
            formatted_data['data'] = { "shuffled_words": words, "correct_sentence": correct_sentence }
        
        elif formatted_data['type'] == 'image-match':
            lang = request.args.get('lang', 'en')
            options = formatted_data['data']['options'][lang]
            random.shuffle(options)
            formatted_data['data'] = {
                "image_url": formatted_data['data']['image_url'],
                "options": options,
                "answer": formatted_data['data']['answer'][lang]
            }
        
        elif formatted_data['type'] == 'fill-in-the-blank':
            lang = request.args.get('lang', 'en')
            options = formatted_data['data']['options'][lang]
            random.shuffle(options)
            formatted_data['data'] = {
                "sentence_parts": formatted_data['data']['sentence_parts'][lang],
                "options": options,
                "answer": formatted_data['data']['answer'][lang]
            }

        return jsonify(formatted_data)

    except Exception as e:
        print(f"An error occurred in get_mixed_rush_question: {e}")
        return jsonify(error="An internal server error occurred."), 500    
