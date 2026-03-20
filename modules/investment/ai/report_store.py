import uuid
import json
import chromadb
from datetime import datetime
from sqlalchemy import select, desc, text
from loguru import logger
from typing import List, Dict, Any, Optional

from core.database import AsyncSessionLocal
from modules.investment.models import AnalysisReport
from modules.investment.ai.schemas import ReportSummary

class ReportStore:
    def __init__(self):
        self._init_chroma()

    def _init_chroma(self):
        try:
            from chromadb.utils import embedding_functions
            import os
            db_path = os.path.join(os.getcwd(), "chroma_db")
            self._client = chromadb.PersistentClient(path=db_path)
            self._emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
            self._collection = self._client.get_or_create_collection(
                name="analysis_reports",
                embedding_function=self._emb_fn
            )
            logger.info("ChromaDB report_store collection initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB for reports: {e}")
            self._collection = None

    async def save_report(
        self,
        symbol: str,
        timeframe: str,
        report_type: str,
        content: dict,
        llm_summary: str,
        conviction_level: int,
        data_as_of: datetime
    ) -> str:
        report_id = uuid.uuid4()
        async with AsyncSessionLocal() as session:
            new_report = AnalysisReport(
                id=report_id,
                symbol=symbol,
                timeframe=timeframe,
                report_type=report_type,
                content=content,
                llm_summary=llm_summary,
                conviction_level=conviction_level,
                data_as_of=data_as_of
            )
            session.add(new_report)
            await session.commit()
            
        logger.info(f"Saved {report_type} for {symbol} to DB (ID: {report_id})")
        return str(report_id)

    async def get_recent_reports(
        self,
        symbol: str,
        limit: int = 10,
        report_type: str | None = None
    ) -> List[ReportSummary]:
        async with AsyncSessionLocal() as session:
            stmt = select(AnalysisReport).where(AnalysisReport.symbol == symbol)
            if report_type:
                stmt = stmt.where(AnalysisReport.report_type == report_type)
            stmt = stmt.order_by(desc(AnalysisReport.created_at)).limit(limit)
            
            result = await session.execute(stmt)
            reports = result.scalars().all()
            
            return [
                ReportSummary(
                    id=str(r.id),
                    symbol=r.symbol,
                    timeframe=r.timeframe,
                    report_type=r.report_type,
                    llm_summary=r.llm_summary,
                    conviction_level=r.conviction_level,
                    created_at=r.created_at,
                    data_as_of=r.data_as_of
                ) for r in reports
            ]

    async def get_report_by_id(self, report_id: str) -> dict | None:
        async with AsyncSessionLocal() as session:
            try:
                uid = uuid.UUID(report_id)
                stmt = select(AnalysisReport).where(AnalysisReport.id == uid)
                result = await session.execute(stmt)
                report = result.scalar_one_or_none()
                return report.content if report else None
            except Exception as e:
                logger.error(f"Error fetching report {report_id}: {e}")
                return None

    async def get_reports_for_digest(
        self,
        symbols: List[str],
        since: datetime
    ) -> List[ReportSummary]:
        async with AsyncSessionLocal() as session:
            stmt = select(AnalysisReport).where(
                AnalysisReport.symbol.in_(symbols),
                AnalysisReport.created_at >= since
            ).order_by(desc(AnalysisReport.created_at))
            
            result = await session.execute(stmt)
            reports = result.scalars().all()
            
            return [
                ReportSummary(
                    id=str(r.id),
                    symbol=r.symbol,
                    timeframe=r.timeframe,
                    report_type=r.report_type,
                    llm_summary=r.llm_summary,
                    conviction_level=r.conviction_level,
                    created_at=r.created_at,
                    data_as_of=r.data_as_of
                ) for r in reports
            ]

    async def embed_and_index(self, report_id: str, text: str, metadata: dict) -> None:
        if not self._collection:
            return
            
        try:
            self._collection.upsert(
                ids=[report_id],
                documents=[text],
                metadatas=[metadata]
            )
            logger.info(f"Indexed report {report_id} in ChromaDB.")
        except Exception as e:
            logger.error(f"Failed to index report {report_id}: {e}")

    async def search_relevant_reports(
        self,
        query: str,
        symbols: List[str] | None = None,
        n: int = 5
    ) -> List[Dict[str, Any]]:
        if not self._collection:
            return []
            
        where_clause: Dict[str, Any] = {}
        if symbols and len(symbols) > 0:
            if len(symbols) == 1:
                where_clause = {"symbol": symbols[0]}
            else:
                where_clause = {"symbol": {"$in": symbols}}
                
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=n,
                where=where_clause if where_clause else None
            )
            
            ret = []
            if results and results.get('documents') and results['documents']:
                for idx, doc in enumerate(results['documents'][0]):
                    meta = results['metadatas'][0][idx] if results.get('metadatas') else {}
                    score = results['distances'][0][idx] if results.get('distances') else 0.0
                    ret.append({
                        "report_id": results['ids'][0][idx],
                        "symbol": meta.get("symbol"),
                        "created_at": meta.get("created_at"),
                        "relevant_excerpt": doc[:500],
                        "similarity_score": score
                    })
            return ret
        except Exception as e:
            logger.error(f"Failed to search reports in ChromaDB: {e}")
            return []
