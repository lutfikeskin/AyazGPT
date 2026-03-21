import pytest
import unittest.mock as mock
from datetime import datetime, timezone
import json
import asyncio
from modules.investment.ai.llm_client import LLMClient
from modules.investment.ai.schemas import ContextPackage, SourceRef, SymbolReport
from modules.investment.analysis.schemas import AnalysisResult, TechnicalAnalysisResult, FundamentalAnalysisResult, AggregatedSentiment, RiskAnalysisResult

@pytest.mark.asyncio
async def test_analyze_symbol_source_mapping():
    # 1. Setup Mock Context
    news_id = "news_123"
    macro_id = "macro_FEDFUNDS"
    price_id = "price_THYAO_latest"
    
    available_sources = [
        SourceRef(id=news_id, type="news", label="Test News", date=datetime.now(timezone.utc)),
        SourceRef(id=macro_id, type="macro", label="FED Funds Rate", date=datetime.now(timezone.utc)),
        SourceRef(id=price_id, type="price", label="Price Data", date=datetime.now(timezone.utc))
    ]
    
    mock_context = mock.MagicMock(spec=ContextPackage)
    mock_context.available_sources = available_sources
    mock_context.model_dump_json.return_value = "{}"
    
    # 2. Mock LLM Response
    mock_llm_data = {
        "executive_summary": "Test Summary",
        "price_performance": "Good",
        "key_catalysts": ["C1"],
        "risks": ["R1"],
        "what_i_might_be_missing": ["M1"],
        "pattern_found": True,
        "pattern_description": "P1",
        "macro_connection": "Macro1",
        "sentiment_trend": "Bullish",
        "conviction_level": 8,
        "conviction_reasoning": "Reason1",
        "sources_cited": [news_id, macro_id, "fabricated_id"],
        "data_as_of": datetime.now(timezone.utc).isoformat()
    }
    
    llm_client = LLMClient()
    
    # We need to mock the Gemini client call inside analyze_symbol
    with mock.patch("modules.investment.ai.llm_client.client.models.generate_content") as mock_gen:
        mock_response = mock.MagicMock()
        mock_response.text = json.dumps(mock_llm_data)
        mock_gen.return_value = mock_response
        
        # 3. Execute
        report = await llm_client.analyze_symbol("THYAO.IS", "1M", mock_context)
        
        # 4. Verify
        assert len(report.sources) == 2
        assert report.sources[0].id == news_id
        assert report.sources[1].id == macro_id
        # Verify fabricated_id was discarded
        assert not any(s.id == "fabricated_id" for s in report.sources)
        
        print("Source mapping verification passed!")

if __name__ == "__main__":
    asyncio.run(test_analyze_symbol_source_mapping())
