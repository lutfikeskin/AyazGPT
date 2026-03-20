import pytz # type: ignore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from modules.investment.collectors.market_collector import MarketCollector
from modules.investment.collectors.news_collector import NewsCollector
from modules.investment.collectors.macro_collector import MacroCollector
from modules.investment.collectors.kap_collector import KAPCollector

istanbul_tz = pytz.timezone("Europe/Istanbul")

scheduler = AsyncIOScheduler(timezone=istanbul_tz)

BIST_SYMBOLS = ["THYAO.IS", "BIMAS.IS", "KCHOL.IS", "TUPRS.IS"]
GLOBAL_SYMBOLS = ["AAPL", "SPY", "GC=F", "SI=F", "USDTRY=X", "XAUUSD=X"]

async def collect_bist_prices():
    logger.info("Starting scheduled BIST market price collection.")
    collector = MarketCollector(dry_run=False)
    for symbol in BIST_SYMBOLS:
        await collector.fetch_latest(symbol)
    logger.info("Finished BIST market price collection.")

async def collect_global_prices():
    logger.info("Starting scheduled Global market price collection.")
    collector = MarketCollector(dry_run=False)
    for symbol in GLOBAL_SYMBOLS:
        await collector.fetch_latest(symbol)
    logger.info("Finished Global market price collection.")

async def collect_news():
    logger.info("Starting scheduled News collection.")
    collector = NewsCollector(dry_run=False)
    await collector.run_collection()
    logger.info("Finished News collection.")

async def collect_macro():
    logger.info("Starting scheduled Macro collection.")
    collector = MacroCollector(dry_run=False)
    await collector.run_collection()
    logger.info("Finished Macro collection.")

async def collect_tcmb_policy_rate():
    logger.info("Starting scheduled TCMB Policy Rate collection.")
    collector = MacroCollector(dry_run=False)
    records = await collector.fetch_tcmb_policy_rate()
    await collector.save_to_db(records)
    logger.info("Finished TCMB Policy Rate collection.")

async def collect_resmi_gazete():
    logger.info("Starting scheduled Resmi Gazete collection.")
    collector = MacroCollector(dry_run=False)
    await collector.fetch_resmi_gazete()
    logger.info("Finished Resmi Gazete collection.")

async def collect_kap():
    logger.info("Starting scheduled KAP disclosure collection.")
    collector = KAPCollector()
    await collector.run_collection()
    logger.info("Finished KAP disclosure collection.")

def setup_scheduler():
    """Configure and start the background scheduler."""
    if scheduler.running:
        logger.warning("Scheduler is already running.")
        return

    # Market prices: weekdays at 18:30 Istanbul time (BIST close)
    scheduler.add_job(
        collect_bist_prices, 
        'cron', 
        day_of_week='mon-fri', 
        hour=18, 
        minute=30,
        id="collect_bist_prices",
        replace_existing=True
    )
    
    # Global prices: weekdays at 22:30 Istanbul time (NYSE close)
    scheduler.add_job(
        collect_global_prices, 
        'cron', 
        day_of_week='mon-fri', 
        hour=22, 
        minute=30,
        id="collect_global_prices",
        replace_existing=True
    )

    # News: every 2 hours
    scheduler.add_job(
        collect_news, 
        'interval', 
        hours=2,
        id="collect_news",
        replace_existing=True
    )

    # Macro: every Sunday at 09:00 Istanbul time
    scheduler.add_job(
        collect_macro, 
        'cron', 
        day_of_week='sun', 
        hour=9, 
        minute=0,
        id="collect_macro",
        replace_existing=True
    )

    # TCMB policy rate: weekly on Monday 09:00
    scheduler.add_job(
        collect_tcmb_policy_rate, 
        'cron', 
        day_of_week='mon', 
        hour=9, 
        minute=0,
        id="collect_tcmb_policy_rate",
        replace_existing=True
    )

    # Resmi Gazete: daily at 08:00
    scheduler.add_job(
        collect_resmi_gazete, 
        'cron', 
        hour=8, 
        minute=0,
        id="collect_resmi_gazete",
        replace_existing=True
    )

    # KAP Disclosures: every 30 minutes on weekdays
    scheduler.add_job(
        collect_kap,
        'cron',
        day_of_week='mon-fri',
        minute='0,30',
        id="collect_kap_weekdays",
        replace_existing=True
    )

    # KAP Disclosures: every 4 hours on weekends
    scheduler.add_job(
        collect_kap,
        'cron',
        day_of_week='sat-sun',
        hour='*/4',
        id="collect_kap_weekends",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("Investment background scheduler started.")

def shutdown_scheduler():
    """Shutdown the background scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Investment background scheduler stopped.")
