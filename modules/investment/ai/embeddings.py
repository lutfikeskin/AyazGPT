import os
import chromadb # type: ignore
from loguru import logger
from typing import List, Dict, Any, Optional

class EmbeddingService:
    _instance = None
    _collection = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingService, cls).__new__(cls)
            cls._instance._init_client()
        return cls._instance

    def _init_client(self):
        try:
            db_path = os.path.join(os.getcwd(), "chroma_db")
            self._client = chromadb.PersistentClient(path=db_path)
            
            from chromadb.utils import embedding_functions # type: ignore
            emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
            
            self._collection = self._client.get_or_create_collection(
                name="investment_news",
                embedding_function=emb_fn
            )
            logger.info("ChromaDB embedding service initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")

    def add_news_items(self, items: List[Any]):
        """Adds NewsItem sqlalchemy objects to ChromaDB"""
        if not self._collection or not items:
            return
            
        ids = []
        documents = []
        metadatas = []
        
        for item in items:
            if not item.id or not item.title:
                continue
                
            ids.append(str(item.id))
            doc = f"{item.title}. {item.body or ''}"
            documents.append(doc)
            
            symbols_str = ",".join(item.symbols_mentioned) if item.symbols_mentioned else ""
            
            metadatas.append({
                "symbol": symbols_str,
                "published_at": item.published_at.isoformat() if item.published_at else "",
                "sentiment_score": float(item.sentiment_score) if item.sentiment_score is not None else 0.0,
                "source": item.source or ""
            })
            
        try:
            self._collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
            logger.info(f"Upserted {len(ids)} items to ChromaDB.")
        except Exception as e:
            logger.error(f"Failed to upsert to ChromaDB: {e}")

    def search_relevant_context(self, 
                                query: str, 
                                symbols: Optional[List[str]] = None, 
                                date_range: Optional[tuple] = None, 
                                n: int = 15) -> List[Dict[str, Any]]:
        """Search relevant news for context building"""
        if not self._collection:
            return []
            
        where_clause = {}
        if symbols and len(symbols) > 0:
            where_clause = {"symbol": {"$contains": symbols[0]}}
                
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
                    ret.append({
                        "content": doc,
                        "metadata": meta
                    })
            return ret
            
        except Exception as e:
            logger.error(f"Failed to search ChromaDB: {e}")
            return []
