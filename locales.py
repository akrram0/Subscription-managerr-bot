translations = {
    "en": {
        "welcome": "Welcome to Subscription Manager 🚀"
    },
    "ar": {
        "welcome": "مرحبًا بك في مدير الاشتراكات 🚀"
    }
}

def get_text(key, lang="en"):
    return translations.get(lang, translations["en"]).get(key, key)
