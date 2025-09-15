import os
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client, Client


# .env dosyasındaki ortam değişkenlerini yükler
load_dotenv()

# --- Uygulama ve Servislerin Başlatılması ---

# Flask uygulamasını oluşturur
app = Flask(__name__)
# Frontend'den gelecek isteklere izin vermek için CORS'u etkinleştirir
CORS(app, resources={r"/api/*": {
    "origins": ["http://localhost:5173", "http://127.0.0.1:5173"],
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization"],
    "supports_credentials": True
}})

# routes/games.py dosyasından 'games_bp' Blueprint'ini import et
from routes.games import games_bp
from routes.profile import profile_bp
from routes.progress import progress_bp 
from routes.achievements import achievements_bp
from routes.leaderboard import leaderboard_bp
from routes.social import social_bp



# 'games_bp' Blueprint'ini uygulamaya kaydet.
# Artık games.py içindeki tüm route'lar aktif.
app.register_blueprint(games_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(progress_bp)
app.register_blueprint(achievements_bp)
app.register_blueprint(leaderboard_bp)
app.register_blueprint(social_bp)

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
