import streamlit as st # type: ignore
import requests
import pandas as pd
import plotly.graph_objects as go # type: ignore
from loguru import logger

API_URL = "http://localhost:8000/api/investment"

# Page configuration handled by ui/app.py

T = {
    "tr": {
        "title": "🧠 MyMind Yatırım Danışmanı",
        "watchlist": "İzleme Listesi Yönetimi",
        "add_sym": "Sembol Ekle",
        "add": "Ekle",
        "active_sym": "Aktif Sembol",
        "timeframe": "Zaman Dilimi",
        "run_analysis": "Analizi Çalıştır",
        "tab1": "📊 Sembol Analizi",
        "tab2": "📰 Haftalık Özet",
        "tab3": "💬 Soru Sor",
        "tab4": "🌍 Makro Görünüm",
        "metrics": "Temel Göstergeler",
        "price": "Güncel Fiyat",
        "conviction": "İnanç Seviyesi",
        "sentiment": "Duyarlılık",
        "pattern": "Formasyon",
        "as_of": "Veri Tarihi",
        "exec_summary": "Yönetici Özeti",
        "catalysts": "🚀 Temel Katalizörler",
        "risks": "⚠️ Riskler",
        "missing": "🔍 Gözden Kaçanlar",
        "detected_pattern": "📈 Tespit Edilen Formasyon",
        "macro_conn": "🌍 Makro Bağlantı",
        "click_run": "Rapor oluşturmak için 'Analizi Çalıştır'a tıklayın.",
        "refresh_digest": "Özeti Yenile",
        "portfolio_overview": "Portföy Genel Görünümü",
        "top_performers": "🏆 En İyi Performans Gösterenler",
        "macro_env": "🌍 Makro Ortam",
        "portfolio_insights": "💡 Portföy İçgörüleri",
        "ask_mymind": "MyMind'a Sor",
        "ask_placeholder": "Yatırımlarınız hakkında bir şey sorun...",
        "ctx_sym": "Bağlam Sembolü (Opsiyonel)",
        "ask": "Sor",
        "analyzing": "Bağlam analiz ediliyor...",
        "answer": "Cevap",
        "macro_dash": "Makro Paneli",
        "snapshot": "Güncel Durum",
        "detected": "Bulundu",
        "none": "Yok",
        "history": "Rapor Geçmişi",
        "conv_trend": "İnanç Trendi",
        "search_history": "Geçmiş raporlarda ara",
        "view_full": "Tam Raporu Görüntüle",
        "compare": "Güncelle Karşılaştır",
        "sources": "Kullanılan Kaynaklar",
        "view_changed": "Görüş Değişti mi?",
        "yes": "Evet",
        "no": "Hayır",
        "tab5": "🎯 Tavsiyeler",
        "regime": "Piyasa Rejimi",
        "scan": "Tarama Başlat",
        "scan_warning": "Bu işlem 2-4 dakika sürer. {size} sembol taranacak.",
        "top_opps": "🚀 En İyi Fırsatlar",
        "watchlist_eval": "📋 İzleme Listesi Değerlendirmesi",
        "to_avoid": "🛑 Kaçınılacaklar",
        "primary_thesis": "Temel Tez",
        "counter_thesis": "Şeytanın Avukatı (Bear Case)",
        "invalidation": "Geçersiz Kılma Tetikleyicileri",
        "return_est": "Getiri Tahminleri (Tarihsel)",
        "confidence": "Güven",
        "regime_align": "Rejim Uyumu",
        "scanning": "Taranıyor: {symbol} ({current}/{total})",
        "scan_done": "Tarama tamamlandı! {duration} saniye sürdü."
    },
    "en": {
        "title": "🧠 MyMind Investment Advisor",
        "watchlist": "Watchlist Management",
        "add_sym": "Add Symbol",
        "add": "Add",
        "active_sym": "Active Symbol",
        "timeframe": "Timeframe",
        "run_analysis": "Run Analysis",
        "tab1": "📊 Symbol Analysis",
        "tab2": "📰 Weekly Digest",
        "tab3": "💬 Ask a Question",
        "tab4": "🌍 Macro Dashboard",
        "metrics": "Key Metrics",
        "price": "Current Price",
        "conviction": "Conviction",
        "sentiment": "Sentiment",
        "pattern": "Pattern",
        "as_of": "Data As Of",
        "exec_summary": "Executive Summary",
        "catalysts": "🚀 Key Catalysts",
        "risks": "⚠️ Risks",
        "missing": "🔍 What You Might Be Missing",
        "detected_pattern": "📈 Detected Pattern",
        "macro_conn": "🌍 Macro Connection",
        "click_run": "Click 'Run Analysis' to fetch the latest AI synthesis.",
        "refresh_digest": "Refresh Digest",
        "portfolio_overview": "Portfolio Overview",
        "top_performers": "🏆 Top Performers",
        "macro_env": "🌍 Macro Environment",
        "portfolio_insights": "💡 Portfolio Insights",
        "ask_mymind": "Ask MyMind",
        "ask_placeholder": "Ask anything about your investments...",
        "ctx_sym": "Context Symbol (Optional)",
        "ask": "Ask",
        "analyzing": "Analyzing context & consulting AI...",
        "answer": "Answer",
        "macro_dash": "Macro Dashboard",
        "snapshot": "Current Snapshot",
        "detected": "Detected",
        "none": "None",
        "history": "Report History",
        "conv_trend": "Conviction Trend",
        "search_history": "Search past reports",
        "view_full": "View Full Report",
        "compare": "Compare with Current",
        "sources": "Sources Used",
        "view_changed": "Has View Changed?",
        "yes": "Yes",
        "no": "No",
        "tab5": "🎯 Recommendations",
        "regime": "Market Regime",
        "scan": "Start Universe Scan",
        "scan_warning": "This takes 2-4 minutes. {size} symbols will be scanned.",
        "top_opps": "🚀 Top Opportunities",
        "watchlist_eval": "📋 Watchlist Evaluation",
        "to_avoid": "🛑 Symbols to Avoid",
        "primary_thesis": "Primary Thesis",
        "counter_thesis": "Devil's Advocate (Bear Case)",
        "invalidation": "Invalidation Triggers",
        "return_est": "Return Estimates (Historical)",
        "confidence": "Confidence",
        "regime_align": "Regime Alignment",
        "scanning": "Scanning: {symbol} ({current}/{total})",
        "scan_done": "Scan complete in {duration} seconds."
    }
}

