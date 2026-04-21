"""
FSM States Module
=================

This module defines all Finite State Machine states for the bot.
"""

from aiogram.fsm.state import StatesGroup, State


# =============================================================================
# START STATE
# =============================================================================

class StartState(StatesGroup):
    """States for the start menu and general information."""
    start = State()
    about_us = State()


# =============================================================================
# REGISTRATION STATES
# =============================================================================

class RegistrationState(StatesGroup):
    """States for user registration process."""
    phone_number = State()
    add_user = State()
    birth_date = State()


# =============================================================================
# ADMIN PANEL STATES
# =============================================================================

class AdminPanel(StatesGroup):
    """
    States for admin panel management.
    
    Categories:
    -----------
    - MAIN: Navigation and main panel states
    - CATEGORY MANAGEMENT: Creating and editing categories
    - DISH CREATION: Multi-step dish creation flow
    - DISH EDITING: Editing dish fields
    - DELIVERY MANAGEMENT: Dates, limits, and statuses
    - INTERFACE CONFIGURATION: Customizing bot appearance
    """
    
    # -------------------------------------------------------------------------
    # MAIN NAVIGATION
    # -------------------------------------------------------------------------
    admin_panel = State()          # Главная панель администратора
    my_menu = State()              # Управление меню
    category = State()             # Управление категорией
    
    # -------------------------------------------------------------------------
    # CATEGORY MANAGEMENT
    # -------------------------------------------------------------------------
    new_category_name_fsm = State()      # Создание категории (ввод названия)
    edit_category_name_fsm = State()     # Редактирование категории (ввод нового названия)
    
    # -------------------------------------------------------------------------
    # DISH CREATION FLOW (5 шагов)
    # -------------------------------------------------------------------------
    new_dish_name_fsm = State()          # Шаг 1: Ввод названия блюда
    new_dish_description_fsm = State()   # Шаг 2: Ввод описания блюда
    new_dish_price_fsm = State()         # Шаг 3: Ввод цены блюда
    new_dish_image_fsm = State()         # Шаг 4: Загрузка фото блюда
    save_dish_fsm = State()              # Шаг 5: Подтверждение сохранения
    
    # -------------------------------------------------------------------------
    # DISH EDITING FLOW
    # -------------------------------------------------------------------------
    edit_dish_name = State()             # Редактирование названия
    edit_dish_description = State()      # Редактирование описания
    edit_dish_price = State()            # Редактирование цены
    edit_dish_image = State()            # Редактирование фото
    edit_dish_category = State()         # Редактирование категории
    
    # -------------------------------------------------------------------------
    # DELIVERY MANAGEMENT (Доставка)
    # -------------------------------------------------------------------------
    add_delivery_date = State()          # Добавление даты доставки (ввод даты)
    add_delivery_limit = State()         # Установка лимита заказов на дату
    edit_delivery_limit = State()        # Редактирование лимита заказов
    edit_delivery_note = State()         # Редактирование примечания к дате
    add_delivery_status_name = State()   # Добавление статуса доставки (ввод названия)
    add_delivery_status_price = State()  # Добавление статуса доставки (ввод цены)
    edit_delivery_status = State()       # Редактирование статуса доставки
    
    # -------------------------------------------------------------------------
    # BULK DELIVERY OPERATIONS (Массовые операции с доставкой)
    # -------------------------------------------------------------------------
    bulk_move_confirm = State()          # Подтверждение массового переноса заказов
    close_delivery_confirm = State()     # Подтверждение закрытия доставки
    
    # -------------------------------------------------------------------------
    # INTERFACE CONFIGURATION
    # -------------------------------------------------------------------------
    edit_interface_photo = State()       # Редактирование фото интерфейса
    edit_interface_text = State()        # Редактирование текста интерфейса


# =============================================================================
# MAILING STATES
# =============================================================================

class MailingStates(StatesGroup):
    """States for mailing process."""
    select_audience = State()    # Выбор аудитории (всем/активным/новым/админам)
    enter_text = State()         # Ввод текста сообщения
    add_photo = State()          # Добавление фото (опционально)
    add_buttons = State()        # Добавление кнопок (опционально)
    preview = State()            # Предпросмотр перед отправкой
    sending = State()            # Отправка (процесс)


# =============================================================================
# USER MENU STATES
# =============================================================================

