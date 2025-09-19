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
            # Fallback: implement aggregation in Python using existing tables
            try:
                # 1) find game_type id by slug
                gt_res = supabase.table('game_types').select('id, slug, name').eq('slug', game_slug).single().execute()
                if not gt_res.data:
                    return jsonify([])
                gt_id = gt_res.data['id']

                # 2) get categories for this game type
                cats_res = supabase.table('categories').select('id').eq('game_type_id', gt_id).execute()
                cat_ids = [c['id'] for c in (cats_res.data or [])]
                if not cat_ids:
                    return jsonify([])

                # 3) fetch user_level_progress rows for these categories
                progress_res = supabase.table('user_level_progress').select('user_id, score').in_('category_id', cat_ids).execute()
                rows = progress_res.data or []

                # 4) aggregate scores per user
                totals = {}
                for r in rows:
                    uid = r.get('user_id')
                    try:
                        s = int(r.get('score') or 0)
                    except Exception:
                        s = 0
                    totals[uid] = totals.get(uid, 0) + s

                if not totals:
                    return jsonify([])

                # 5) fetch profiles for these users
                user_ids = list(totals.keys())
                profiles_res = supabase.table('profiles').select('id, username, avatar_url').in_('id', user_ids).execute()
                profiles = {p['id']: p for p in (profiles_res.data or [])}

                # 6) build leaderboard list
                result = []
                for uid, score in totals.items():
                    prof = profiles.get(uid, {})
                    result.append({
                        'id': uid,
                        'username': prof.get('username') or None,
                        'avatar_url': prof.get('avatar_url') or None,
                        'total_score_for_game': int(score)
                    })

                # sort and limit
                result.sort(key=lambda x: x['total_score_for_game'], reverse=True)
                result = result[:50]
                data = result
            except Exception as e:
                return jsonify(error=str(e)), 500
            
        # sanitize
        for item in data:
            item.setdefault('avatar_url', None)
        return jsonify(data)
    except Exception as e:
        return jsonify(error=str(e)), 500