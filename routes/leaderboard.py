from flask import Blueprint, jsonify, request
from extensions import supabase

leaderboard_bp = Blueprint('leaderboard_bp', __name__, url_prefix='/api/leaderboard')

@leaderboard_bp.route('/total-score')
def get_total_score_leaderboard():
    try:
        # Try RPC first, fallback to manual query with avatar_url
        try:
            response = supabase.rpc('get_leaderboard_total_score').execute()
            data = response.data or []
        except:
            # Fallback: manual query with avatar_url join
            response = supabase.table('profiles').select('id, username, total_score, avatar_url').order('total_score', desc=True).limit(50).execute()
            data = response.data or []
            
        # sanitize: ensure numeric scores and avatar_url exist to avoid frontend errors
        for item in data:
            if 'total_score' in item:
                try:
                    item['total_score'] = int(item.get('total_score') or 0)
                except Exception:
                    item['total_score'] = 0
            if 'mixed_rush_highscore' in item:
                try:
                    item['mixed_rush_highscore'] = int(item.get('mixed_rush_highscore') or 0)
                except Exception:
                    item['mixed_rush_highscore'] = 0
            item.setdefault('avatar_url', None)
        return jsonify(data)
    except Exception as e:
        return jsonify(error=str(e)), 500

@leaderboard_bp.route('/total-scores')
def get_total_scores_leaderboard():
    """Frontend compatibility endpoint with limit support"""
    try:
        limit = request.args.get('limit', 10, type=int)
        
        # Try RPC first, fallback to manual query with avatar_url
        try:
            response = supabase.rpc('get_leaderboard_total_score').execute()
            data = response.data or []
            
            # Check if avatar_url is missing from RPC result
            if data and not any('avatar_url' in item for item in data[:3]):
                raise Exception("RPC missing avatar_url")
                
        except:
            # Fallback: manual query with avatar_url join
            response = supabase.table('profiles').select('id, username, total_score, avatar_url').order('total_score', desc=True).limit(limit or 50).execute()
            data = response.data or []
        
        # Limit the results if specified and using RPC
        if limit and isinstance(data, list) and len(data) > limit:
            data = data[:limit]

        # sanitize
        for item in data:
            if 'total_score' in item:
                try:
                    item['total_score'] = int(item.get('total_score') or 0)
                except Exception:
                    item['total_score'] = 0
            item.setdefault('avatar_url', None)

        return jsonify(data)
    except Exception as e:
        return jsonify(error=str(e)), 500

@leaderboard_bp.route('/mixed-rush')
def get_mixed_rush_leaderboard():
    try:
        # Try RPC first, fallback to manual query with avatar_url
        try:
            response = supabase.rpc('get_leaderboard_mixed_rush').execute()
            data = response.data or []
            
            # Check if avatar_url is missing from RPC result
            if data and not any('avatar_url' in item for item in data[:3]):
                raise Exception("RPC missing avatar_url")
                
        except:
            # Fallback: manual query with avatar_url join
            response = supabase.table('profiles').select('id, username, mixed_rush_highscore, avatar_url').order('mixed_rush_highscore', desc=True).limit(50).execute()
            data = response.data or []
            
        # sanitize
        for item in data:
            if 'mixed_rush_highscore' in item:
                try:
                    item['mixed_rush_highscore'] = int(item.get('mixed_rush_highscore') or 0)
                except Exception:
                    item['mixed_rush_highscore'] = 0
            item.setdefault('avatar_url', None)
        return jsonify(data)
    except Exception as e:
        return jsonify(error=str(e)), 500

@leaderboard_bp.route('/game/<game_slug>')
def get_game_leaderboard(game_slug):
    try:
        # Try RPC first, fallback to manual query with avatar_url
        try:
            response = supabase.rpc('get_leaderboard_for_game', {'p_game_slug': game_slug}).execute()
            data = response.data or []
            
            # Check if avatar_url is missing from RPC result
            if data and not any('avatar_url' in item for item in data[:3]):
                raise Exception("RPC missing avatar_url")
                
        except:
            # Fallback: This would need category_progress table join - simplified for now
            # You might need to implement this based on your exact schema
            return jsonify(error=f"Game leaderboard for '{game_slug}' requires schema details"), 501
            
        # sanitize
        for item in data:
            item.setdefault('avatar_url', None)
        return jsonify(data)
    except Exception as e:
        return jsonify(error=str(e)), 500