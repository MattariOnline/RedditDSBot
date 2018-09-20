
"""Utility functions that don't belong in the other files."""
import time
import traceback

class RetryError(Exception):
    pass

def backoff(tries):
    """
    Waits some duration of time in order to prevent server overloading when
    in high load.

    Args:
        tries: The number of unsuccessful attempts in a row
    """
    sleep_time = None
    if tries < 30:
        sleep_time = tries * 60
    else:
        sleep_time = 30 * 60

    print(f'Sleeping for {sleep_time} seconds')
    time.sleep(sleep_time)

def until_success(doer, args=None, kwargs=None, failure_fn=backoff, max_attempts=None):
    """
    Repeats the doer until the first result is truthy.

    Args:
        doer: A function that returns a tuple of two things, bool and any.
            If the bool is True, the function immediately returns the second
            value in the tuple. If the function raises an error, it is captured,
            printed, and treated as if it returned False, None
        args: Arguments to pass to doer as an array. Also passed to the failure
            function after tries.
        kwargs: Keyword arguments to pass to doer and failure function.
        failure_fn: The function to call upon failure. Passed the number of
            unsuccessful attempts so far. Defaults to backing off.
        max_attempts: The maximum number of attempts to do before raising a
            RetryError. None for no limit. Defaults to no limit.

    Returns:
        The second result of the tuple returned by doer.

    Raises:
        RetryError: if this exceeds the maximum attempts.
    """

    if args is None:
        args = []

    if kwargs is None:
        kwargs = {}

    tries = 0
    while max_attempts is None or tries < max_attempts:
        tries = tries + 1
        success, result = None, None
        try:
            success, result = doer(*args, **kwargs)
        except Exception:
            traceback.print_exc()

        if success:
            return result

        failure_fn(tries, *args, **kwargs)

    raise RetryError(f'Number attempts exceeded max attempts={max_attempts}')
