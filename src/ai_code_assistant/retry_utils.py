"""Retry utilities for handling transient API failures."""

import time
import logging
from functools import wraps
from typing import Callable, Any, Optional, Tuple, Type
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (ClientError,),
    retryable_error_codes: Optional[Tuple[str, ...]] = None
) -> Callable:
    """Decorator to retry functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Multiplier for delay between retries
        max_delay: Maximum delay between retries in seconds
        retryable_exceptions: Tuple of exception types to retry on
        retryable_error_codes: Specific AWS error codes to retry on
    
    Returns:
        Decorated function with retry logic
    """
    if retryable_error_codes is None:
        retryable_error_codes = (
            'ThrottlingException',
            'TooManyRequestsException',
            'ServiceUnavailable',
            'RequestTimeout',
            'RequestTimeoutException',
            'InternalServerError',
            'BadGateway',
            'ServiceUnavailable',
            'GatewayTimeout'
        )
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    # Check if this is a retryable error
                    should_retry = False
                    error_code = None
                    
                    if isinstance(e, ClientError):
                        error_code = e.response.get('Error', {}).get('Code', '')
                        should_retry = error_code in retryable_error_codes
                    else:
                        # For non-ClientError exceptions in retryable_exceptions
                        should_retry = True
                    
                    if not should_retry or attempt == max_retries:
                        logger.error(f"Non-retryable error or max retries reached: {e}")
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(backoff_factor ** attempt, max_delay)
                    
                    logger.warning(
                        f"Retryable error (attempt {attempt + 1}/{max_retries + 1}): "
                        f"{error_code or type(e).__name__}. "
                        f"Retrying in {delay:.1f} seconds..."
                    )
                    
                    time.sleep(delay)
            
            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
            
        return wrapper
    return decorator


class RetryableBedrockError(Exception):
    """Custom exception for retryable Bedrock errors."""
    pass