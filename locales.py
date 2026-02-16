"""
Localization Module — Bilingual Support (Arabic & English)
==========================================================
All user-facing text strings organized by language code.
Usage: TEXTS[lang_code][key]
"""

TEXTS = {
    "en": {
        # Language selection
        "choose_language": "🌐 <b>Choose your language:</b>",
        "language_set": "✅ Language set to <b>English</b>.",

        # Welcome & Help
        "welcome": (
            "👋 <b>Welcome to Subscription Manager Bot!</b>\n\n"
            "I'm your personal assistant for managing all your digital subscriptions.\n"
            "Here's what I can do:\n\n"
            "📌 <b>Add Subscriptions</b> — Track every service you subscribe to\n"
            "📋 <b>View Subscriptions</b> — Organized list of all your subscriptions\n"
            "💰 <b>Calculate Costs</b> — Know your total monthly & yearly expenses\n"
            "🔔 <b>Auto Reminders</b> — Notifications 7, 3, and 1 days before payment\n"
            "🗑 <b>Delete Subscriptions</b> — Remove services you no longer need\n\n"
            "Use the buttons below to get started 👇"
        ),
        "help": (
            "📖 <b>Usage Guide:</b>\n\n"
            "🔹 /start — Show welcome message\n"
            "🔹 /add — Add a new subscription\n"
            "🔹 /list — View all subscriptions\n"
            "🔹 /total — Calculate total costs\n"
            "🔹 /delete — Delete a subscription\n"
            "🔹 /language — Change language\n"
            "🔹 /help — Show this guide\n"
            "🔹 /cancel — Cancel current operation"
        ),

        # Reply Keyboard Buttons
        "btn_add": "➕ Add Subscription",
        "btn_list": "📋 My Subscriptions",
        "btn_total": "💰 Calculate Total",
        "btn_settings": "⚙️ Settings / Language",

        # Inline Keyboard Buttons
        "btn_add_inline": "➕ Add Subscription",
        "btn_list_inline": "📋 View Subscriptions",
        "btn_total_inline": "💰 Calculate Costs",
        "btn_delete_inline": "🗑 Delete Subscription",
        "btn_help_inline": "📖 Help",
        "btn_back": "🔙 Back",
        "btn_cancel": "❌ Cancel",

        # Add Subscription Flow
        "add_title": "📝 <b>Add New Subscription</b>",
        "add_step1": "Step 1/5: Send the <b>service name</b>\nExample: Netflix, Spotify, YouTube Premium",
        "add_step2_ok": "✅ Service: <b>{}</b>\n\nStep 2/5: Send the <b>subscription cost</b> (number only)\nExample: 9.99",
        "add_step3_ok": "✅ Cost: <b>{}</b>\n\nStep 3/5: Choose the <b>currency</b> below 👇",
        "add_step4_ok": "✅ Currency: <b>{}</b>\n\nStep 4/5: Choose the <b>billing cycle</b> 👇",
        "add_step5_ok": "✅ Billing Cycle: <b>{}</b>\n\nStep 5/5: Send the <b>next payment date</b>\nFormat: <code>YYYY-MM-DD</code>\nExample: <code>{}</code>",
        "add_success": (
            "🎉 <b>Subscription added successfully!</b>\n\n"
            "┌─────────────────────\n"
            "│ 📌 Service: <b>{service}</b>\n"
            "│ 💵 Cost: <b>{cost} {currency}</b>\n"
            "│ 🔄 Cycle: {cycle}\n"
            "│ 📅 Payment Date: <code>{date}</code>\n"
            "│ 🆔 ID: #{id}\n"
            "└─────────────────────\n\n"
            "🔔 You will be reminded automatically before the payment date."
        ),
        "add_error_name": "⚠️ Please enter a valid service name (under 100 characters).",
        "add_error_cost": "⚠️ Please enter a valid amount (positive number).\nExample: 9.99",
        "add_error_date_format": "⚠️ Invalid date format.\nPlease use: <code>YYYY-MM-DD</code>\nExample: <code>2026-03-15</code>",
        "add_error_date_past": "⚠️ Cannot enter a past date. Please enter a future date.",
        "add_error_save": "❌ Error saving subscription. Please try again.",

        # Billing cycles
        "cycle_monthly": "📅 Monthly",
        "cycle_yearly": "📆 Yearly",
        "monthly": "Monthly",
        "yearly": "Yearly",

        # List
        "list_title": "📋 <b>Your Subscriptions ({count})</b>\n",
        "list_empty": "📋 <b>Your Subscriptions</b>\n\nNo subscriptions registered yet.\nUse ➕ <b>Add Subscription</b> to add one.",
        "card_cost": "💵 Cost",
        "card_cycle": "🔄 Cycle",
        "card_date": "📅 Payment Date",
        "card_remaining": "⏳ Remaining",
        "days_overdue": "⚠️ <b>Overdue!</b>",
        "days_today": "🔴 <b>Today!</b>",
        "days_tomorrow": "🟠 <b>Tomorrow</b>",
        "days_soon": "🟡 <b>In {} days</b>",
        "days_week": "🟢 In {} days",
        "days_later": "⚪ In {} days",

        # Total
        "total_title": "💰 <b>Total Costs</b>\n",
        "total_empty": "💰 <b>Total Costs</b>\n\nNo subscriptions registered to calculate costs.",
        "total_count": "📊 Active subscriptions: <b>{}</b>\n",
        "total_monthly": "📅 Monthly",
        "total_yearly": "📆 Yearly",
        "total_nearest": "⏰ <b>Nearest payment:</b>\n   {} — {} (in {} days)",

        # Delete
        "delete_title": "🗑 <b>Delete Subscription</b>\n\nSelect the subscription to delete:",
        "delete_empty": "🗑 <b>Delete Subscription</b>\n\nNo subscriptions to delete.",
        "delete_confirm": "⚠️ <b>Confirm Deletion</b>\n\nAre you sure you want to delete <b>{}</b>?\nCost: {} {}",
        "delete_yes": "✅ Yes, delete",
        "delete_no": "❌ No, go back",
        "delete_success": "✅ <b>Subscription deleted successfully!</b>",
        "delete_error": "❌ Error deleting subscription.",
        "delete_not_found": "⚠️ Subscription not found.",

        # Cancel
        "cancel_none": "❌ No active operation to cancel.",
        "cancel_ok": "✅ Operation cancelled.\nUse the menu to start again.",

        # Settings
        "settings_title": "⚙️ <b>Settings</b>\n\nCurrent language: <b>English</b>\n\nChoose a new language:",
        "settings_btn_en": "🇬🇧 English ✓",
        "settings_btn_ar": "🇸🇦 العربية",

        # Reminders
        "reminder_title": "🔔 <b>Payment Reminder — {urgency}</b>",
        "reminder_body": (
            "┌─────────────────────\n"
            "│ 📌 Service: <b>{service}</b>\n"
            "│ 💵 Amount: <b>{cost} {currency}</b>\n"
            "│ 📅 Payment Date: <code>{date}</code>\n"
            "│ ⏳ Remaining: {time_text}\n"
            "└─────────────────────\n\n"
            "Reminder: Subscription <b>{service}</b> worth "
            "<b>{cost} {currency}</b> is due {time_text}."
        ),
        "reminder_1day": "Tomorrow 🔴",
        "reminder_3days": "In 3 days 🟠",
        "reminder_7days": "In 7 days 🟡",
        "urgency_1": "Urgent",
        "urgency_3": "Soon",
        "urgency_7": "Early Notice",

        # Bot commands descriptions
        "cmd_start": "Start the bot",
        "cmd_add": "Add a new subscription",
        "cmd_list": "View all subscriptions",
        "cmd_total": "Calculate total costs",
        "cmd_delete": "Delete a subscription",
        "cmd_language": "Change language",
        "cmd_help": "Usage guide",
        "cmd_cancel": "Cancel current operation",
    },

    "ar": {
        # Language selection
        "choose_language": "🌐 <b>اختر اللغة:</b>",
        "language_set": "✅ تم تعيين اللغة إلى <b>العربية</b>.",

        # Welcome & Help
        "welcome": (
            "👋 <b>مرحباً بك في بوت إدارة الاشتراكات!</b>\n\n"
            "أنا مساعدك الشخصي لإدارة جميع اشتراكاتك الرقمية.\n"
            "سأساعدك في:\n\n"
            "📌 <b>إضافة اشتراكات جديدة</b> — تتبع كل خدمة تشترك فيها\n"
            "📋 <b>عرض اشتراكاتك</b> — قائمة منظمة بكل اشتراكاتك\n"
            "💰 <b>حساب التكاليف</b> — معرفة إجمالي مصاريفك الشهرية والسنوية\n"
            "🔔 <b>تذكيرات تلقائية</b> — إشعارات قبل موعد الدفع بـ 7 و 3 و 1 أيام\n"
            "🗑 <b>حذف الاشتراكات</b> — إزالة الاشتراكات التي لم تعد بحاجة إليها\n\n"
            "استخدم الأزرار أدناه للبدء 👇"
        ),
        "help": (
            "📖 <b>دليل الاستخدام:</b>\n\n"
            "🔹 /start — عرض الرسالة الترحيبية\n"
            "🔹 /add — إضافة اشتراك جديد\n"
            "🔹 /list — عرض جميع الاشتراكات\n"
            "🔹 /total — حساب إجمالي التكاليف\n"
            "🔹 /delete — حذف اشتراك\n"
            "🔹 /language — تغيير اللغة\n"
            "🔹 /help — عرض هذا الدليل\n"
            "🔹 /cancel — إلغاء العملية الحالية"
        ),

        # Reply Keyboard Buttons
        "btn_add": "➕ إضافة اشتراك",
        "btn_list": "📋 اشتراكاتي",
        "btn_total": "💰 حساب التكاليف",
        "btn_settings": "⚙️ الإعدادات / اللغة",

        # Inline Keyboard Buttons
        "btn_add_inline": "➕ إضافة اشتراك",
        "btn_list_inline": "📋 عرض الاشتراكات",
        "btn_total_inline": "💰 حساب التكاليف",
        "btn_delete_inline": "🗑 حذف اشتراك",
        "btn_help_inline": "📖 المساعدة",
        "btn_back": "🔙 رجوع",
        "btn_cancel": "❌ إلغاء",

        # Add Subscription Flow
        "add_title": "📝 <b>إضافة اشتراك جديد</b>",
        "add_step1": "الخطوة 1/5: أرسل <b>اسم الخدمة</b>\nمثال: Netflix, Spotify, YouTube Premium",
        "add_step2_ok": "✅ اسم الخدمة: <b>{}</b>\n\nالخطوة 2/5: أرسل <b>تكلفة الاشتراك</b> (رقم فقط)\nمثال: 9.99",
        "add_step3_ok": "✅ التكلفة: <b>{}</b>\n\nالخطوة 3/5: اختر <b>العملة</b> من الأزرار أدناه 👇",
        "add_step4_ok": "✅ العملة: <b>{}</b>\n\nالخطوة 4/5: اختر <b>دورة الفوترة</b> 👇",
        "add_step5_ok": "✅ دورة الفوترة: <b>{}</b>\n\nالخطوة 5/5: أرسل <b>تاريخ الدفع القادم</b>\nبالصيغة: <code>YYYY-MM-DD</code>\nمثال: <code>{}</code>",
        "add_success": (
            "🎉 <b>تم إضافة الاشتراك بنجاح!</b>\n\n"
            "┌─────────────────────\n"
            "│ 📌 الخدمة: <b>{service}</b>\n"
            "│ 💵 التكلفة: <b>{cost} {currency}</b>\n"
            "│ 🔄 الدورة: {cycle}\n"
            "│ 📅 موعد الدفع: <code>{date}</code>\n"
            "│ 🆔 رقم الاشتراك: #{id}\n"
            "└─────────────────────\n\n"
            "🔔 سيتم تذكيرك قبل موعد الدفع تلقائياً."
        ),
        "add_error_name": "⚠️ يرجى إدخال اسم خدمة صحيح (أقل من 100 حرف).",
        "add_error_cost": "⚠️ يرجى إدخال مبلغ صحيح (رقم موجب).\nمثال: 9.99",
        "add_error_date_format": "⚠️ صيغة التاريخ غير صحيحة.\nيرجى الإدخال بالصيغة: <code>YYYY-MM-DD</code>\nمثال: <code>2026-03-15</code>",
        "add_error_date_past": "⚠️ لا يمكن إدخال تاريخ في الماضي. يرجى إدخال تاريخ مستقبلي.",
        "add_error_save": "❌ حدث خطأ أثناء حفظ الاشتراك. يرجى المحاولة مرة أخرى.",

        # Billing cycles
        "cycle_monthly": "📅 شهري",
        "cycle_yearly": "📆 سنوي",
        "monthly": "شهري",
        "yearly": "سنوي",

        # List
        "list_title": "📋 <b>اشتراكاتك ({count})</b>\n",
        "list_empty": "📋 <b>اشتراكاتك</b>\n\nلا توجد اشتراكات مسجلة حالياً.\nاستخدم ➕ <b>إضافة اشتراك</b> لإضافة اشتراك جديد.",
        "card_cost": "💵 التكلفة",
        "card_cycle": "🔄 الدورة",
        "card_date": "📅 موعد الدفع",
        "card_remaining": "⏳ المتبقي",
        "days_overdue": "⚠️ <b>متأخر!</b>",
        "days_today": "🔴 <b>اليوم!</b>",
        "days_tomorrow": "🟠 <b>غداً</b>",
        "days_soon": "🟡 <b>بعد {} أيام</b>",
        "days_week": "🟢 بعد {} أيام",
        "days_later": "⚪ بعد {} يوم",

        # Total
        "total_title": "💰 <b>إجمالي التكاليف</b>\n",
        "total_empty": "💰 <b>إجمالي التكاليف</b>\n\nلا توجد اشتراكات مسجلة لحساب التكاليف.",
        "total_count": "📊 عدد الاشتراكات النشطة: <b>{}</b>\n",
        "total_monthly": "📅 شهرياً",
        "total_yearly": "📆 سنوياً",
        "total_nearest": "⏰ <b>أقرب موعد دفع:</b>\n   {} — {} (بعد {} يوم)",

        # Delete
        "delete_title": "🗑 <b>حذف اشتراك</b>\n\nاختر الاشتراك الذي تريد حذفه:",
        "delete_empty": "🗑 <b>حذف اشتراك</b>\n\nلا توجد اشتراكات لحذفها.",
        "delete_confirm": "⚠️ <b>تأكيد الحذف</b>\n\nهل أنت متأكد من حذف اشتراك <b>{}</b>؟\nالتكلفة: {} {}",
        "delete_yes": "✅ نعم، احذف",
        "delete_no": "❌ لا، تراجع",
        "delete_success": "✅ <b>تم حذف الاشتراك بنجاح!</b>",
        "delete_error": "❌ حدث خطأ أثناء حذف الاشتراك.",
        "delete_not_found": "⚠️ الاشتراك غير موجود.",

        # Cancel
        "cancel_none": "❌ لا توجد عملية جارية لإلغائها.",
        "cancel_ok": "✅ تم إلغاء العملية.\nاستخدم القائمة للبدء من جديد.",

        # Settings
        "settings_title": "⚙️ <b>الإعدادات</b>\n\nاللغة الحالية: <b>العربية</b>\n\nاختر لغة جديدة:",
        "settings_btn_en": "🇬🇧 English",
        "settings_btn_ar": "🇸🇦 العربية ✓",

        # Reminders
        "reminder_title": "🔔 <b>تذكير بموعد الدفع — {urgency}</b>",
        "reminder_body": (
            "┌─────────────────────\n"
            "│ 📌 الخدمة: <b>{service}</b>\n"
            "│ 💵 المبلغ: <b>{cost} {currency}</b>\n"
            "│ 📅 موعد الدفع: <code>{date}</code>\n"
            "│ ⏳ المتبقي: {time_text}\n"
            "└─────────────────────\n\n"
            "تذكير: اشتراك <b>{service}</b> بقيمة "
            "<b>{cost} {currency}</b> يستحق الدفع {time_text}."
        ),
        "reminder_1day": "غداً 🔴",
        "reminder_3days": "بعد 3 أيام 🟠",
        "reminder_7days": "بعد 7 أيام 🟡",
        "urgency_1": "عاجل",
        "urgency_3": "قريباً",
        "urgency_7": "تنبيه مبكر",

        # Bot commands descriptions
        "cmd_start": "بدء البوت",
        "cmd_add": "إضافة اشتراك جديد",
        "cmd_list": "عرض جميع الاشتراكات",
        "cmd_total": "حساب إجمالي التكاليف",
        "cmd_delete": "حذف اشتراك",
        "cmd_language": "تغيير اللغة",
        "cmd_help": "دليل الاستخدام",
        "cmd_cancel": "إلغاء العملية الحالية",
    }
}


def t(lang: str, key: str) -> str:
    """Get a translated text string. Falls back to English if key not found."""
    lang = lang or "en"
    if lang in TEXTS and key in TEXTS[lang]:
        return TEXTS[lang][key]
    return TEXTS.get("en", {}).get(key, f"[{key}]")
