from enum import Enum

class PaymentMethod(Enum):
    MONTHLY     = 'mensual'
    FORTNIGHTLY = 'quincenal'
    WEEKLY      = 'semanal'
    DIARY       = 'diaria'
    FIXED_DATE  = 'dia_fijo'
class PaymentStatus(Enum):
    pending = 'pendiente'
    paid = 'pagado'
    default = 'mora'