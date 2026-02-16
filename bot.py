"""
Subscription Manager Bot with Web3 Integration
Supports Arabic and English languages
"""

import os
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from database import Database
from locales import get_text, set_user_language, get_user_language

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
ADMIN_IDS = list(map(int, os.getenv('ADMIN_IDS', '').split(','))) if os.getenv('ADMIN_IDS') else []
WEBAPP_URL = os.getenv('WEBAPP_URL', 'https://your-webapp-url.com')
CRYPTO_WALLET_ADDRESS = os.getenv('WALLET_ADDRESS', 'YOUR_WALLET_ADDRESS')

db = Database()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user = update.effective_user
    user_id = user.id
    
    # Register user in database
    db.add_user(user_id, user.username, user.first_name, user.last_name)
    
    # Get user's language
    lang = get_user_language(user_id)
    
    keyboard = [
        [
            InlineKeyboardButton(
                get_text('language_ar', lang), 
                callback_data='lang_ar'
            ),
            InlineKeyboardButton(
                get_text('language_en', lang), 
                callback_data='lang_en'
            )
        ],
        [
            InlineKeyboardButton(
                get_text('subscribe_btn', lang),
                callback_data='subscribe'
            )
        ],
        [
            InlineKeyboardButton(
                get_text('my_subscription', lang),
                callback_data='my_subscription'
            )
        ],
        [
            InlineKeyboardButton(
                get_text('open_webapp', lang),
                web_app=WebAppInfo(url=WEBAPP_URL)
            )
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        get_text('welcome', lang).format(name=user.first_name),
        reply_markup=reply_markup
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    lang = get_user_language(user_id)
    
    if query.data.startswith('lang_'):
        # Language selection
        new_lang = query.data.split('_')[1]
        set_user_language(user_id, new_lang)
        lang = new_lang
        
        await query.edit_message_text(
            get_text('language_changed', lang)
        )
        
        # Show main menu again
        keyboard = [
            [
                InlineKeyboardButton(
                    get_text('subscribe_btn', lang),
                    callback_data='subscribe'
                )
            ],
            [
                InlineKeyboardButton(
                    get_text('my_subscription', lang),
                    callback_data='my_subscription'
                )
            ],
            [
                InlineKeyboardButton(
                    get_text('open_webapp', lang),
                    web_app=WebAppInfo(url=WEBAPP_URL)
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            get_text('main_menu', lang),
            reply_markup=reply_markup
        )
    
    elif query.data == 'subscribe':
        # Show subscription plans
        keyboard = [
            [
                InlineKeyboardButton(
                    get_text('plan_monthly', lang),
                    callback_data='plan_monthly'
                )
            ],
            [
                InlineKeyboardButton(
                    get_text('plan_yearly', lang),
                    callback_data='plan_yearly'
                )
            ],
            [
                InlineKeyboardButton(
                    get_text('plan_lifetime', lang),
                    callback_data='plan_lifetime'
                )
            ],
            [
                InlineKeyboardButton(
                    get_text('back_btn', lang),
                    callback_data='back_to_menu'
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            get_text('choose_plan', lang),
            reply_markup=reply_markup
        )
    
    elif query.data.startswith('plan_'):
        # Show payment options
        plan_type = query.data.split('_')[1]
        
        # Get plan details
        plans = {
            'monthly': {'price': 10, 'days': 30},
            'yearly': {'price': 100, 'days': 365},
            'lifetime': {'price': 500, 'days': 36500}
        }
        
        plan = plans.get(plan_type)
        
        keyboard = [
            [
                InlineKeyboardButton(
                    get_text('pay_crypto', lang),
                    callback_data=f'pay_crypto_{plan_type}'
                )
            ],
            [
                InlineKeyboardButton(
                    get_text('pay_webapp', lang),
                    web_app=WebAppInfo(url=f"{WEBAPP_URL}?plan={plan_type}")
                )
            ],
            [
                InlineKeyboardButton(
                    get_text('back_btn', lang),
                    callback_data='subscribe'
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            get_text('plan_details', lang).format(
                plan=get_text(f'plan_{plan_type}', lang),
                price=plan['price'],
                days=plan['days']
            ),
            reply_markup=reply_markup
        )
    
    elif query.data.startswith('pay_crypto_'):
        # Show crypto payment instructions
        plan_type = query.data.split('_')[2]
        plans = {
            'monthly': {'price': 10, 'days': 30},
            'yearly': {'price': 100, 'days': 365},
            'lifetime': {'price': 500, 'days': 36500}
        }
        
        plan = plans.get(plan_type)
        
        keyboard = [
            [
                InlineKeyboardButton(
                    get_text('confirm_payment', lang),
                    callback_data=f'confirm_{plan_type}'
                )
            ],
            [
                InlineKeyboardButton(
                    get_text('back_btn', lang),
                    callback_data=f'plan_{plan_type}'
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            get_text('crypto_payment_info', lang).format(
                wallet=CRYPTO_WALLET_ADDRESS,
                amount=plan['price']
            ),
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    elif query.data.startswith('confirm_'):
        # Confirm payment (in production, verify on blockchain)
        plan_type = query.data.split('_')[1]
        plans = {
            'monthly': {'price': 10, 'days': 30},
            'yearly': {'price': 100, 'days': 365},
            'lifetime': {'price': 500, 'days': 36500}
        }
        
        plan = plans.get(plan_type)
        
        # Add pending payment to database
        db.add_pending_payment(user_id, plan_type, plan['price'])
        
        keyboard = [
            [
                InlineKeyboardButton(
                    get_text('back_to_menu', lang),
                    callback_data='back_to_menu'
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            get_text('payment_pending', lang),
            reply_markup=reply_markup
        )
        
        # Notify admins
        for admin_id in ADMIN_IDS:
            try:
                admin_keyboard = [
                    [
                        InlineKeyboardButton(
                            "✅ Approve",
                            callback_data=f'approve_{user_id}_{plan_type}'
                        ),
                        InlineKeyboardButton(
                            "❌ Reject",
                            callback_data=f'reject_{user_id}'
                        )
                    ]
                ]
                admin_markup = InlineKeyboardMarkup(admin_keyboard)
                
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"New payment request:\nUser: {query.from_user.username or user_id}\nPlan: {plan_type}\nAmount: ${plan['price']}",
                    reply_markup=admin_markup
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")
    
    elif query.data.startswith('approve_'):
        # Admin approves payment
        if user_id not in ADMIN_IDS:
            await query.answer("Unauthorized", show_alert=True)
            return
        
        parts = query.data.split('_')
        target_user_id = int(parts[1])
        plan_type = parts[2]
        
        plans = {
            'monthly': {'price': 10, 'days': 30},
            'yearly': {'price': 100, 'days': 365},
            'lifetime': {'price': 500, 'days': 36500}
        }
        
        plan = plans.get(plan_type)
        
        # Activate subscription
        expiry_date = datetime.now() + timedelta(days=plan['days'])
        db.activate_subscription(target_user_id, plan_type, expiry_date)
        
        await query.edit_message_text(
            f"✅ Payment approved for user {target_user_id}"
        )
        
        # Notify user
        try:
            target_lang = get_user_language(target_user_id)
            await context.bot.send_message(
                chat_id=target_user_id,
                text=get_text('subscription_activated', target_lang).format(
                    plan=get_text(f'plan_{plan_type}', target_lang),
                    expiry=expiry_date.strftime('%Y-%m-%d')
                )
            )
        except Exception as e:
            logger.error(f"Failed to notify user {target_user_id}: {e}")
    
    elif query.data.startswith('reject_'):
        # Admin rejects payment
        if user_id not in ADMIN_IDS:
            await query.answer("Unauthorized", show_alert=True)
            return
        
        target_user_id = int(query.data.split('_')[1])
        
        db.remove_pending_payment(target_user_id)
        
        await query.edit_message_text(
            f"❌ Payment rejected for user {target_user_id}"
        )
        
        # Notify user
        try:
            target_lang = get_user_language(target_user_id)
            await context.bot.send_message(
                chat_id=target_user_id,
                text=get_text('payment_rejected', target_lang)
            )
        except Exception as e:
            logger.error(f"Failed to notify user {target_user_id}: {e}")
    
    elif query.data == 'my_subscription':
        # Show user's subscription status
        subscription = db.get_subscription(user_id)
        
        if subscription and subscription['is_active']:
            keyboard = [
                [
                    InlineKeyboardButton(
                        get_text('back_to_menu', lang),
                        callback_data='back_to_menu'
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                get_text('subscription_info', lang).format(
                    plan=subscription['plan_type'],
                    expiry=subscription['expiry_date']
                ),
                reply_markup=reply_markup
            )
        else:
            keyboard = [
                [
                    InlineKeyboardButton(
                        get_text('subscribe_btn', lang),
                        callback_data='subscribe'
                    )
                ],
                [
                    InlineKeyboardButton(
                        get_text('back_to_menu', lang),
                        callback_data='back_to_menu'
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                get_text('no_subscription', lang),
                reply_markup=reply_markup
            )
    
    elif query.data == 'back_to_menu':
        # Back to main menu
        keyboard = [
            [
                InlineKeyboardButton(
                    get_text('language_ar', lang), 
                    callback_data='lang_ar'
                ),
                InlineKeyboardButton(
                    get_text('language_en', lang), 
                    callback_data='lang_en'
                )
            ],
            [
                InlineKeyboardButton(
                    get_text('subscribe_btn', lang),
                    callback_data='subscribe'
                )
            ],
            [
                InlineKeyboardButton(
                    get_text('my_subscription', lang),
                    callback_data='my_subscription'
                )
            ],
            [
                InlineKeyboardButton(
                    get_text('open_webapp', lang),
                    web_app=WebAppInfo(url=WEBAPP_URL)
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            get_text('main_menu', lang),
            reply_markup=reply_markup
        )


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("Unauthorized")
        return
    
    stats = db.get_statistics()
    
    text = f"""📊 Bot Statistics:
    
Total Users: {stats['total_users']}
Active Subscriptions: {stats['active_subscriptions']}
Pending Payments: {stats['pending_payments']}
Total Revenue: ${stats['total_revenue']}
"""
    
    await update.message.reply_text(text)


async def webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle data from Web App"""
    if update.message.web_app_data:
        data = update.message.web_app_data.data
        user_id = update.effective_user.id
        lang = get_user_language(user_id)
        
        await update.message.reply_text(
            get_text('webapp_data_received', lang)
        )


def main():
    """Start the bot"""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_data))
    
    # Start bot
    logger.info("Bot started...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
    
