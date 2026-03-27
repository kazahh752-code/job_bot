import logging
import re
import httpx
from bs4 import BeautifulSoup
from config import AVITO_BASE_URL

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Map common city names to Avito URL slugs
AVITO_REGIONS = {
    "москва": "moskva",
    "санкт-петербург": "sankt-peterburg",
    "питер": "sankt-peterburg",
    "спб": "sankt-peterburg",
    "новосибирск": "novosibirsk",
    "екатеринбург": "ekaterinburg",
    "казань": "kazan",
    "нижний новгород": "nizhniy_novgorod",
    "челябинск": "chelyabinsk",
    "самара": "samara",
    "омск": "omsk",
    "ростов-на-дону": "rostov-na-donu",
    "уфа": "ufa",
    "красноярск": "krasnoyarsk",
    "воронеж": "voronezh",
    "пермь": "perm",
    "волгоград": "volgograd",
    "краснодар": "krasnodar",
}


def get_avito_region_slug(region: str) -> str:
    if not region:
        return "rossiya"
    return AVITO_REGIONS.get(region.lower().strip(), "rossiya")


async def fetch_avito_vacancies(query: str, region: str = None, salary_from: int = None) -> list[dict]:
    region_slug = get_avito_region_slug(region)
    url = f"{AVITO_BASE_URL}/{region_slug}/vakansii"

    params = {"q": query}
    if salary_from:
        params["s[salary][from]"] = salary_from

    try:
        async with httpx.AsyncClient(
            timeout=20,
            headers=HEADERS,
            follow_redirects=True
        ) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        logger.error(f"Avito fetch error: {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    # Avito frequently changes class names — we use data-marker attributes
    items = soup.select("[data-marker='item']")
    if not items:
        # Fallback selectors
        items = soup.select("div[class*='iva-item-root']")

    for item in items[:20]:
        try:
            # Title
            title_el = (
                item.select_one("[data-marker='item-title']") or
                item.select_one("h3") or
                item.select_one("a[class*='title']")
            )
            title = title_el.get_text(strip=True) if title_el else "Без названия"

            # URL
            link_el = item.select_one("a[href]")
            href = link_el["href"] if link_el else ""
            job_url = f"{AVITO_BASE_URL}{href}" if href.startswith("/") else href

            # ID from URL
            job_id = re.search(r"_(\d+)$", href)
            job_id = f"avito_{job_id.group(1)}" if job_id else f"avito_{hash(href)}"

            # Company
            company_el = (
                item.select_one("[data-marker='item-company-name']") or
                item.select_one("[class*='company']") or
                item.select_one("[class*='seller']")
            )
            company = company_el.get_text(strip=True) if company_el else "—"

            # Salary
            price_el = (
                item.select_one("[data-marker='item-price']") or
                item.select_one("[class*='price']")
            )
            salary = price_el.get_text(strip=True) if price_el else "не указана"

            # Location
            geo_el = item.select_one("[class*='geo']") or item.select_one("[class*='location']")
            location = geo_el.get_text(strip=True) if geo_el else (region or "Россия")

            jobs.append({
                "id": job_id,
                "title": title,
                "company": company,
                "salary": salary,
                "region": location,
                "url": job_url,
                "source": "Авито",
                "published": "",
            })
        except Exception as e:
            logger.debug(f"Avito item parse error: {e}")
            continue

    return jobs
