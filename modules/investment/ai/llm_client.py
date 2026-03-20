import json
from typing import List, Optional, Dict, Any, Literal
from loguru import logger
from google import genai
from google.genai import types
from datetime import datetime, timezone

from core.config import settings
from modules.investment.ai.schemas import ContextPackage, SymbolReport, PatternAnalysis, WeeklyDigest, ComparisonReport, BlindSpot
from modules.investment.ai.prompts import SYSTEM_PROMPT, SYMBOL_ANALYSIS_PROMPT, PATTERN_PROMPT, WEEKLY_DIGEST_PROMPT, COMPARISON_PROMPT, PATTERN_SYNTHESIS_PROMPT, HISTORICAL_QA_PROMPT

# Initialize Gemini Client (new google-genai SDK)
client = genai.Client(api_key=settings.gemini_api_key)

FLASH = getattr(settings, "gemini_model_flash", "gemini-3-flash-preview")
PRO   = getattr(settings, "gemini_model_pro", "gemini-3.1-pro-preview")

MODEL_ROUTING = {
    "sentiment_batch": FLASH,
    "quick_qa":        FLASH,
    "symbol_analysis": PRO,
    "weekly_digest":   PRO,
    "blind_spots":     PRO,
    "pattern_detect":  PRO,
    "comparison":      PRO,
}

