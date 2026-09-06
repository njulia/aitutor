from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from .account_store import ensure_account
from .kid_session_store import resolve_kid_session
from .study_buddy_store import EMOJI_OPTIONS, acknowledge_challenge_completion_notification, buddies, buddy_code_for, challenge_completion_notifications_for, challenges_for, complete_challenge, create_challenge, create_request, emoji_reactions_for, find_students, get_study_buddy_settings, init_study_buddy_db, parent_requests, approve_request, ranking, remove_buddy, remove_buddy_for_parent, send_emoji_reaction
from .study_buddy_challenge_catalog import challenge_catalog_options
from src.auth_tokens import verify_token

class SearchRequest(BaseModel): query: str = Field(..., min_length=3, max_length=20)
class BuddyRequestBody(BaseModel): target_student_id: str = Field(..., max_length=80)
class ChallengeBody(BaseModel): target_student_id: str = Field(..., max_length=80); challenge_type: str = Field(..., max_length=48)
class EmojiReactionBody(BaseModel): target_student_id: str = Field(..., max_length=80); emoji: str = Field(..., min_length=1, max_length=20)
class DecisionBody(BaseModel): approve: bool

def _kid(req):
    token=req.cookies.get('kid_session') or req.headers.get('X-Kid-Session')
    session=resolve_kid_session(token) if token else None
    if not session: raise HTTPException(401,"Kid sign-in required.")
    return str(session['student_id'])

def _parent(req):
    token=req.cookies.get('session') or req.headers.get('Authorization')
    if token and token.lower().startswith('bearer '): token=token[7:].strip()
    username=verify_token(token) if token else None
    if not username: raise HTTPException(401,"Parent sign-in required.")
    account=ensure_account(username)
    return str(account['id'])

def build_study_buddy_router(project_root):
    init_study_buddy_db()
    project_root = Path(project_root)
    r=APIRouter()
    @r.get('/study-buddies')
    async def page(): return FileResponse(project_root/'static'/'study-buddies.html', headers={'Cache-Control':'no-store, private', 'X-Robots-Tag':'noindex, nofollow'})
    @r.post('/api/study-buddies/search')
    async def search(body:SearchRequest, req:Request): return {'students':find_students(body.query,_kid(req))}
    @r.post('/api/study-buddies/request')
    async def request(body:BuddyRequestBody, req:Request):
        try: return create_request(_kid(req),body.target_student_id)
        except (ValueError,PermissionError) as e: raise HTTPException(400,str(e))
    @r.get('/api/study-buddies')
    async def mine(req:Request):
        sid=_kid(req)
        return {
            'student_id': sid,
            'buddy_code': buddy_code_for(sid),
            'buddies': buddies(sid),
            'challenges': challenges_for(sid),
            'challenge_options': challenge_catalog_options(),
            'ranking': ranking(sid),
            'buddy_completion_notifications': challenge_completion_notifications_for(sid),
            'emoji_reactions': emoji_reactions_for(sid),
            'emoji_options': [
                {'key': key, **value}
                for key, value in EMOJI_OPTIONS.items()
            ],
            'daily_emoji_limit': get_study_buddy_settings()['max_emojis_per_learner'],
        }
    @r.post('/api/study-buddies/emoji')
    async def emoji(body: EmojiReactionBody, req: Request):
        try:
            return send_emoji_reaction(_kid(req), body.target_student_id, body.emoji)
        except PermissionError as e:
            raise HTTPException(403, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))
    @r.post('/api/study-buddies/challenge')
    async def challenge(body:ChallengeBody, req:Request):
        try: return create_challenge(_kid(req),body.target_student_id,body.challenge_type)
        except (ValueError,PermissionError) as e: raise HTTPException(400,str(e))
    @r.post('/api/study-buddies/remove/{buddy_id}')
    async def remove(buddy_id: str, req: Request):
        try: return remove_buddy(_kid(req), buddy_id)
        except ValueError as e: raise HTTPException(404, str(e))

    @r.post('/api/study-buddies/challenge/{challenge_id}/complete')
    async def complete(challenge_id:str, req:Request):
        try: return complete_challenge(challenge_id,_kid(req))
        except (ValueError,PermissionError) as e: raise HTTPException(400,str(e))
    @r.post('/api/study-buddies/challenge-notifications/{notification_id}/seen')
    async def acknowledge_completion_notice(notification_id: str, req: Request):
        try: return acknowledge_challenge_completion_notification(notification_id, _kid(req))
        except ValueError as e: raise HTTPException(404, str(e))
    @r.get('/api/parent/study-buddies/requests')
    async def requests(req:Request): return {'requests':parent_requests(_parent(req))}
    @r.post('/api/parent/study-buddies/remove/{request_id}')
    async def parent_remove(request_id: str, req: Request):
        try: return remove_buddy_for_parent(_parent(req), request_id)
        except PermissionError as e: raise HTTPException(403, str(e))
        except ValueError as e: raise HTTPException(404, str(e))

    @r.post('/api/parent/study-buddies/requests/{request_id}')
    async def decide(request_id:str, body:DecisionBody, req:Request):
        try: return approve_request(request_id,_parent(req),body.approve)
        except PermissionError as e: raise HTTPException(403,str(e))
        except ValueError as e: raise HTTPException(404 if "not found" in str(e).lower() else 400,str(e))
    return r
