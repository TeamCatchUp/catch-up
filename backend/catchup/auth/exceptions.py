class OAuthError(Exception):
    """OAuth 인증 과정에서 발생하는 기본 예외"""
    
    def __init__(
        self,
        message: str,
        details: str | None = None
    ):
        self.message = message
        self.details = details