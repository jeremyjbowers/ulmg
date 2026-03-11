# ABOUTME: Query-level caching utilities for ULMG using Valkey (Redis-compatible).
# ABOUTME: Caches expensive queries for homepage, team pages, and player pages (12h TTL).

import logging
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

CACHE_PREFIX = "ulmg"
CACHE_TTL = getattr(settings, "CACHE_TTL", 60 * 60 * 12)  # 12 hours default


def is_valkey_active():
    """
    Check if Valkey cache backend is reachable.
    Returns True if cache is working, False otherwise.
    """
    try:
        cache.set("ulmg:health_check", "ok", timeout=10)
        return cache.get("ulmg:health_check") == "ok"
    except Exception as e:
        logger.debug("Valkey health check failed: %s", e)
        return False


def cache_key(*parts):
    """Build a namespaced cache key. Django adds KEY_PREFIX and version automatically."""
    return ":".join([CACHE_PREFIX] + [str(p) for p in parts])


def get_cached_or_compute(key, compute_fn, timeout=CACHE_TTL):
    """
    Get value from cache or compute and store it.
    compute_fn is a callable that takes no args and returns the value to cache.
    """
    try:
        return cache.get_or_set(key, compute_fn, timeout=timeout)
    except Exception as e:
        logger.warning("Cache get_or_set failed for %s: %s", key, e)
        return compute_fn()


def delete_cache_key(key):
    """Delete a single cache key. Returns True if deleted."""
    try:
        return cache.delete(key)
    except Exception as e:
        logger.warning("Cache delete failed for %s: %s", key, e)
        return False


def get_all_cache_keys(pattern=None):
    """
    Get all cache keys, optionally filtered by pattern.
    Pattern should match django-valkey's key format (e.g. "ulmg:*").
    Returns list of full keys as stored in Valkey.
    """
    if pattern is None:
        pattern = f"{CACHE_PREFIX}:*"
    try:
        keys = cache.keys(pattern)
        return sorted(keys) if keys else []
    except Exception as e:
        logger.warning("Cache keys failed: %s", e)
        return []


def delete_cache_key_for_admin(key):
    """
    Delete a cache key for the admin UI purge action.
    Keys from get_all_cache_keys() are logical keys - use cache.delete() which
    applies the correct prefix/version formatting.
    """
    try:
        return cache.delete(key)
    except Exception as e:
        logger.warning("Cache delete failed for %s: %s", key, e)
        return False
