import asyncio
import logging
from telegram import Bot
from telegram.error import TelegramError

from database import Database
from parser_hh import fetch_hh_vacancies
from parser_avito import fetch_avito_vacancies
from config import CHECK_INTERVAL_MINUTES

logger = logging.getLogger(__name__)


def format_job_message(job: dict) -> str:
    emoji = "🔴" if job["source"] == "hh.ru" else "🟡"
    lines = [
        f"{emoji} <b>{job['title']}</b>",
        f"🏢 {job['company']}",
        f"💰 {job['salary']}",
        f"📍 {job['region']}",
    ]
    if job.get("published"):
        lines.append(f"📅 {job['published']}")
    lines.append(f"🔗 <a href=\"{job['url']}\">Открыть вакансию</a>")
    return "\n".join(lines)


async def check_subscription(bot: Bot, db: Database, sub: dict):
    source = sub["source"]
    query = sub["query"]
    region = sub.get("region")
    salary = sub.get("salary_from")
    user_id = sub["user_id"]
    sub_id = sub["id"]

    all_jobs = []

    if source in ("hh", "both"):
        jobs = await fetch_hh_vacancies(query, region, salary)
        all_jobs.extend(jobs)

    if source in ("avito", "both"):
        jobs = await fetch_avito_vacancies(query, region, salary)
        all_jobs.extend(jobs)

    new_count = 0
    for job in all_jobs:
        if db.is_job_seen(sub_id, job["id"]):
            continue
        db.mark_job_seen(sub_id, job["id"])
        try:
            await bot.send_message(
                chat_id=user_id,
                text=format_job_message(job),
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            new_count += 1
            await asyncio.sleep(0.3)  # avoid flood
        except TelegramError as e:
            logger.error(f"Send error to {user_id}: {e}")

    if new_count:
        logger.info(f"Sub #{sub_id} ({query}): sent {new_count} new jobs to {user_id}")


async def check_all(bot: Bot, db: Database):
    subs = db.get_subscriptions()
    logger.info(f"Checking {len(subs)} subscriptions...")
    db.cleanup_old_seen(days=7)

    for sub in subs:
        try:
            await check_subscription(bot, db, sub)
        except Exception as e:
            logger.error(f"Error in sub #{sub['id']}: {e}")
        await asyncio.sleep(1)


def start_scheduler(bot: Bot, db: Database, loop: asyncio.AbstractEventLoop):
    async def _loop():
        while True:
            await check_all(bot, db)
            await asyncio.sleep(CHECK_INTERVAL_MINUTES * 60)

    def _run():
        asyncio.run_coroutine_threadsafe(_loop(), loop)

    import threading
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    logger.info(f"Scheduler started. Interval: {CHECK_INTERVAL_MINUTES} min.")
