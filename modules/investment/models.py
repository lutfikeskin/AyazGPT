from datetime import datetime
from sqlalchemy import String, Float, DateTime, Text, BigInteger, Index, Integer, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func
import uuid

from core.database import Base

class MarketPrice(Base):
    __tablename__ = "market_prices"
    
    symbol: Mapped[str] = mapped_column(String(50), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    open: Mapped[float] = mapped_column(Float, nullable=True)
    high: Mapped[float] = mapped_column(Float, nullable=True)
    low: Mapped[float] = mapped_column(Float, nullable=True)
    close: Mapped[float] = mapped_column(Float, nullable=True)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=True)
    source: Mapped[str] = mapped_column(String(50))


class NewsItem(Base):
    __tablename__ = "news_items"
    
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(1000))
    source: Mapped[str] = mapped_column(String(100))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    symbols_mentioned: Mapped[list[str]] = mapped_column(JSONB, default=list)
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=True)


class MacroIndicator(Base):
    __tablename__ = "macro_indicators"
    
    indicator: Mapped[str] = mapped_column(String(100), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    value: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(50))


class AnalysisReport(Base):
    __tablename__ = "analysis_reports"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    timeframe: Mapped[str] = mapped_column(String(20))
    report_type: Mapped[str] = mapped_column(String(50), index=True)
    content: Mapped[dict] = mapped_column(JSONB)
    llm_summary: Mapped[str] = mapped_column(Text)
    conviction_level: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    data_as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_analysis_reports_symbol_created_at", "symbol", text("created_at DESC")),
        Index("ix_analysis_reports_type_created_at", "report_type", text("created_at DESC")),
    )

async def setup_hypertables():
    """Converts the standard market_prices table into a TimescaleDB hypertable."""
    from core.database import AsyncSessionLocal
    from sqlalchemy import text
    from loguru import logger
    
    async with AsyncSessionLocal() as session:
        try:
            # Check and create hypertable on the 'timestamp' column
            await session.execute(text("SELECT create_hypertable('market_prices', by_range('timestamp'), if_not_exists => TRUE);"))
            await session.commit()
            logger.info("Market prices hypertable successfully verified/configured.")
        except Exception as e:
            await session.rollback()
            # This throws an error if the table is not created yet (e.g., waiting for alembic)
            logger.warning(f"Hypertable setup delayed or error occurred (ignored if table missing): {e}")
