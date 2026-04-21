"""
Admin Router Module
===================

This module serves as the central entry point for all admin-related routers.
All admin functionality is imported and registered here for clean organization.

Module Structure:
-----------------
1. Delivery Management - Dates, statuses, and address zones
2. Mailing System - Broadcast messages to users
3. Menu Management - Categories and dishes CRUD
4. Order Management - Processing and tracking orders
5. Main Panel - Admin dashboard and navigation
6. Promotion Management - Seasonal and special offers
7. Admin Registration - Secret admin access
8. Statistics - Revenue and order analytics
9. Settings - System configuration
10. Help - Documentation and support

Usage:
------
The AdminRouter is imported in main.py and included in the dispatcher.
"""

# =============================================================================
# IMPORTS
# =============================================================================

from aiogram import Router

# -----------------------------------------------------------------------------
# Admin Modules
# -----------------------------------------------------------------------------
from handlers.admin.admin_delivery import AdminDeliveryRouter        # 🚚 Delivery dates & statuses
from handlers.admin.admin_mailing import MailingRouter               # 📢 Broadcast messages
from handlers.admin.admin_menu import MenuRouter                     # 🍽 Menu management
from handlers.admin.admin_orders import AdminOrdersRouter            # 📦 Order processing
from handlers.admin.admin_orders_without_status import AdminOrdersWithoutStatusRouter
from handlers.admin.admin_panel import AdminPanelRouter              # 🏠 Main admin dashboard
from handlers.admin.admin_promotion import AdminPromotionRouter      # 🌿 Seasonal dishes
from handlers.admin.admin_ready_orders import AdminReadyOrdersRouter
from handlers.admin.admin_reg import AdminRegRouter                  # 👑 Admin registration
from handlers.admin.admin_statistics import AdminStatisticsRouter    # 📊 Analytics & revenue
from handlers.admin.admin_settings import AdminSettingsRouter        # ⚙️ Configuration
from handlers.admin.admin_help import AdminHelpRouter
from handlers.admin.admin_viewing_reviews import AdminFeedbackRouter                # ❓ Documentation

# =============================================================================
# ROUTER INITIALIZATION
# =============================================================================

AdminRouter = Router(name="admin_router")

"""
Main admin router that aggregates all admin functionality.

This router is included in the main dispatcher and handles:
- All admin panel navigation
- Menu and dish management
- Order processing workflows
- User communications
- System configuration
"""

# =============================================================================
# ROUTER REGISTRATION
# =============================================================================

AdminRouter.include_routers(
    # 1. Main Panel - Dashboard and navigation
    AdminPanelRouter,
    
    # 2. Order Management - Processing orders
    AdminOrdersRouter,
    
    # 3. Statistics - Revenue and analytics
    AdminStatisticsRouter,
    
    # 4. Settings - System configuration
    AdminSettingsRouter,
    
    # 5. Help - Documentation
    AdminHelpRouter,
    
    # 6. Admin Registration - Secret access
    AdminRegRouter,
    
    # 7. Menu Management - Categories and dishes
    MenuRouter,
    
    # 8. Mailing - Broadcast messages
    MailingRouter,
    
    # 9. Promotions - Seasonal offers
    AdminPromotionRouter,
    
    # 10. Delivery Management - Dates, zones, addresses
    AdminDeliveryRouter,

    # 11. Future admin-related routers can be added here as needed
    AdminOrdersWithoutStatusRouter,

    #
    AdminReadyOrdersRouter,

    AdminFeedbackRouter
)

# =============================================================================
# USAGE EXAMPLE
# =============================================================================

"""
How to use in main.py:
---------------------
from handlers.admin.admin_router import AdminRouter

dp.include_router(AdminRouter)

All admin functionality is now available under the AdminRouter.
Each sub-router handles its own callbacks and states.
"""