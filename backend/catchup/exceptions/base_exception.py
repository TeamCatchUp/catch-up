
class BaseDomainException(Exception):
    code = "domain_error"
    default_message = "Domain error"

    def __init__(
        self,
        message: str | None = None,
    ) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)
