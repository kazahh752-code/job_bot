import logging
import httpx
from config import HH_API_URL, HH_APP_NAME, HH_REGIONS

logger = logging.getLogger(__name__)


def get_hh_region_id(region_name: str) -> int | None:
    if not region_name:
        return None
    return HH_REGIONS.get(region_name.lower().strip())


async def fetch_hh_vacancies(query: str, region: str = None, salary_from: int = None) -> list[dict]:
    params = {
        "text": query,
        "per_page": 20,
        "order_by": "publication_time",
        "search_field": "name",
    }

    region_id = get_hh_region_id(region) if region else None
    if region_id:
        params["area"] = region_id
    elif region:
        # Try text search in region field
        params["area"] = 113  # Russia default

    if salary_from:
        params["salary"] = salary_from
        params["only_with_salary"] = "true"

    headers = {"User-Agent": HH_APP_NAME}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(HH_API_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.error(f"hh.ru fetch error: {e}")
        return []

    jobs = []
    for item in data.get("items", []):
        salary = item.get("salary")
        salary_str = ""
        if salary:
            lo = salary.get("from")
            hi = salary.get("to")
            cur = salary.get("currency", "RUR")
            cur = "₽" if cur == "RUR" else cur
            if lo and hi:
                salary_str = f"{lo:,}–{hi:,} {cur}".replace(",", " ")
            elif lo:
                salary_str = f"от {lo:,} {cur}".replace(",", " ")
            elif hi:
                salary_str = f"до {hi:,} {cur}".replace(",", " ")

        jobs.append({
            "id": f"hh_{item['id']}",
            "title": item.get("name", ""),
            "company": item.get("employer", {}).get("name", ""),
            "salary": salary_str or "не указана",
            "region": item.get("area", {}).get("name", ""),
            "url": item.get("alternate_url", ""),
            "source": "hh.ru",
            "published": item.get("published_at", "")[:10],
        })

    return jobs
