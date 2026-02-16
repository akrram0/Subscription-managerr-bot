require('dotenv').config();
const { Bot, session, Keyboard, InlineKeyboard } = require('grammy');
const { I18n } = require('@grammyjs/i18n');
const express = require('express');
const cors = require('cors');

// 1. إعداد البوت
const bot = new Bot(process.env.BOT_TOKEN);

// 2. إعداد اللغات (i18n)
const i18n = new I18n({
    defaultLocale: 'en',
    directory: 'locales',
    useSession: true, // تخزين لغة المستخدم في الجلسة
});

bot.use(session({ initial: () => ({ language: 'en', subscription: false }) }));
bot.use(i18n);

// 3. أمر البداية واختيار اللغة
bot.command('start', async (ctx) => {
    const keyboard = new InlineKeyboard()
        .text('English 🇺🇸', 'lang_en')
        .text('العربية 🇸🇦', 'lang_ar');
    
    await ctx.reply(ctx.t('welcome'), { reply_markup: keyboard });
});

// معالجة تغيير اللغة
bot.callbackQuery('lang_en', async (ctx) => {
    await ctx.i18n.setLocale('en');
    ctx.session.language = 'en';
    await showMainMenu(ctx);
});

bot.callbackQuery('lang_ar', async (ctx) => {
    await ctx.i18n.setLocale('ar');
    ctx.session.language = 'ar';
    await showMainMenu(ctx);
});

// القائمة الرئيسية مع زر التطبيق المصغر (Web App)
async function showMainMenu(ctx) {
    const webAppUrl = process.env.WEB_APP_URL; // رابط استضافة تطبيقك (Vercel/Netlify)
    
    const keyboard = new Keyboard()
        .webApp(ctx.t('open_app'), webAppUrl) // زر يفتح الـ Mini App
        .resized();

    await ctx.reply(ctx.t('language_set'), { reply_markup: keyboard });
}

// 4. API بسيط لاستقبال تأكيد الدفع من الويب
const app = express();
app.use(express.json());
app.use(cors());

app.post('/verify-payment', async (req, res) => {
    const { userId, txHash } = req.body;
    // هنا يجب التحقق من المعاملة عبر البلوكشين (Web3)
    console.log(`Payment received from ${userId}, Hash: ${txHash}`);
    
    // إرسال رسالة للمستخدم
    try {
        await bot.api.sendMessage(userId, "✅ Payment received! Subscription Activated.");
    } catch (e) {
        console.error(e);
    }
    
    res.json({ success: true });
});

// تشغيل السيرفر والبوت
app.listen(3000, () => console.log('API Server running on port 3000'));
bot.start();
