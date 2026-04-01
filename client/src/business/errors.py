class BusinessError(Exception):
    """Base class for business-layer errors."""
    pass


class ValidationError(BusinessError):
    """Raised when user input is invalid."""
    pass


class AuthError(BusinessError):
    """Raised when authentication fails."""
    pass


class ConversationNotFoundError(BusinessError):
    """Raised when conversation does not exist locally."""
    pass


class ReplayAttackError(BusinessError):
    """Raised when a replayed message is detected."""
    pass


class DecryptError(BusinessError):
    """Raised when message decryption fails."""
    pass
