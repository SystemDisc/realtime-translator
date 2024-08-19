import traceback

def format_error_message(e: Exception) -> str:
    """
    Format the exception message with the full traceback.

    Args:
        e (Exception): The exception to format.

    Returns:
        str: A formatted string with the exception message and traceback.
    """
    return ''.join(traceback.format_exception(type(e), e, e.__traceback__))
