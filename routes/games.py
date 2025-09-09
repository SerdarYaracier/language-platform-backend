from flask import Blueprint, jsonify, request
import random

from .extensions import supabase
games_bp = Blueprint('games_bp', __name__, url_prefix='/api/games')

# --- SENTENCE SCRAMBLE (GET) ---
@games_bp.route("/sentence-scramble", methods=['GET'])
def get_sentence_scramble_game():
    target_lang = request.args.get('lang', 'en')
    level = request.args.get('level', 1)
    try:
        game_type_response = supabase.table('game_types').select('id').eq('slug', 'sentence-scramble').single().execute()
        if not game_type_response.data:
            return jsonify(error="Game type 'sentence-scramble' not found."), 404
        game_type_id = game_type_response.data['id']
        response = supabase.table('game_items').select('content').eq('game_type_id', game_type_id).eq('level', level).execute()
        if not response.data:
            return jsonify(error=f"No game content found for lang='{target_lang}' and level={level}"), 404
        random_game_item = random.choice(response.data)
        correct_sentence = random_game_item['content'].get(target_lang)
        if not correct_sentence:
            return jsonify(error=f"Content for language '{target_lang}' not found in the selected game item."), 404
        words = correct_sentence.split()
        random.shuffle(words)
        game_data = { "shuffled_words": words, "correct_sentence": correct_sentence }
        return jsonify(game_data)
    except Exception as e:
        print(f"An error occurred: {e}")
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
@games_bp.route("/image-match", methods=['GET'])
def get_image_match_game():
    target_lang = request.args.get('lang', 'en')
    level = request.args.get('level', 1)
    try:
        game_type_response = supabase.table('game_types').select('id').eq('slug', 'image-match').single().execute()
        if not game_type_response.data:
            return jsonify(error="Game type 'image-match' not found."), 404
        game_type_id = game_type_response.data['id']
        response = supabase.table('game_items').select('content').eq('game_type_id', game_type_id).eq('level', level).execute()
        if not response.data:
            return jsonify(error=f"No game content found for lang='{target_lang}' and level={level}"), 404
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
    """
    Fill in the Blank oyunu için veri sağlayan API endpoint'i.
    """
    target_lang = request.args.get('lang', 'en')
    level = request.args.get('level', 1)

    try:
        # 'fill-in-the-blank' oyun türünün ID'sini bul
        game_type_response = supabase.table('game_types').select('id').eq('slug', 'fill-in-the-blank').single().execute()
        if not game_type_response.data:
            return jsonify(error="Game type 'fill-in-the-blank' not found."), 404
        game_type_id = game_type_response.data['id']

        # O türe ait tüm oyun içeriklerini çek
        response = supabase.table('game_items').select('content').eq('game_type_id', game_type_id).eq('level', level).execute()
        if not response.data:
            return jsonify(error=f"No game content found for lang='{target_lang}' and level={level}"), 404

        # Rastgele bir oyun seç
        random_game_item = random.choice(response.data)['content']

        # İstenen dile göre verileri hazırla
        sentence_parts = random_game_item.get('sentence_parts', {}).get(target_lang)
        options = random_game_item.get('options', {}).get(target_lang)
        answer = random_game_item.get('answer', {}).get(target_lang)

        if not all([sentence_parts, options, answer]):
            return jsonify(error=f"Content for language '{target_lang}' is incomplete for the selected game item."), 404

        random.shuffle(options)

        game_data = {
            "sentence_parts": sentence_parts,
            "options": options,
            "answer": answer
        }

        return jsonify(game_data)

    except Exception as e:
        print(f"An error occurred in get_fill_in_the_blank_game: {e}")
        return jsonify(error="An internal server error occurred."), 500