import asyncio
from modules.investment.ai.context_builder import ContextBuilder

async def check_context():
    print("Checking ContextBuilder DB integration...")
    cb = ContextBuilder()
    
    symbol = "THYAO.IS"
    timeframe = "1M"
    
    try:
        context = await cb.build(symbol, timeframe)
        if not context:
            print("FAILED: Context build returned None (likely no price data in DB)")
            return

        print(f"\nContext built for {symbol}")
        print(f"Macro Indicators: {context.macro_indicators}")
        print(f"Available Sources Count: {len(context.available_sources)}")
        
        for source in context.available_sources:
            print(f" - [{source.type.upper()}] ID: {source.id} | Label: {source.label} | Date: {source.date}")
            
        # Check if we have at least one of each expected type if data exists
        types = [s.type for s in context.available_sources]
        print(f"\nSource types found: {set(types)}")
        
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(check_context())
