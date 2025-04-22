import enum

class UserType(enum.Enum):
    admin = "01" # Admin
    partner = "02" # Socio
    collector = "03" # Recaudador

    @staticmethod
    def get_type(user_type: str):
        if user_type == UserType.admin.value: return UserType.admin.name
        if user_type == UserType.collector.value: return UserType.admin.name
        if user_type == UserType.partner.value: return UserType.admin.name