class AppError(Exception):
    """ Base application exception with HTTP Status code. """
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, status_code=403)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, status_code=401)
