"""WebSocket router -- browser connects here for real-time session (D-06).

Endpoint: /ws/{session_token}
Token flow:
1. Flask generates token (secrets.token_urlsafe(32)), stores in Redis with user data
2. Browser opens WebSocket to /ws/{token}
3. Engine validates token against Redis (single-use, 60s TTL)
4. If valid: accept connection, start session manager
5. If invalid: close with 4401 code (unauthorized)

The token is single-use (deleted after validation) to prevent replay attacks.
"""
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from nerve_rt.redis_bridge import redis_bridge

logger = logging.getLogger("nerve_rt.ws")

router = APIRouter()

# SessionManager is injected at app startup (avoid circular imports)
_session_manager = None


def set_session_manager(manager):
    """Inject SessionManager instance at startup. Called from main.py lifespan."""
    global _session_manager
    _session_manager = manager


@router.websocket("/ws/{session_token}")
async def websocket_endpoint(websocket: WebSocket, session_token: str):
    """Main WebSocket endpoint for real-time sessions.

    Token validation flow (Pitfall 4: cannot read Flask session cookies):
    - Flask writes session data to Redis: HSET nerve:session:{token} user_id X mode Y
    - Engine reads and deletes token (single-use)
    - On valid token: accept + start session
    - On invalid/expired token: close with 4401
    """
    # Validate session token
    session_data = await redis_bridge.get_session(session_token)
    if not session_data:
        logger.warning("[WS] Invalid/expired token: %s...", session_token[:8])
        await websocket.close(code=4401)
        return

    if not _session_manager:
        logger.error("[WS] SessionManager not initialized")
        await websocket.close(code=4500)
        return

    logger.info(
        "[WS] Connection accepted: user=%s, mode=%s",
        session_data.get("user_id"),
        session_data.get("mode"),
    )

    await websocket.accept()

    try:
        await _session_manager.handle_session(websocket, session_data)
    except WebSocketDisconnect:
        logger.info("[WS] Client disconnected: user=%s", session_data.get("user_id"))
    except Exception as e:
        logger.error("[WS] Session error: %s", e)
