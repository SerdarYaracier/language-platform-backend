import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client, Client
from extensions import supabase


# .env dosyasındaki ortam değişkenlerini yükler
load_dotenv()

# --- Uygulama ve Servislerin Başlatılması ---

# Flask uygulamasını oluşturur
app = Flask(__name__)
# Frontend'den gelecek isteklere izin vermek için CORS'u etkinleştirir
CORS(app, resources={r"/api/*": {
    "origins": ["http://localhost:5173", "http://127.0.0.1:5173"],
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization", "X-Requested-With", "Accept", "Origin", "Referer", "User-Agent"],
    "supports_credentials": True
}})

# routes/games.py dosyasından 'games_bp' Blueprint'ini import et
from routes.games import games_bp
from routes.profile import profile_bp
from routes.progress import progress_bp 
from routes.achievements import achievements_bp
from routes.leaderboard import leaderboard_bp
from routes.social import social_bp
from routes.duel import duel_bp
from routes.profile import upload_avatar as profile_upload_avatar_compat



# 'games_bp' Blueprint'ini uygulamaya kaydet.
# Artık games.py içindeki tüm route'lar aktif.
app.register_blueprint(games_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(progress_bp)
app.register_blueprint(achievements_bp)
app.register_blueprint(leaderboard_bp)
app.register_blueprint(social_bp)
app.register_blueprint(duel_bp)


# Top-level compatibility route so frontend can call /api/upload-avatar
@app.route('/api/upload-avatar', methods=['POST', 'OPTIONS'])
def upload_avatar_root():
    # ensure preflight returns OK
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    # forward POST handling to the profile blueprint's handler
    return profile_upload_avatar_compat()




# --- Ana Test Route'u ---

# Sunucunun ayakta olup olmadığını kontrol etmek için basit bir endpoint
@app.route("/")
def index():
    return jsonify(status="API is up and running!")


# Bu blok, 'python app.py' komutuyla direkt çalıştırma için kullanılır.
# 'flask run' komutuyla çalıştırdığımızda bu bloğa ihtiyaç duyulmaz ama
# standart bir pratiktir.
if __name__ == '__main__':
    app.run(debug=True)