class LLMClient:
    def __init__(self):
        pass

    def _get_language_instruction(self, lang: str) -> str:
        return "CRITICAL: You MUST write your entire analysis, reasoning, and any text fields in Turkish." if lang == "tr" else "CRITICAL: You MUST write your entire analysis, reasoning, and any text fields in English."

    def _get_system_prompt(self, lang: str) -> str:
        return SYSTEM_PROMPT.format(language_instruction=self._get_language_instruction(lang))

    async def analyze_symbol(self, symbol: str, timeframe: str, context: ContextPackage, lang: str = "tr") -> SymbolReport:
        dt_str = datetime.now(timezone.utc).isoformat()
        prompt = SYMBOL_ANALYSIS_PROMPT.format(
            symbol=symbol,
            timeframe=timeframe,
            context=context.model_dump_json()
        )
        
        try:
            model_id = MODEL_ROUTING.get("symbol_analysis", PRO)
            logger.info(f"Calling Gemini ({model_id}) via models.generate_content")
            
            response = client.models.generate_content(
                model=model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self._get_system_prompt(lang),
                    response_mime_type='application/json',
                    max_output_tokens=4096
                )
            )
            
            data = json.loads(response.text or "{}")
            if 'data_as_of' not in data:
                data['data_as_of'] = dt_str
            return SymbolReport.model_validate(data)
        except Exception as e:
            logger.error(f"Failed to parse LLM Output into SymbolReport: {e}")
            raise ValueError(f"LLM response did not match required JSON schema: {e}")

    async def find_patterns(self, symbol: str, context: ContextPackage, lang: str = "tr") -> PatternAnalysis:
        prompt = PATTERN_PROMPT.format(
            symbol=symbol,
            context=context.model_dump_json()
        )
        
        try:
            model_id = MODEL_ROUTING.get("pattern_detect", PRO)
            logger.info(f"Calling Gemini ({model_id}) via models.generate_content")
            
            response = client.models.generate_content(
                model=model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self._get_system_prompt(lang),
                    response_mime_type='application/json',
                    max_output_tokens=4096
                )
            )
            
            return PatternAnalysis.model_validate_json(response.text or "{}")
        except Exception as e:
            logger.error(f"Failed to parse LLM Output into PatternAnalysis: {e}")
            raise ValueError(f"LLM response did not match required JSON schema: {e}")

    async def generate_weekly_digest(self, watched_symbols_context: dict, lang: str = "tr") -> WeeklyDigest:
        dt_str = datetime.now(timezone.utc).isoformat()
        context_str = json.dumps({k: json.loads(v.model_dump_json()) for k, v in watched_symbols_context.items()})
        
        prompt = WEEKLY_DIGEST_PROMPT.format(context=context_str)
        
        try:
            model_id = MODEL_ROUTING.get("weekly_digest", PRO)
            logger.info(f"Calling Gemini ({model_id}) via models.generate_content")
            
            response = client.models.generate_content(
                model=model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self._get_system_prompt(lang),
                    response_mime_type='application/json',
                    max_output_tokens=4096
                )
            )
            
            data = json.loads(response.text or "{}")
            if 'data_as_of' not in data:
                data['data_as_of'] = dt_str
            return WeeklyDigest.model_validate(data)
        except Exception as e:
            logger.error(f"Failed to parse LLM Output into WeeklyDigest: {e}")
            raise ValueError(f"LLM response did not match required JSON schema: {e}")

    async def compare_symbols(self, context_str: str, lang: str = "tr") -> ComparisonReport:
        prompt = COMPARISON_PROMPT.format(context=context_str)
        try:
            model_id = MODEL_ROUTING.get("comparison", PRO)
            logger.info(f"Calling Gemini ({model_id}) via models.generate_content")
            
            response = client.models.generate_content(
                model=model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self._get_system_prompt(lang),
                    response_mime_type='application/json',
                    max_output_tokens=4096
                )
            )
            
            return ComparisonReport.model_validate_json(response.text or "{}")
        except Exception as e:
            logger.error(f"Failed to parse LLM Output into ComparisonReport: {e}")
            raise ValueError(f"LLM response did not match required JSON schema: {e}")

    async def answer_question(self, question: str, context: ContextPackage, lang: str = "tr") -> str:
        prompt = f"Context Package:\n{context.model_dump_json()}\n\nQuestion: {question}\n\nAnswer thoughtfully based directly on the provided context."
        try:
            model_id = MODEL_ROUTING.get("quick_qa", FLASH)
            logger.info(f"Calling Gemini ({model_id}) for Q&A via models.generate_content")
            
            response = client.models.generate_content(
                model=model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self._get_system_prompt(lang),
                    max_output_tokens=4096
                )
            )
            
            return response.text or ""
        except Exception as e:
            logger.error(f"Error answering question: {e}")
            return "Internal Error"

    async def synthesize_patterns(
        self,
        symbol: str,
        similar_setups: Any,
        macro_triggers: Any,
        sector_divergence: Any,
        blind_spots: Any,
        lang: str = "tr"
    ) -> str:
        """Generates a skeptical narrative synthesis of all pattern findings."""
        prompt = PATTERN_SYNTHESIS_PROMPT.format(
            symbol=symbol,
            similar_setups=similar_setups,
            macro_triggers=macro_triggers,
            sector_divergence=sector_divergence,
            blind_spots=blind_spots,
            language_instruction=self._get_language_instruction(lang)
        )
        
        try:
            model_id = MODEL_ROUTING.get("pattern_detect", PRO)
            logger.info(f"Calling Gemini ({model_id}) for pattern synthesis")
            
            response = client.models.generate_content(
                model=model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self._get_system_prompt(lang),
                    max_output_tokens=4096
                )
            )
            
            return response.text or ""
        except Exception as e:
            logger.error(f"Error synthesizing patterns: {e}")
            return "Error generating synthesis."

    async def answer_with_history(
        self,
        question: str,
        symbol: str,
        history_text: str,
        current_context: ContextPackage,
        lang: str = "tr"
    ) -> str:
        prompt = HISTORICAL_QA_PROMPT.format(
            question=question,
            symbol=symbol,
            relevant_reports=history_text,
            current_context=current_context.model_dump_json(),
            language_instruction=self._get_language_instruction(lang)
        )
        
        try:
            model_id = MODEL_ROUTING.get("symbol_analysis", PRO)
            logger.info(f"Calling Gemini ({model_id}) for Historical Q&A")
            
            response = client.models.generate_content(
                model=model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self._get_system_prompt(lang),
                    max_output_tokens=4096
                )
            )
            
            return response.text or ""
        except Exception as e:
            logger.error(f"Error answering historical question: {e}")
            return "Internal Error"
