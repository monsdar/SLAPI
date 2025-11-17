from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional, Protocol, TypeVar

from .cache import FileCache

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ClientProtocol(Protocol):
    """Protocol defining the interface that client decorators expect."""

    def fetch_leagues(self) -> List[Dict[str, Any]]:
        """Fetch leagues from the upstream API."""
        ...

    def fetch_standings(self, league_id: str) -> Dict[str, Any]:
        """Fetch standings for a league from the upstream API."""
        ...

    def fetch_matches(self, league_id: str) -> Dict[str, Any]:
        """Fetch matches for a league from the upstream API."""
        ...

    def fetch_associations(self) -> Dict[str, Any]:
        """Fetch associations (Verbände) from the upstream API."""
        ...

    def fetch_club_leagues(self, club_name: str, verband_id: int) -> List[Dict[str, Any]]:
        """Fetch leagues for a specific club from the upstream API."""
        ...


class CachedClient:
    """
    Decorator that adds caching functionality to client methods.
    Caches responses based on method name and arguments.
    """

    def __init__(
        self,
        client: ClientProtocol,
        cache: Optional[FileCache] = None,
    ) -> None:
        self._client = client
        self._cache = cache or FileCache()

    def fetch_leagues(self, use_cache: bool = True, **kwargs: Any) -> List[Dict[str, Any]]:
        """
        Fetch leagues with caching support.
        
        Args:
            use_cache: If True, check cache first and store results. If False, bypass cache.
            **kwargs: Additional arguments (ignored, but kept for compatibility with decorator chain).
        
        Returns:
            List of league dictionaries.
        """
        cache_key = "leagues"
        
        if use_cache:
            cached = self._cache.read(cache_key)
            if cached is not None:
                logger.debug("Cache hit for key: %s", cache_key)
                return cached
        
        logger.debug("Cache miss for key: %s, fetching from client", cache_key)
        # Don't pass use_cache to underlying client - it's only relevant for caching
        result = self._client.fetch_leagues()
        
        if use_cache:
            self._cache.write(cache_key, result)
        
        return result

    def fetch_standings(self, league_id: str, use_cache: bool = True, **kwargs: Any) -> Dict[str, Any]:
        """
        Fetch standings with caching support.
        
        Args:
            league_id: The league ID to fetch standings for.
            use_cache: If True, check cache first and store results. If False, bypass cache.
            **kwargs: Additional arguments (ignored, but kept for compatibility with decorator chain).
        
        Returns:
            Dictionary containing standings data.
        """
        cache_key = f"standings_{league_id}"
        
        if use_cache:
            cached = self._cache.read(cache_key)
            if cached is not None:
                logger.debug("Cache hit for key: %s", cache_key)
                return cached
        
        logger.debug("Cache miss for key: %s, fetching from client", cache_key)
        result = self._client.fetch_standings(league_id)
        
        if use_cache:
            self._cache.write(cache_key, result)
        
        return result

    def fetch_matches(self, league_id: str, use_cache: bool = True, **kwargs: Any) -> Dict[str, Any]:
        """
        Fetch matches with caching support.
        
        Args:
            league_id: The league ID to fetch matches for.
            use_cache: If True, check cache first and store results. If False, bypass cache.
            **kwargs: Additional arguments (ignored, but kept for compatibility with decorator chain).
        
        Returns:
            Dictionary containing matches data.
        """
        cache_key = f"matches_{league_id}"
        
        if use_cache:
            cached = self._cache.read(cache_key)
            if cached is not None:
                logger.debug("Cache hit for key: %s", cache_key)
                return cached
        
        logger.debug("Cache miss for key: %s, fetching from client", cache_key)
        result = self._client.fetch_matches(league_id)
        
        if use_cache:
            self._cache.write(cache_key, result)
        
        return result

    def fetch_associations(self, use_cache: bool = True, **kwargs: Any) -> Dict[str, Any]:
        """
        Fetch Verbände with caching support.
        
        Args:
            use_cache: If True, check cache first and store results. If False, bypass cache.
            **kwargs: Additional arguments (ignored, but kept for compatibility).
        
        Returns:
            Dictionary containing associations data.
        """
        cache_key = "associations"

        if use_cache:
            cached = self._cache.read(cache_key)
            if cached is not None:
                logger.debug("Cache hit for key: %s", cache_key)
                return cached

        logger.debug("Cache miss for key: %s, fetching from client", cache_key)
        result = self._client.fetch_associations(**kwargs)

        if use_cache:
            self._cache.write(cache_key, result)

        return result

    def fetch_club_leagues(
        self, club_name: str, verband_id: int = 7, use_cache: bool = True, **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """
        Fetch club leagues with caching support.
        
        Args:
            club_name: Name of the club to search for.
            verband_id: Association ID (default: 7 for Niedersachsen).
            use_cache: If True, check cache first and store results. If False, bypass cache.
            **kwargs: Additional arguments (ignored, but kept for compatibility).
        
        Returns:
            List of league dictionaries.
        """
        cache_key = f"club_leagues_{verband_id}_{club_name}"

        if use_cache:
            cached = self._cache.read(cache_key)
            if cached is not None:
                logger.debug("Cache hit for key: %s", cache_key)
                return cached

        logger.debug("Cache miss for key: %s, fetching from client", cache_key)
        result = self._client.fetch_club_leagues(club_name, verband_id)

        if use_cache:
            self._cache.write(cache_key, result)

        return result


class RetryClient:
    """
    Decorator that adds retry and throttling logic to client methods.
    Handles transient failures and rate limiting.
    """

    def __init__(
        self,
        client: ClientProtocol,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        backoff_factor: float = 2.0,
        throttle_delay: float = 0.5,
    ) -> None:
        self._client = client
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.backoff_factor = backoff_factor
        self.throttle_delay = throttle_delay
        self._last_request_time: Optional[float] = None

    def _apply_throttle(self) -> None:
        """Apply rate limiting by ensuring minimum time between requests."""
        if self._last_request_time is not None:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.throttle_delay:
                sleep_time = self.throttle_delay - elapsed
                logger.debug("Throttling request, sleeping for %.2f seconds", sleep_time)
                time.sleep(sleep_time)
        self._last_request_time = time.time()

    def _retry_with_backoff(
        self,
        func: Callable[[], T],
        retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
    ) -> T:
        """
        Execute a function with retry logic and exponential backoff.
        
        Args:
            func: The function to execute.
            retryable_exceptions: Tuple of exception types that should trigger retries.
        
        Returns:
            The result of the function call.
        
        Raises:
            The last exception if all retries are exhausted.
        """
        last_exception: Optional[Exception] = None
        delay = self.retry_delay

        for attempt in range(self.max_retries + 1):
            try:
                self._apply_throttle()
                return func()
            except retryable_exceptions as e:
                last_exception = e
                if attempt < self.max_retries:
                    logger.warning(
                        "Attempt %d/%d failed: %s. Retrying in %.2f seconds...",
                        attempt + 1,
                        self.max_retries + 1,
                        str(e),
                        delay,
                    )
                    time.sleep(delay)
                    delay *= self.backoff_factor
                else:
                    logger.error(
                        "All %d retry attempts exhausted. Last error: %s",
                        self.max_retries + 1,
                        str(e),
                    )

        if last_exception:
            raise last_exception
        raise RuntimeError("Retry logic failed without exception")

    def fetch_leagues(self, **kwargs: Any) -> List[Dict[str, Any]]:
        """
        Fetch leagues with retry and throttling support.
        
        Args:
            **kwargs: Ignored (base client doesn't accept parameters, but kept for decorator chain compatibility).
        
        Returns:
            List of league dictionaries.
        """
        # Base client doesn't accept kwargs, so we don't pass them through
        return self._retry_with_backoff(
            lambda: self._client.fetch_leagues(),
            retryable_exceptions=(ConnectionError, TimeoutError, Exception),
        )

    def fetch_standings(self, league_id: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Fetch standings with retry and throttling support.
        
        Args:
            league_id: The league ID to fetch standings for.
            **kwargs: Additional arguments passed through to the underlying client.
        
        Returns:
            Dictionary containing standings data.
        """
        return self._retry_with_backoff(
            lambda: self._client.fetch_standings(league_id),
            retryable_exceptions=(ConnectionError, TimeoutError, Exception),
        )

    def fetch_matches(self, league_id: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Fetch matches with retry and throttling support.
        
        Args:
            league_id: The league ID to fetch matches for.
            **kwargs: Additional arguments passed through to the underlying client.
        
        Returns:
            Dictionary containing matches data.
        """
        return self._retry_with_backoff(
            lambda: self._client.fetch_matches(league_id),
            retryable_exceptions=(ConnectionError, TimeoutError, Exception),
        )

    def fetch_associations(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Fetch Verbände with retry and throttling support.
        
        Args:
            **kwargs: Additional arguments passed through to the underlying client.
        
        Returns:
            Dictionary containing associations data.
        """
        return self._retry_with_backoff(
            lambda: self._client.fetch_associations(**kwargs),
            retryable_exceptions=(ConnectionError, TimeoutError, Exception),
        )

    def fetch_club_leagues(self, club_name: str, verband_id: int = 7, **kwargs: Any) -> List[Dict[str, Any]]:
        """
        Fetch club leagues with retry and throttling support.
        
        Args:
            club_name: Name of the club to search for.
            verband_id: Association ID (default: 7 for Niedersachsen).
            **kwargs: Additional arguments passed through to the underlying client.
        
        Returns:
            List of league dictionaries.
        """
        return self._retry_with_backoff(
            lambda: self._client.fetch_club_leagues(club_name, verband_id, **kwargs),
            retryable_exceptions=(ConnectionError, TimeoutError, Exception),
        )


class TransformClient:
    """
    Decorator that adds data transformation capabilities to client methods.
    Currently a placeholder for future transformation logic.
    """

    def __init__(self, client: ClientProtocol) -> None:
        self._client = client

    def fetch_leagues(self, **kwargs: Any) -> List[Dict[str, Any]]:
        """
        Fetch leagues with transformation support.
        
        Args:
            **kwargs: Ignored (base client doesn't accept parameters, but kept for decorator chain compatibility).
        
        Returns:
            Transformed list of league dictionaries.
        """
        # Base client doesn't accept kwargs, so we don't pass them through
        result = self._client.fetch_leagues()
        # Placeholder for future transformation logic
        # For now, just pass through
        return result

    def fetch_standings(self, league_id: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Fetch standings with transformation support.
        
        Args:
            league_id: The league ID to fetch standings for.
            **kwargs: Additional arguments passed through to the underlying client.
        
        Returns:
            Transformed standings dictionary.
        """
        result = self._client.fetch_standings(league_id, **kwargs)
        # Placeholder for future transformation logic
        # For now, just pass through
        return result

    def fetch_matches(self, league_id: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Fetch matches with transformation support.
        
        Args:
            league_id: The league ID to fetch matches for.
            **kwargs: Additional arguments passed through to the underlying client.
        
        Returns:
            Transformed matches dictionary.
        """
        result = self._client.fetch_matches(league_id, **kwargs)
        # Placeholder for future transformation logic
        # For now, just pass through
        return result

    def fetch_associations(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Fetch Verbände with transformation support.
        
        Args:
            **kwargs: Additional arguments passed through to the underlying client.
        
        Returns:
            Transformed associations dictionary.
        """
        result = self._client.fetch_associations(**kwargs)
        # Placeholder for future transformation logic
        # For now, just pass through
        return result

    def fetch_club_leagues(self, club_name: str, verband_id: int = 7, **kwargs: Any) -> List[Dict[str, Any]]:
        """
        Fetch club leagues with transformation support.
        
        Args:
            club_name: Name of the club to search for.
            verband_id: Association ID (default: 7 for Niedersachsen).
            **kwargs: Additional arguments passed through to the underlying client.
        
        Returns:
            Transformed list of league dictionaries.
        """
        result = self._client.fetch_club_leagues(club_name, verband_id, **kwargs)
        # Placeholder for future transformation logic
        # For now, just pass through
        return result


class MetricsClient:
    """
    Decorator that adds metrics collection to client methods.
    Currently a placeholder for future metrics implementation.
    """

    def __init__(self, client: ClientProtocol) -> None:
        self._client = client

    def fetch_leagues(self, **kwargs: Any) -> List[Dict[str, Any]]:
        """
        Fetch leagues with metrics collection.
        
        Args:
            **kwargs: Passed through to the underlying client.
        
        Returns:
            List of league dictionaries.
        """
        start_time = time.time()
        try:
            result = self._client.fetch_leagues(**kwargs)
            duration = time.time() - start_time
            logger.debug("fetch_leagues completed in %.3f seconds", duration)
            # Placeholder for future metrics collection
            # e.g., self._metrics.record_latency("fetch_leagues", duration)
            # e.g., self._metrics.increment_counter("fetch_leagues.success")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.debug("fetch_leagues failed after %.3f seconds", duration)
            # Placeholder for future metrics collection
            # e.g., self._metrics.increment_counter("fetch_leagues.error")
            raise

    def fetch_standings(self, league_id: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Fetch standings with metrics collection.
        
        Args:
            league_id: The league ID to fetch standings for.
            **kwargs: Passed through to the underlying client.
        
        Returns:
            Dictionary containing standings data.
        """
        start_time = time.time()
        try:
            result = self._client.fetch_standings(league_id, **kwargs)
            duration = time.time() - start_time
            logger.debug("fetch_standings completed in %.3f seconds for league_id=%s", duration, league_id)
            # Placeholder for future metrics collection
            # e.g., self._metrics.record_latency("fetch_standings", duration)
            # e.g., self._metrics.increment_counter("fetch_standings.success")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.debug("fetch_standings failed after %.3f seconds for league_id=%s", duration, league_id)
            # Placeholder for future metrics collection
            # e.g., self._metrics.increment_counter("fetch_standings.error")
            raise

    def fetch_matches(self, league_id: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Fetch matches with metrics collection.
        
        Args:
            league_id: The league ID to fetch matches for.
            **kwargs: Passed through to the underlying client.
        
        Returns:
            Dictionary containing matches data.
        """
        start_time = time.time()
        try:
            result = self._client.fetch_matches(league_id, **kwargs)
            duration = time.time() - start_time
            logger.debug("fetch_matches completed in %.3f seconds for league_id=%s", duration, league_id)
            # Placeholder for future metrics collection
            # e.g., self._metrics.record_latency("fetch_matches", duration)
            # e.g., self._metrics.increment_counter("fetch_matches.success")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.debug("fetch_matches failed after %.3f seconds for league_id=%s", duration, league_id)
            # Placeholder for future metrics collection
            # e.g., self._metrics.increment_counter("fetch_matches.error")
            raise

    def fetch_associations(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Fetch Verbände with metrics collection.
        
        Args:
            **kwargs: Passed through to the underlying client.
        
        Returns:
            Dictionary containing associations data.
        """
        start_time = time.time()
        try:
            result = self._client.fetch_associations(**kwargs)
            duration = time.time() - start_time
            logger.debug("fetch_associations completed in %.3f seconds", duration)
            return result
        except Exception:
            duration = time.time() - start_time
            logger.debug("fetch_associations failed after %.3f seconds", duration)
            raise

    def fetch_club_leagues(self, club_name: str, verband_id: int = 7, **kwargs: Any) -> List[Dict[str, Any]]:
        """
        Fetch club leagues with metrics collection.
        
        Args:
            club_name: Name of the club to search for.
            verband_id: Association ID (default: 7 for Niedersachsen).
            **kwargs: Passed through to the underlying client.
        
        Returns:
            List of league dictionaries.
        """
        start_time = time.time()
        try:
            result = self._client.fetch_club_leagues(club_name, verband_id, **kwargs)
            duration = time.time() - start_time
            logger.debug(
                "fetch_club_leagues completed in %.3f seconds for club_name=%s, verband_id=%s",
                duration,
                club_name,
                verband_id,
            )
            return result
        except Exception:
            duration = time.time() - start_time
            logger.debug(
                "fetch_club_leagues failed after %.3f seconds for club_name=%s, verband_id=%s",
                duration,
                club_name,
                verband_id,
            )
            raise

