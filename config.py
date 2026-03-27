import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
PORT = int(os.getenv("PORT", 5000))

# hh.ru API
HH_API_URL = "https://api.hh.ru/vacancies"
HH_APP_NAME = "JobTrackerBot/1.0"

# Avito scraping — user-agent rotation
AVITO_BASE_URL = "https://www.avito.ru"
AVITO_SEARCH_URL = "https://www.avito.ru/rossiya/vakansii"

CHECK_INTERVAL_MINUTES = 30

# Region IDs for hh.ru (most common)
HH_REGIONS = {
    "москва": 1,
    "санкт-петербург": 2,
    "питер": 2,
    "спб": 2,
    "новосибирск": 4,
    "екатеринбург": 3,
    "казань": 88,
    "нижний новгород": 66,
    "челябинск": 104,
    "самара": 78,
    "омск": 68,
    "ростов-на-дону": 76,
    "уфа": 99,
    "красноярск": 54,
    "воронеж": 26,
    "пермь": 72,
    "волгоград": 24,
    "краснодар": 53,
}
