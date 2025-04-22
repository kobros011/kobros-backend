import re
import logging
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger("app_logger")

class ValidatorErrors:
    @staticmethod
    def integrity_error(error: IntegrityError) ->str:

        error_message = str(error.orig)
        logger.error(f"IntegrityError capturado: {error_message}")

        # Violación de restricción UNIQUE
        if 'UNIQUE constraint failed' in error_message or ' duplicate key value' in error_message:
            match = re.search(r'UNIQUE constraint failed: (\w+)\.(\w+)', error_message)
            if match:
                table, column = match.groups()
                return f"El valor proporcionado para '{column}' ya existe."
            return "Ya existe un registro con los datos proporcionados."
        
        # Violación de restricción NOT NULL
        elif 'NOT NULL constraint failed' in error_message:
            match = re.search(r'NOT NULL constraint failed: (\w+)\.(\w+)', error_message)
            if match:
                table, column = match.groups()
                return f"El campo '{column}' es obligatorio y no puede estar vacío."
            return "Faltan campos obligatorios en la solicitud."
        
        # Violación de restricción de clave foránea
        elif 'FOREIGN KEY constraint failed' in error_message:
            return "Referencia a un registro inexistente. Verifica los datos ingresados."
        
        return "Error de integridad"