class UserMenu(StatesGroup):
    """
    States for user menu navigation.
    
    Categories:
    -----------
    - MAIN NAVIGATION: Browsing catalog and dishes
    - CHECKOUT FLOW: Order placement steps
    - ADDRESS MANAGEMENT: Adding and editing addresses (подробный ввод адреса)
    - CONFIRM ORDERS FLOW: Payment and delivery confirmation
    - ORDER MANAGEMENT: Viewing and managing orders
    - TIME RANGE SELECTION: Choosing delivery time range
    - FEEDBACK FLOW: User feedback and reviews
    """
    
    # -------------------------------------------------------------------------
    # MAIN NAVIGATION
    # -------------------------------------------------------------------------
    catalog = State()            # Просмотр каталога (выбор категории)
    category = State()           # Просмотр категории (выбор блюда)
    dish = State()               # Просмотр деталей блюда
    cart = State()               # Просмотр корзины
    orders = State()             # История заказов
    profile = State()            # Профиль пользователя
    
    # -------------------------------------------------------------------------
    # CHECKOUT FLOW (Оформление заказа)
    # -------------------------------------------------------------------------
    checkout_comment = State()   # Шаг 1: Ввод комментария к заказу
    checkout_payment = State()   # Шаг 2: Ожидание фото чека
    
    # -------------------------------------------------------------------------
    # ADDRESS MANAGEMENT (Управление адресами) — РАСШИРЕННЫЙ ВВОД
    # -------------------------------------------------------------------------
    checkout_address = State()           # Выбор адреса доставки из списка
    add_address_name = State()           # Ввод названия адреса (Дом/Работа/Дача)
    add_address_coordinates = State()    # Выбор способа ввода координат
    add_address_location = State()       # Отправка геопозиции (кнопка)
    add_address_manual = State()         # Ручной ввод координат
    add_address_street = State()         # Ввод улицы
    add_address_house = State()          # Ввод номера дома
    add_address_building = State()       # Ввод корпуса/строения (опционально)
    add_address_apartment = State()      # Ввод квартиры/офиса (опционально)
    add_address_floor = State()          # Ввод этажа (опционально)
    add_address_entrance = State()       # Ввод подъезда (опционально)
    add_address_intercom = State()       # Ввод кода домофона (опционально)
    add_address_comment = State()        # Ввод комментария для курьера (опционально)
    confirm_address = State()            # Подтверждение добавленного адреса
    confirm_delivery_address = State()   # Подтверждение выбранного адреса для заказа
    
    # -------------------------------------------------------------------------
    # CONFIRM ORDERS FLOW (Подтверждение заказов, готовых к оплате)
    # -------------------------------------------------------------------------
    confirm_orders = State()                 # Просмотр списка заказов для подтверждения
    confirm_order_detail = State()           # Просмотр деталей заказа
    confirm_order_delivery_date = State()    # Выбор даты доставки
    confirm_order_time_range = State()       # Выбор временного диапазона для подтверждения заказа
    confirm_order_time_confirmed = State()   # Время выбрано, переход к оплате
    confirm_order_comment = State()          # Ввод комментария при подтверждении заказа
    confirm_order_payment = State()          # Ожидание фото чека при подтверждении заказа
    
    # -------------------------------------------------------------------------
    # ORDER MANAGEMENT (Управление заказами)
    # -------------------------------------------------------------------------
    order_detail = State()               # Просмотр деталей заказа из истории
    order_cancel_confirm = State()       # Подтверждение отмены заказа
    order_repeat_confirm = State()       # Подтверждение повторения заказа
    order_received_confirm = State()     # Подтверждение получения заказа (READY_FOR_DELIVERY → COMPLETED)
    
    # -------------------------------------------------------------------------
    # TIME RANGE SELECTION (Выбор временного диапазона доставки) — ДЛЯ КОРЗИНЫ
    # -------------------------------------------------------------------------
    select_time_range = State()          # Выбор часов начала и конца диапазона (9-20)
    time_range_confirmed = State()       # Диапазон выбран, переход к оплате
    
    # -------------------------------------------------------------------------
    # FEEDBACK FLOW (Отзывы)
    # -------------------------------------------------------------------------
    feedback_text = State()              # Ввод текста отзыва


# =============================================================================
# PROMOTION STATES
# =============================================================================

class PromotionStates(StatesGroup):
    """
    States for promotion (seasonal dishes) management.
    """
    main_menu = State()          # Главное меню управления акциями
    select_category = State()    # Выбор категории для акционных блюд
    select_dish = State()        # Выбор блюда для акции
    bulk_select = State()        # Массовый выбор блюд для акции
    confirm_bulk = State()       # Подтверждение массового обновления акций


# =============================================================================
# STATE SUMMARY
# =============================================================================

"""
Total States Count:
------------------
- StartState:         2 states
- RegistrationState:  3 states
- AdminPanel:         24 states
- MailingStates:      6 states
- UserMenu:           32 states  (добавлено 1 состояние для отзыва: feedback_text)
- PromotionStates:    5 states
-------------------------------------------------
TOTAL:                72 states

Added to UserMenu (Feedback Flow):
---------------------------------
- feedback_text                  # Ввод текста отзыва

Total UserMenu states: 31 → 32 (+1)

Legend:
-------
✅ = Fully implemented
🟡 = Partially implemented
❌ = Not implemented yet
"""