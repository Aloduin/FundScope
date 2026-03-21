"""L1 memory cache with TTL support.

Provides a TTL-based in-memory cache for data source methods.
Cache entries automatically expire after a configurable time period.
"""
from functools import wraps
from typing import Any, Callable
import cachetools


# Global TTL cache: maxsize=1000, ttl=1800 seconds (30 minutes)
_l1_cache: cachetools.TTLCache = cachetools.TTLCache(maxsize=1000, ttl=1800)


def _make_cache_key(key_prefix: str, method_name: str, args: tuple, kwargs: dict) -> str:
    """Build cache key from method arguments.

    Format: key_prefix:method_name:arg1:arg2:key=value

    Args:
        key_prefix: Category prefix (e.g., "fund_info", "nav_history")
        method_name: Name of the cached method
        args: Positional arguments (excluding self)
        kwargs: Keyword arguments

    Returns:
        String cache key
    """
    parts = [key_prefix, method_name]

    # Add positional arguments
    for arg in args:
        parts.append(str(arg))

    # Add keyword arguments (sorted for consistency)
    for key in sorted(kwargs.keys()):
        parts.append(f"{key}={kwargs[key]}")

    return ":".join(parts)


def cached(key_prefix: str) -> Callable:
    """Decorator to cache method results in L1 cache.

    Args:
        key_prefix: Category prefix for cache keys (e.g., "fund_info", "nav_history")

    Returns:
        Decorator function

    Example:
        @cached(key_prefix="fund_info")
        def get_fund_basic_info(self, fund_code: str) -> dict:
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Build cache key
            # Skip 'self' argument (first positional arg in methods)
            method_args = args[1:] if args else args
            key = _make_cache_key(key_prefix, func.__name__, method_args, kwargs)

            # Check cache
            if key in _l1_cache:
                return _l1_cache[key]

            # Call original method
            result = func(*args, **kwargs)

            # Store in cache
            _l1_cache[key] = result

            return result
        return wrapper
    return decorator


def clear_l1_cache() -> None:
    """Clear all entries from L1 cache.

    Use this when you need to force refresh cached data.
    """
    _l1_cache.clear()
