class BeanquickError(Exception):
    """Base exception for Beanquick parsing."""
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message

class BeanquickParseError(BeanquickError):
    """Raised when parsing fails."""
    def __init__(self, message: str = "Failed to parse Beanquick string.") -> None:
        super().__init__(message)

class BeanquickIllegalCharError(BeanquickError):
    """Raised for illegal characters during lexing."""
    def __init__(self, char: str) -> None:
        super().__init__(f'Illegal character "{char}" in Beanquick string.')

class BeanquickConfigError(BeanquickError):
    """Raised for issues with the configuration."""
    pass