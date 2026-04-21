# database/enumirate/orders_enum.py

import enum


class OrdersStatus(enum.Enum):
    """Статусы заказов."""
    
    ASSEMBLY = "assembly"                     # 8 символов
    AWAITING_ADDRESS_STATUS = "awaiting_addr" # 14 символов (было 24)
    VERIFICATION = "verification"             # 12 символов
    ACCEPTED = "accepted"                     # 8 символов
    READY_FOR_DELIVERY = "ready_delivery"     # 14 символов (было 19)
    COMPLETED = "completed"                   # 9 символов
    REFUSED = "refused"                       # 7 символов