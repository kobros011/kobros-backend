import enum

class UserType(enum.Enum):
    dev = "01" # Desarrolladores
    super = "02" # Super usuario
    admin = "03" # Admin
    partner = "04" # Socio
    collector = "05" # Recaudador

    @staticmethod
    def get_type(user_type: str):
        if user_type == UserType.dev.value: return UserType.dev.name
        if user_type == UserType.super.value: return UserType.super.name
        if user_type == UserType.admin.value: return UserType.admin.name
        if user_type == UserType.collector.value: return UserType.collector.name
        if user_type == UserType.partner.value: return UserType.partner.name