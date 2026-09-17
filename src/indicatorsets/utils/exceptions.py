"""Exceptions raised while talking to the Epidata API."""


class InvalidApiKeyError(Exception):
    """Raised when an Epidata request returns 401 Unauthorized."""
