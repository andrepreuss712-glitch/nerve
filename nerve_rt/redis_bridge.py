"""
NERVE Real-Time Engine — Redis Bridge

Async Redis client for bidirectional communication between
the Flask app and the RT Engine.

Pattern: Flask writes session tokens to Redis, Engine validates them.
Engine publishes analysis results, Flask can subscribe for updates.

IMPORTANT: No audio data ever touches Redis (D-09 / ephemeral processing).
"""

import json
import logging
from typing import Optional, AsyncIterator

from redis import asyncio as aioredis

logger = logging.getLogger("nerve_rt.redis")

# Redis key prefixes — shared convention between Flask and Engine
SESSION_PREFIX = "nerve:session:"       # HSET — Flask writes, Engine reads
RESULTS_CHANNEL = "nerve:results:"      # PUB/SUB — Engine publishes, Flask subscribes
CONTROL_CHANNEL = "nerve:control:"      # PUB/SUB — Flask publishes, Engine subscribes


class RedisBridge:
    """Async Redis client for communication between Flask and RT Engine.

    Singleton instance created at module level. Connect/close managed
    by FastAPI lifespan events in main.py.
    """

    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None
        self._pubsub: Optional[aioredis.client.PubSub] = None

    async def connect(self, url: str = None):
        """Connect to Redis. Called during FastAPI startup."""
        from nerve_rt.config import settings
        redis_url = url or settings.redis_url
        self._redis = await aioredis.from_url(
            redis_url,
            decode_responses=True,
            max_connections=10,
        )
        logger.info(f"[Redis] Connected to {redis_url}")

    async def close(self):
        """Close Redis connections. Called during FastAPI shutdown."""
        if self._pubsub:
            await self._pubsub.close()
            self._pubsub = None
        if self._redis:
            await self._redis.close()
            self._redis = None
        logger.info("[Redis] Connection closed")

    async def ping(self) -> bool:
        """Check Redis connection health."""
        try:
            if self._redis:
                return await self._redis.ping()
            return False
        except Exception:
            return False

    # -- Session Token Operations ------------------------------------------

    async def get_session(self, token: str) -> Optional[dict]:
        """Validate session token and return session data.

        Flask writes:
            HSET nerve:session:{token} user_id X mode Y profile_id Z
            EXPIRE nerve:session:{token} 60

        Token is single-use: deleted after first read to prevent
        replay attacks (T-04.8.1-01 mitigation).

        Returns session data dict or None if expired/invalid.
        """
        if not self._redis:
            return None
        key = f"{SESSION_PREFIX}{token}"
        data = await self._redis.hgetall(key)
        if not data:
            return None
        # Single-use: delete token after read
        await self._redis.delete(key)
        return data

    # -- Result Publishing (Engine -> Flask/Dashboard) ---------------------

    async def publish_result(self, user_id: str, result: dict):
        """Publish analysis result for a user.

        Flask or other subscribers can listen on nerve:results:{user_id}
        for real-time dashboard updates.
        """
        if not self._redis:
            return
        channel = f"{RESULTS_CHANNEL}{user_id}"
        await self._redis.publish(channel, json.dumps(result))

    # -- Control Subscription (Flask -> Engine) ----------------------------

    async def subscribe_control(self, session_id: str) -> Optional[aioredis.client.PubSub]:
        """Subscribe to control messages from Flask for a specific session.

        Returns a PubSub instance to iterate over with listen_control().
        """
        if not self._redis:
            return None
        self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe(f"{CONTROL_CHANNEL}{session_id}")
        return self._pubsub

    async def listen_control(self, pubsub: aioredis.client.PubSub) -> AsyncIterator[dict]:
        """Async generator for control messages.

        Usage:
            ps = await redis_bridge.subscribe_control(session_id)
            async for msg in redis_bridge.listen_control(ps):
                handle(msg)
        """
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    yield json.loads(message["data"])
                except json.JSONDecodeError:
                    logger.warning(
                        f"[Redis] Invalid control message: {message['data']}"
                    )

    # -- Latest Result Store (polling fallback) ----------------------------

    async def set_latest_result(self, user_id: str, result: dict, ttl: int = 300):
        """Store latest result in Redis for Flask polling fallback.

        TTL defaults to 300s (5 minutes). This allows Flask's existing
        /api/ergebnis endpoint to read from Redis instead of in-memory
        state during the migration period.
        """
        if not self._redis:
            return
        key = f"nerve:latest:{user_id}"
        await self._redis.set(key, json.dumps(result), ex=ttl)


# Module-level singleton (same pattern as Flask db instance)
redis_bridge = RedisBridge()
