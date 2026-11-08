class AppException(Exception):
    """Excepción base para la aplicación."""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code

class NotFoundException(AppException):
    """Excepción para recursos no encontrados."""
    def __init__(self, message: str = "Recurso no encontrado"):
        super().__init__(message, status_code=404)

class ConflictException(AppException):
    """Excepción para conflictos, como duplicados."""
    def __init__(self, message: str = "Conflicto de datos"):
        super().__init__(message, status_code=409)


class BadRequestException(AppException):
    """Excepción para solicitudes que no cumplen una regla de negocio."""
    def __init__(self, message: str = "Solicitud inválida"):
        super().__init__(message, status_code=400)
