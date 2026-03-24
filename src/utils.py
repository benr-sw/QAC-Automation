import time
import logging
import anthropic


def claude_with_retry(client, logger: logging.Logger, max_retries: int = 4, **kwargs):
    """
    Call client.messages.create with exponential backoff on 529 overloaded errors.
    All keyword arguments are passed through to client.messages.create unchanged.
    """
    delays = [30, 60, 120, 180]
    for attempt in range(max_retries + 1):
        try:
            return client.messages.create(**kwargs)
        except (anthropic.OverloadedError, anthropic.APIStatusError) as e:
            if isinstance(e, anthropic.APIStatusError) and e.status_code != 529:
                raise
            if attempt == max_retries:
                logger.error("Claude API still overloaded after max retries — giving up.")
                raise
            delay = delays[min(attempt, len(delays) - 1)]
            logger.warning(
                f"Claude API overloaded — waiting {delay}s before retry "
                f"(attempt {attempt + 1}/{max_retries})..."
            )
            time.sleep(delay)
