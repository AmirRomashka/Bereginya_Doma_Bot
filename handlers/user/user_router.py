"""
User Router Module
==================

This module serves as the central entry point for all user-related routers.
All user-facing functionality is imported and registered here for clean organization.

Module Structure:
-----------------
1. User Panel - Main menu and navigation
2. Registration - User onboarding and phone verification
3. User Menu - Catalog browsing and dish viewing
4. Shopping Cart - Order assembly and checkout
5. Order History - Past orders archive
6. Seasonal Dishes - Current promotions
7. About Us - Cafe information and contacts
8. Current Orders - Active order tracking

Usage:
------
The UserRouter is imported in main.py and included in the dispatcher.
"""

# =============================================================================
# IMPORTS
# =============================================================================

from aiogram import Router

# -----------------------------------------------------------------------------
# User Modules
# -----------------------------------------------------------------------------
from handlers.user.registration import RegistrationRouter          # 📝 User onboarding
from handlers.user.user_confirm_orders import UserConfirmOrdersRouter
from handlers.user.user_feedback import UserFeedbackRouter
from handlers.user.user_menu import UserMenuRouter                 # 🍽 Menu browsing
from handlers.user.user_panel import UserPanelRouter               # 🏠 Main dashboard
from handlers.user.user_basket import UserBasketRouter             # 🛒 Shopping cart
from handlers.user.user_order_history import UserOrdersRouter      # 📜 Order archive
from handlers.user.user_promotions import UserPromotionsRouter     # 🌿 Seasonal offers
from handlers.user.user_about import UserAboutRouter               # ℹ️ Cafe info
from handlers.user.user_current_order import UserCurrentOrdersRouter  # 🍳 Active orders

# =============================================================================
# ROUTER INITIALIZATION
# =============================================================================

UserRouter = Router(name="user_router")

"""
Main user router that aggregates all user-facing functionality.

This router is included in the main dispatcher and handles:
- User registration and authentication
- Menu browsing and dish selection
- Shopping cart management
- Order placement and tracking
- Order history viewing
- Cafe information
"""

# =============================================================================
# ROUTER REGISTRATION
# =============================================================================

UserRouter.include_routers(
    # 1. Main Panel - Dashboard and navigation
    UserPanelRouter,
    
    # 2. Registration - User onboarding
    RegistrationRouter,
    
    # 3. User Menu - Catalog browsing
    UserMenuRouter,
    
    # 4. Shopping Cart - Order assembly
    UserBasketRouter,
    
    # 5. Order History - Past orders
    UserOrdersRouter,
    
    # 6. Seasonal Dishes - Current promotions
    UserPromotionsRouter,
    
    # 7. About Us - Cafe information
    UserAboutRouter,
    
    # 8. Current Orders - Active order tracking
    UserCurrentOrdersRouter,

    # 9. Future user-related routers can be added here as needed
    UserConfirmOrdersRouter,

    UserFeedbackRouter



)

# =============================================================================
# USAGE EXAMPLE
# =============================================================================

"""
How to use in main.py:
---------------------
from handlers.user.user_router import UserRouter

dp.include_router(UserRouter)

All user functionality is now available under the UserRouter.
Each sub-router handles its own callbacks and states.

State Structure:
----------------
User states are defined in States/user_states.py:
- UserMenu: catalog, category, dish
- UserMenu.catalog: browsing categories
- UserMenu.category: viewing dishes in category
- UserMenu.dish: viewing dish details
- UserMenu.cart: managing shopping cart
- UserMenu.checkout_comment: adding order comment
- UserMenu.checkout_payment: payment confirmation
"""