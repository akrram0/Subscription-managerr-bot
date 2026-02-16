"""
Localization module - Arabic and English support
"""

from typing import Dict
from database import Database

# Language dictionary
TRANSLATIONS = {
    'en': {
        'welcome': "👋 Welcome {name}!\n\nI'm your subscription manager bot. Choose an option below:",
        'main_menu': "📋 Main Menu\n\nSelect an option:",
        'language_ar': "🇸🇦 العربية",
        'language_en': "🇬🇧 English",
        'language_changed': "✅ Language changed successfully!",
        'subscribe_btn': "💎 Subscribe",
        'my_subscription': "📊 My Subscription",
        'open_webapp': "🌐 Open Web App",
        'choose_plan': "💰 Choose Your Plan:\n\nSelect one of the available subscription plans:",
        'plan_monthly': "📅 Monthly Plan - $10/month",
        'plan_yearly': "📆 Yearly Plan - $100/year (Save 17%)",
        'plan_lifetime': "♾️ Lifetime Plan - $500 (One-time)",
        'plan_details': "📋 Plan Details:\n\n{plan}\nPrice: ${price}\nDuration: {days} days\n\nChoose payment method:",
        'pay_crypto': "💰 Pay with Crypto",
        'pay_webapp': "💳 Pay via Web App",
        'back_btn': "🔙 Back",
        'back_to_menu': "🏠 Main Menu",
        'crypto_payment_info': "💰 Crypto Payment Instructions:\n\n1. Send exactly `${amount} USDT` (TRC20) to:\n\n`{wallet}`\n\n2. After payment, click 'Confirm Payment'\n\n3. Admin will verify and activate your subscription\n\n⚠️ Make sure to send the exact amount!",
        'confirm_payment': "✅ Confirm Payment",
        'payment_pending': "⏳ Payment Pending\n\nYour payment is being verified by our admin team.\nYou'll be notified once your subscription is activated.\n\nThank you for your patience! 🙏",
        'payment_rejected': "❌ Payment Rejected\n\nYour payment couldn't be verified.\nPlease contact support or try again.",
        'subscription_activated': "🎉 Subscription Activated!\n\nPlan: {plan}\nExpiry Date: {expiry}\n\nEnjoy your premium access! 🚀",
        'subscription_info': "📊 Your Subscription:\n\nPlan: {plan}\nExpiry Date: {expiry}\n\nStatus: ✅ Active",
        'no_subscription': "❌ No Active Subscription\n\nYou don't have an active subscription yet.\nSubscribe now to access premium features!",
        'webapp_data_received': "✅ Data received from Web App!",
    },
    'ar': {
        'welcome': "👋 أهلاً {name}!\n\nأنا بوت إدارة الاشتراكات الخاص بك. اختر خياراً من الأسفل:",
        'main_menu': "📋 القائمة الرئيسية\n\nاختر خياراً:",
        'language_ar': "🇸🇦 العربية",
        'language_en': "🇬🇧 English",
        'language_changed': "✅ تم تغيير اللغة بنجاح!",
        'subscribe_btn': "💎 الاشتراك",
        'my_subscription': "📊 اشتراكي",
        'open_webapp': "🌐 فتح التطبيق",
        'choose_plan': "💰 اختر خطة الاشتراك:\n\nاختر إحدى خطط الاشتراك المتاحة:",
        'plan_monthly': "📅 خطة شهرية - 10$ شهرياً",
        'plan_yearly': "📆 خطة سنوية - 100$ سنوياً (وفر 17%)",
        'plan_lifetime': "♾️ خطة مدى الحياة - 500$ (دفعة واحدة)",
        'plan_details': "📋 تفاصيل الخطة:\n\n{plan}\nالسعر: ${price}\nالمدة: {days} يوم\n\nاختر طريقة الدفع:",
        'pay_crypto': "💰 الدفع بالعملات الرقمية",
        'pay_webapp': "💳 الدفع عبر التطبيق",
        'back_btn': "🔙 رجوع",
        'back_to_menu': "🏠 القائمة الرئيسية",
        'crypto_payment_info': "💰 تعليمات الدفع بالعملات الرقمية:\n\n1. أرسل بالضبط `${amount} USDT` (TRC20) إلى:\n\n`{wallet}`\n\n2. بعد الدفع، انقر على 'تأكيد الدفع'\n\n3. سيقوم المسؤول بالتحقق وتفعيل اشتراكك\n\n⚠️ تأكد من إرسال المبلغ الصحيح!",
        'confirm_payment': "✅ تأكيد الدفع",
        'payment_pending': "⏳ الدفع قيد المراجعة\n\nيتم التحقق من دفعتك من قبل فريق الإدارة.\nسيتم إشعارك عند تفعيل اشتراكك.\n\nشكراً لصبرك! 🙏",
        'payment_rejected': "❌ تم رفض الدفع\n\nلم نتمكن من التحقق من دفعتك.\nالرجاء التواصل مع الدعم أو المحاولة مرة أخرى.",
        'subscription_activated': "🎉 تم تفعيل الاشتراك!\n\nالخطة: {plan}\nتاريخ الانتهاء: {expiry}\n\nاستمتع بالوصول المميز! 🚀",
        'subscription_info': "📊 اشتراكك:\n\nالخطة: {plan}\nتاريخ الانتهاء: {expiry}\n\nالحالة: ✅ نشط",
        'no_subscription': "❌ لا يوجد اشتراك نشط\n\nليس لديك اشتراك نشط حالياً.\nاشترك الآن للوصول إلى الميزات المميزة!",
        'webapp_data_received': "✅ تم استلام البيانات من التطبيق!",
    }
}

db = Database()


def get_text(key: str, language: str = 'en') -> str:
    """Get translated text"""
    return TRANSLATIONS.get(language, TRANSLATIONS['en']).get(key, key)


def get_user_language(user_id: int) -> str:
    """Get user's preferred language"""
    return db.get_user_language(user_id)


def set_user_language(user_id: int, language: str):
    """Set user's preferred language"""
    if language in ['ar', 'en']:
        db.set_user_language(user_id, language)
        