lang_option = st.sidebar.selectbox("Dil / Language", ["Türkçe", "English"], index=0)
lang = "tr" if lang_option == "Türkçe" else "en"
t = T[lang]

@st.cache_data(ttl=600)
def fetch_regime():
    try:
        res = requests.get(f"{API_URL}/regime")
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        logger.error(f"Error fetching regime: {e}")
    return None

# Add persistent Regime Card at the top
regime_data = fetch_regime()
if regime_data:
    r_colors = {
        "risk_on": "green", "risk_off": "red", "fx_pressure": "orange",
        "rate_tightening": "yellow", "rate_easing": "blue", "inflation_driven": "violet"
    }
    color = r_colors.get(regime_data['regime'], "gray")
    st.markdown(f"""
    <div style="background-color: rgba(255, 255, 255, 0.05); border-left: 5px solid {color}; padding: 15px; border-radius: 5px; margin-bottom: 25px;">
        <h4 style="margin-top: 0; color: {color};">{t['regime']}: {regime_data['regime'].upper().replace('_', ' ')}</h4>
        <p style="margin-bottom: 5px;">{regime_data['narrative']}</p>
        <small style="opacity: 0.7;">Signals: {", ".join(regime_data['signals_used'])} | Detected at: {regime_data['detected_at'][:16]}</small>
    </div>
    """, unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def fetch_symbols():
    try:
        res = requests.get(f"{API_URL}/symbols")
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        logger.error(f"Error fetching symbols: {e}")
    return ["AAPL", "THYAO.IS"]

@st.cache_data(ttl=3600)
def fetch_analysis(symbol, timeframe, l):
    try:
        res = requests.get(f"{API_URL}/analyze/{symbol}?timeframe={timeframe}&lang={l}")
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        logger.error(f"Error fetching analysis: {e}")
    return None

@st.cache_data(ttl=3600)
def fetch_digest(l):
    try:
        res = requests.get(f"{API_URL}/digest/weekly?lang={l}")
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        logger.error(f"Error fetching digest: {e}")
    return None

@st.cache_data(ttl=3600)
def fetch_patterns(symbol, l):
    try:
        res = requests.get(f"{API_URL}/patterns/{symbol}?lang={l}")
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        logger.error(f"Error fetching patterns: {e}")
    return None

@st.cache_data(ttl=3600)
def fetch_macro():
    try:
        res = requests.get(f"{API_URL}/macro/snapshot")
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        logger.error(f"Error fetching macro: {e}")
    return {}

@st.cache_data(ttl=300)
def fetch_prices(symbol, timeframe):
    try:
        res = requests.get(f"{API_URL}/prices/{symbol}?timeframe={timeframe}")
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        logger.error(f"Error fetching prices: {e}")
    return None

def fetch_q_and_a(symbol, question, l, use_history=False):
    endpoint = f"{API_URL}/ask-with-history" if use_history else f"{API_URL}/ask"
    payload = {"symbol": symbol, "question": question, "lang": l}
    try:
        res = requests.post(endpoint, json=payload)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        return {"answer": f"Error connecting to API: {e}"}
    return {"answer": "Error generating response."}

@st.cache_data(ttl=300)
def fetch_report_history(symbol):
    try:
        res = requests.get(f"{API_URL}/reports/{symbol}")
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        logger.error(f"Error fetching report history: {e}")
    return []

def fetch_report_content(symbol, report_id):
    try:
        res = requests.get(f"{API_URL}/reports/{symbol}/{report_id}")
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        logger.error(f"Error fetching report content: {e}")
    return None

def fetch_latest_scan():
    try:
        res = requests.get(f"{API_URL}/scan/latest")
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return None

def plot_candlestick(prices):
    if not prices or not prices.get("dates"):
        return None
        
    fig = go.Figure(data=[go.Candlestick(
                x=prices['dates'],
                open=prices['open'],
                high=prices['high'],
                low=prices['low'],
                close=prices['close'])])
                
    fig.update_layout(
        xaxis_rangeslider_visible=False, 
        template="plotly_dark", 
        title="Price Chart & Volume",
        margin=dict(l=0, r=0, t=30, b=0),
        height=400
    )
    return fig

def plot_conviction_trend(history):
    if not history: return None
    df = pd.DataFrame(history)
    df['created_at'] = pd.to_datetime(df['created_at'])
    df = df.sort_values('created_at')
    
    fig = go.Figure(data=go.Scatter(
        x=df['created_at'], 
        y=df['conviction_level'],
        mode='lines+markers',
        line=dict(color='#00ffcc', width=2),
        marker=dict(size=8, color='#00ffcc')
    ))
    fig.update_layout(
        template="plotly_dark",
        margin=dict(l=0, r=0, t=20, b=0),
        height=150,
        xaxis=dict(showgrid=False),
        yaxis=dict(range=[0, 11], tickvals=[0, 5, 10])
    )
    return fig

def render_recommendation_card(rec):
    badge_colors = {
        "strong_buy": "#00ff00", "buy": "#7FFF00", "hold": "#FFFF00", 
        "reduce": "#FFD700", "avoid": "#FF4500"
    }
    color = badge_colors.get(rec['recommendation'], "gray")
    
    with st.container():
        st.markdown(f"""
        <div style="border: 1px solid rgba(255,255,255,0.1); padding: 20px; border-radius: 10px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <h3 style="margin: 0;">{rec['symbol']}</h3>
                <span style="background-color: {color}; color: black; padding: 5px 15px; border-radius: 20px; font-weight: bold;">
                    {rec['recommendation'].upper()}
                </span>
            </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
             st.write(f"**{t['price']}:** {rec['current_price']:.2f}")
             st.write(f"**{t['confidence']}:** {rec['confidence']}/10")
             st.progress(rec['confidence'] / 10)
        with col2:
             st.write(f"**{t['return_est']}**")
             ret = rec['returns']
             st.markdown(f"""
             - 1M: {ret['return_1m']}%
             - 3M: {ret['return_3m']}%
             - 1Y: {ret['return_1y']}%
             """)
        with col3:
             st.write(f"**{t['regime_align']}**")
             st.info(rec['macro_alignment'])
        
        st.markdown(f"**{t['primary_thesis']}**")
        st.write(rec['primary_thesis'])
        
        col_cat, col_risk = st.columns(2)
        with col_cat:
            st.write(f"**{t['catalysts']}**")
            for c in rec['key_catalysts']: st.markdown(f"- {c}")
        with col_risk:
            st.write(f"**{t['risks']}**")
            for r in rec['key_risks']: st.markdown(f"- {r}")
            
        st.markdown(f"""
        <div style="background-color: rgba(255, 165, 0, 0.1); padding: 15px; border-radius: 5px; border: 1px dashed orange;">
            <h4 style="margin-top: 0; color: orange;">{t['counter_thesis']}</h4>
            <p>{rec['counter_thesis']}</p>
            <p><strong>{t['invalidation']}:</strong></p>
            <ul>{"".join([f"<li>{trig}</li>" for trig in rec['invalidation_triggers']])}</ul>
        </div>
        """, unsafe_allow_html=True)
        
        if rec.get('blind_spots_flagged'):
             st.write("**Blind Spots:**")
             for bs in rec['blind_spots_flagged']:
                 st.error(f"**{bs.get('title', bs.get('name', 'N/A'))}**: {bs.get('detail', bs.get('description', ''))}")
        
        st.caption(f"Quality: {rec['analysis_quality']} | Source: {rec['returns']['data_source']} | {rec['disclaimer']}")
        st.markdown("</div>", unsafe_allow_html=True)

# UI Layout
st.title(t["title"])

st.sidebar.header(t["watchlist"])
symbols = fetch_symbols()

# Add Symbol
with st.sidebar.form("add_symbol_form"):
    new_symbol = st.text_input(t["add_sym"])
    submitted = st.form_submit_button(t["add"])
    if submitted and new_symbol:
        try:
            res = requests.post(f"{API_URL}/symbols", json={"symbol": new_symbol})
            if res.status_code == 200:
                st.sidebar.success(f"{new_symbol} added" if lang=="en" else f"{new_symbol} eklendi")
                st.rerun()
        except:
            st.sidebar.error("Failed to add symbol.")

selected_symbol = st.sidebar.selectbox(t["active_sym"], symbols)
timeframe = st.sidebar.selectbox(t["timeframe"], ["1W", "1M", "3M", "1Y", "5Y"], index=1)

run_analysis = st.sidebar.button(t["run_analysis"], type="primary")

tab1, tab2, tab3, tab4, tab5 = st.tabs([t["tab1"], t["tab2"], t["tab3"], t["tab4"], t["tab5"]])

with tab1:
    if selected_symbol and run_analysis:
        st.cache_data.clear() # Force refresh on explicit click
        
    data = fetch_analysis(selected_symbol, timeframe, lang)
    prices = fetch_prices(selected_symbol, timeframe)
    
    if data:
        st.header(f"{selected_symbol} ({timeframe})")
        
        # Price Chart
        if prices and prices.get('dates'):
            fig = plot_candlestick(prices)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
                
        # Metric Cards
        st.markdown(f"### {t['metrics']}")
        cols = st.columns(5)
        
        current_price = prices['close'][-1] if prices and prices.get('close') else "N/A"
        
        cols[0].metric(t["price"], f"{current_price:.2f}" if isinstance(current_price, float) else current_price)
        cols[1].metric(t["conviction"], f"{data.get('conviction_level', 0)}/10")
        cols[2].metric(t["sentiment"], data.get('sentiment_trend', 'Neutral').capitalize())
        cols[3].metric(t["pattern"], t["detected"] if data.get('pattern_found') else t["none"])
        cols[4].metric(t["as_of"], data.get('data_as_of', '')[:10])
        
        st.markdown(f"### {t['exec_summary']}")
        st.info(data.get("executive_summary", ""))
        
        col_cat, col_risk = st.columns(2)
        with col_cat:
            st.markdown(f"#### {t['catalysts']}")
            for c in data.get("key_catalysts", []):
                st.markdown(f"- {c}")
        with col_risk:
            st.markdown(f"#### {t['risks']}")
            for r in data.get("risks", []):
                st.markdown(f"- {r}")
                
        st.markdown(f"### {t['missing']}")
        for m in data.get("what_i_might_be_missing", []):
            st.warning(f"**Blind Spot:** {m}")
            
        if data.get("pattern_found"):
            st.markdown(f"### {t['detected_pattern']}")
            st.success(data.get("pattern_description", ""))
            
        st.markdown(f"### {t['macro_conn']}")
        st.write(data.get("macro_connection", ""))
        
        # History Section
        st.markdown("---")
        st.subheader(t["history"])
        history = fetch_report_history(selected_symbol)
        
        if history:
            col_trend, col_list = st.columns([1, 2])
            with col_trend:
                st.markdown(f"**{t['conv_trend']}**")
                trend_fig = plot_conviction_trend(history)
                if trend_fig:
                    st.plotly_chart(trend_fig, use_container_width=True)
            
            with col_list:
                for r in history[:5]:
                    with st.expander(f"{r['created_at'][:10]} - {r['timeframe']} - Conviction: {r['conviction_level']}/10"):
                        st.write(r['llm_summary'])
                        if st.button(t["view_full"], key=f"full_{r['id']}"):
                            full_content = fetch_report_content(selected_symbol, r['id'])
                            st.json(full_content)
        else:
            st.info("No historical reports found for this symbol.")
            
    elif selected_symbol:
        st.warning(t["click_run"])

with tab2:
    st.header(t["tab2"])
    if st.button(t["refresh_digest"]):
        st.cache_data.clear()
        
    digest = fetch_digest(lang)
    if digest:
        st.markdown(f"### {t['portfolio_overview']}")
        st.info(digest.get("executive_summary", ""))
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader(t["top_performers"])
            for p in digest.get("top_performers", []):
                st.markdown(f"- {p}")
        with col2:
            st.subheader(t["macro_env"])
            st.write(digest.get("macro_environment", ""))
            
        st.markdown("---")
        st.subheader(t["portfolio_insights"])
        for i in digest.get("portfolio_insights", []):
            st.markdown(f"- {i}")
    else:
        st.info(t["click_run"])

with tab3:
    st.header(t["ask_mymind"])
    
    col_ask, col_opt = st.columns([3, 1])
    with col_ask:
        question = st.text_input(t["ask_placeholder"])
    with col_opt:
        use_history = st.toggle(t["search_history"], value=True)
        
    target_symbol = st.selectbox(t["ctx_sym"], symbols)
    
    if st.button(t["ask"]) and question:
        with st.spinner(t["analyzing"]):
            res = fetch_q_and_a(target_symbol, question, lang, use_history=use_history)
            st.markdown(f"### {t['answer']}")
            st.write(res.get("answer", ""))
            
            if use_history and res.get("sources_used"):
                st.markdown(f"#### {t['sources']}")
                for s in res['sources_used']:
                    st.caption(f"- {s['created_at'][:10]} ({s['report_type']}): {s['llm_summary'][:100]}...")
                
                col_v, col_outcome = st.columns(2)
                with col_v:
                    st.write(f"**{t['view_changed']}**")
                    st.write(t["yes"] if res.get("has_view_changed") else t["no"])

with tab4:
    st.header(t["macro_dash"])
    macro = fetch_macro()
    if macro:
        st.markdown(f"### {t['snapshot']}")
        cols = st.columns(len(macro))
        for i, (k, v) in enumerate(macro.items()):
            cols[i].metric(k, f"{v}")
    else:
        st.info("Macro snapshot unavailable.")

with tab5:
    st.header(t["tab5"])
    
    col_scan, col_info = st.columns([1, 2])
    with col_scan:
        if st.button(t["scan"], type="primary"):
            with st.spinner(t["scan_warning"].format(size=115)): # Approx universe size
                res = requests.post(f"{API_URL}/scan", json={"watchlist": symbols})
                if res.status_code == 200:
                    st.success(t["scan_done"].format(duration=res.json()['scan_duration_seconds']))
                    st.rerun()
                else:
                    st.error("Scan failed.")
    
    with col_info:
        scan_data = fetch_latest_scan()
        if scan_data:
            st.info(f"Latest Scan: {scan_data['scan_timestamp'][:16]} | Scanned: {scan_data['symbols_scanned']} symbols")
        else:
            st.warning("No universe scan results available. Start a new scan.")

    if scan_data:
        st.markdown(f"## {t['top_opps']}")
        for rec in scan_data['top_opportunities']:
            render_recommendation_card(rec)
            
        st.markdown("---")
        st.markdown(f"## {t['watchlist_eval']}")
        for rec in scan_data['watchlist_recommendations']:
            render_recommendation_card(rec)
            
        st.markdown("---")
        st.markdown(f"## {t['to_avoid']}")
        avoid_df = pd.DataFrame(scan_data['symbols_to_avoid'])
        st.table(avoid_df)
