import logging

_logger = logging.getLogger(__name__)


class OpenSPPOAuthJWTException(Exception):
    def __init__(self, message):
        super().__init__(message)
        _logger.error("OAuth JWT error: %s", message)
