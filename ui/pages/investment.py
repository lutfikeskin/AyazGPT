import streamlit as st # type: ignore
import requests
import pandas as pd
import plotly.graph_objects as go # type: ignore
from loguru import logger
from datetime import datetime
import time

API_URL = "http://localhost:8000/api/investment"

# ═══════════════════════════════════════════════════
# SESSION STATE INITIALIZATION
# ═══════════════════════════════════════════════════
if "page" not in st.session_state:
    st.session_state["page"] = "📊 Bugün"
if "active_symbol" not in st.session_state:
    st.session_state["active_symbol"] = None
if "analyze_clicked" not in st.session_state:
    st.session_state["analyze_clicked"] = False

# ═══════════════════════════════════════════════════
# STYLING
# ═══════════════════════════════════════════════════
st.markdown("""
<style>
/* Active nav button */
div[data-testid="stHorizontalBlock"] button:focus {
    background-color: rgba(255,255,255,0.1);
    border-bottom: 2px solid #00ffcc;
}

/* Watchlist cards */
.watchlist-card {
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 8px;
    background-color: rgba(255, 255, 255, 0.02);
}

/* Recommendation badges */
.badge-strong-buy { color: #00ff00; font-weight: bold; }
.badge-buy { color: #7FFF00; font-weight: bold; }
.badge-hold { color: #FFD700; }
.badge-reduce { color: #FFA500; }
.badge-avoid { color: #FF4500; font-weight: bold; }

/* Devil's advocate section */
.devils-advocate {
    background-color: rgba(255, 165, 0, 0.1);
    border-left: 3px solid orange;
    padding: 12px;
    border-radius: 4px;
    margin: 10px 0;
}

/* Metrics Row */
.metric-row {
     display: flex;
     justify-content: space-between;
     margin-bottom: 20px;
}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════
# DATA FETCHING (CACHED)
# ═══════════════════════════════════════════════════

@st.cache_data(ttl=300) # 5 min
def fetch_status_bar():
    try:
        res = requests.get(f"{API_URL}/macro/snapshot")
        regime = requests.get(f"{API_URL}/regime")
        if res.status_code == 200 and regime.status_code == 200:
            data = res.json()
            data['regime'] = regime.json()
            return data
    except Exception as e:
        logger.error(f"Error fetching status bar: {e}")
    return None

@st.cache_data(ttl=60)
def fetch_symbols():
    try:
        res = requests.get(f"{API_URL}/symbols")
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        logger.error(f"Error fetching symbols: {e}")
    return ["THYAO.IS", "TUPRS.IS", "KCHOL.IS"]

@st.cache_data(ttl=1800) # 30 min
def fetch_cached_reports(symbols):
    results = {}
    for sym in symbols:
        try:
            res = requests.get(f"{API_URL}/reports/{sym}?limit=1")
            if res.status_code == 200:
                results[sym] = res.json()[0] if res.json() else None
        except:
            results[sym] = None
    return results

@st.cache_data(ttl=600) # 10 min
def fetch_news():
    try:
        res = requests.get(f"{API_URL}/disclosures/recent")
        if res.status_code == 200:
            return res.json()
    except:
        return []

@st.cache_data(ttl=3600) # 1 hour
def fetch_full_analysis(symbol, timeframe):
    try:
        # We don't auto-fetch, but we use cache if available
        # Explicit refresh clears this cache
        res = requests.get(f"{API_URL}/analyze/{symbol}?timeframe={timeframe}&lang=tr")
        prices = requests.get(f"{API_URL}/prices/{symbol}?timeframe={timeframe}")
        diff = requests.get(f"{API_URL}/reports/{symbol}/diff")
        
        return {
            "analysis": res.json() if res.status_code == 200 else None,
            "prices": prices.json() if prices.status_code == 200 else None,
            "diff": diff.json() if diff.status_code == 200 else None
        }
    except Exception as e:
        logger.error(f"Analysis fetch failed: {e}")
        return None

@st.cache_data(ttl=21600) # 6 hours
def fetch_categorized_symbols():
    try:
        res = requests.get(f"{API_URL}/symbols/categorized")
        if res.status_code == 200:
            return res.json()
    except:
        return {}

@st.cache_data(ttl=21600) # 6 hours
def fetch_latest_scan():
    try:
        res = requests.get(f"{API_URL}/scan/latest")
        if res.status_code == 200:
            return res.json()
    except:
        return None

# ═══════════════════════════════════════════════════
# SHARED COMPONENTS
# ═══════════════════════════════════════════════════

def render_status_bar():
    data = fetch_status_bar()
    if data:
        cols = st.columns(4)
        
        # BIST100
        bist = data.get("BIST100", data.get("bist100", {}))
        if isinstance(bist, (int, float)):
            bist_val, bist_chg = bist, 0.0
        else:
            bist_val = bist.get("price", 0)
            bist_chg = bist.get("change", 0)
        cols[0].metric("BIST100", f"{bist_val:,.0f}", f"{bist_chg:+.2f}%")
        
        # USDTRY
        usd = data.get("USDTRY", data.get("usdtry", {}))
        if isinstance(usd, (int, float)):
            usd_val, usd_chg = usd, 0.0
        else:
            usd_val = usd.get("price", 0)
            usd_chg = usd.get("change", 0)
        cols[1].metric("USDTRY", f"{usd_val:.4f}", f"{usd_chg:+.2f}%")
        
        # Regime
        regime = data.get("regime", {})
        r_label = regime.get("regime", "N/A").upper().replace("_", " ")
        r_colors = {"risk_on": "🟢", "risk_off": "🔴", "fx_pressure": "🟠", "rate_tightening": "🟡"}
        emoji = r_colors.get(regime.get("regime"), "⚪")
        cols[2].write(f"**Piyasa Rejimi**\n\n{emoji} {r_label}")
        
        # Last Update
        ts = data.get("timestamp", "")
        if ts:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            cols[3].write(f"**Son Güncelleme**\n\n{dt.strftime('%H:%M:%S')}")
        st.divider()

def plot_candlestick(prices):
    if not prices or not prices.get("dates"):
        st.warning("Grafik verisi bulunamadı.")
        return
        
    fig = go.Figure(data=[go.Candlestick(
        x=prices['dates'],
        open=prices['open'],
        high=prices['high'],
        low=prices['low'],
        close=prices['close']
    )])
    fig.update_layout(xaxis_rangeslider_visible=False, template="plotly_dark", height=450, margin=dict(l=0,r=0,t=0,b=0))
    st.plotly_chart(fig, use_container_width=True)

# ═══════════════════════════════════════════════════
# SIDEBAR (Watchlist)
# ═══════════════════════════════════════════════════
with st.sidebar:
    st.header("📋 İzleme Listesi")
    
    # 1. Add/Search Symbol
    with st.form("add_sym", clear_on_submit=True):
        new_sym = st.text_input("Sembol Ekle", placeholder="Örn: THYAO")
        if st.form_submit_button("Ekle", use_container_width=True) and new_sym:
            # Basic validation
            clean_sym = new_sym.upper().strip()
            if not clean_sym.endswith(".IS") and len(clean_sym) <= 5 and not any(x in clean_sym for x in ["=","-"]):
                clean_sym += ".IS"
            
            res = requests.post(f"{API_URL}/symbols", json={"symbol": clean_sym})
            if res.status_code == 200:
                st.cache_data.clear()
                st.rerun()

    # 2. Categorized Browse
    st.write("---")
    st.caption("🔍 Sektörel Keşfet")
    cat_symbols = fetch_categorized_symbols()
    for cat, syms in cat_symbols.items():
        with st.expander(cat):
            # 3 columns for symbols
            c_grid = st.columns(3)
            for j, s in enumerate(syms):
                label = s.split(".")[0]
                if c_grid[j % 3].button(label, key=f"cat_btn_{s}", use_container_width=True):
                    res = requests.post(f"{API_URL}/symbols", json={"symbol": s})
                    if res.status_code == 200:
                        st.cache_data.clear()
                        st.rerun()
    
    st.write("---")
    
    # 3. Watchlist Management
    symbols = fetch_symbols()
    for sym in symbols:
        col_s, col_r = st.columns([4, 1])
        if col_s.button(sym, use_container_width=True, key=f"btn_{sym}", 
                      type="primary" if st.session_state["active_symbol"] == sym else "secondary"):
            st.session_state["active_symbol"] = sym
            st.session_state["page"] = "🔍 Analiz"
            st.session_state["analyze_clicked"] = False
            st.rerun()
        if col_r.button("X", key=f"rem_{sym}", help=f"{sym} listeden kaldır"):
            # Mock delete for now as per previous logic (waiting for backend delete if needed)
            st.toast(f"{sym} kaldırıldı")

# ═══════════════════════════════════════════════════
# TOP NAVIGATION
# ═══════════════════════════════════════════════════
PAGES = ["📊 Bugün", "🔍 Analiz", "🎯 Tavsiyeler", "💬 Soru Sor", "📋 Raporlar"]
cols = st.columns(len(PAGES))
for i, p in enumerate(PAGES):
    if cols[i].button(p, use_container_width=True, 
                    type="primary" if st.session_state["page"] == p else "secondary"):
        st.session_state["page"] = p
        st.rerun()

render_status_bar()

# ═══════════════════════════════════════════════════
# PAGE: BUGÜN
# ═══════════════════════════════════════════════════
if st.session_state["page"] == "📊 Bugün":
    st.title("Sabah Brifingi")
    
    col_reg, col_news = st.columns([3, 2])
    
    with col_reg:
        regime_data = fetch_status_bar()
        if regime_data and "regime" in regime_data:
            r = regime_data["regime"]
            r_colors = {"risk_on": "green", "risk_off": "red", "fx_pressure": "orange", "rate_tightening": "yellow"}
            color = r_colors.get(r['regime'], "gray")
            st.markdown(f"""
            <div style="background-color: rgba(255, 255, 255, 0.05); padding: 25px; border-radius: 12px; border-left: 8px solid {color};">
                <h2 style="color: {color}; margin: 0;">{r['regime'].upper().replace('_', ' ')}</h2>
                <p style="font-size: 1.1em; margin: 15px 0;">{r['narrative']}</p>
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                    {" ".join([f'<span style="background: rgba(255,255,255,0.1); padding: 2px 8px; border-radius: 4px; font-size: 0.8em;">{s}</span>' for s in r['signals_used']])}
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("🔄 Rejimi Yenile"):
                st.cache_data.clear()
                st.rerun()

    with col_news:
        st.subheader("📰 Son Önemli Haberler")
        news = fetch_news()
        if news:
            for item in news[:5]:
                with st.container():
                    st.markdown(f"**[{item['source']}]** {item['title']}")
                    st.caption(f"{item['published_at'][:16]}")
                    st.divider()
            st.button("Daha fazla haber →", use_container_width=True)
        else:
            st.info("Son 24 saatte kritik haber bulunamadı.")

    st.subheader("📋 İzleme Listesi Özeti")
    symbols = fetch_symbols()
    cached_reports = fetch_cached_reports(symbols)
    
    grid = st.columns(3)
    for i, sym in enumerate(symbols):
        with grid[i % 3]:
            report = cached_reports.get(sym)
            if report:
                st.markdown(f"""
                <div class="watchlist-card">
                    <div style="display: flex; justify-content: space-between;">
                        <span style="font-weight: bold;">{sym}</span>
                        <span class="badge-hold">{report.get('recommendation', 'HOLD') if report else 'NO DATA'}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                # Display some cached metrics if available
                if report:
                    c1, c2 = st.columns(2)
                    c1.write(f"İnanç: {report.get('conviction_level', 'N/A')}/10")
                    c2.write(f"Sentiment: {report.get('sentiment_trend', 'N/A')}")
                
                if st.button(f"Analiz Et →", key=f"go_{sym}", use_container_width=True):
                    st.session_state["active_symbol"] = sym
                    st.session_state["page"] = "🔍 Analiz"
                    st.rerun()
            else:
                st.markdown(f'<div class="watchlist-card"><b>{sym}</b><br>Analiz yok</div>', unsafe_allow_html=True)
                if st.button("Analiz Et →", key=f"init_{sym}", use_container_width=True):
                    st.session_state["active_symbol"] = sym
                    st.session_state["page"] = "🔍 Analiz"
                    st.rerun()

# ═══════════════════════════════════════════════════
# PAGE: ANALİZ
# ═══════════════════════════════════════════════════
elif st.session_state["page"] == "🔍 Analiz":
    col_sel, col_tf, col_btn = st.columns([2, 1, 1])
    active_sym = col_sel.selectbox("Sembol Seçin", fetch_symbols(), 
                                 index=fetch_symbols().index(st.session_state["active_symbol"]) if st.session_state["active_symbol"] in fetch_symbols() else 0)
    tf = col_tf.selectbox("Zaman Dilimi", ["1H", "1A", "3A", "1Y", "5Y"], index=1)
    
    if col_btn.button("Analiz Et", type="primary", use_container_width=True):
        st.session_state["analyze_clicked"] = True
        st.session_state["active_symbol"] = active_sym
        st.cache_data.clear() # Force fetch new analysis
        
    if not st.session_state["analyze_clicked"]:
        st.info("Bir sembol seçin ve Analiz Et'e tıklayın")
    else:
        # Fetch data
        with st.spinner("Analiz ediliyor..."):
            res = fetch_full_analysis(active_sym, tf)
            if res:
                data = res["analysis"]
                prices = res["prices"]
                diff = res["diff"]
                
                if data:
                    st.header(f"{active_sym} Analiz Raporu")
                    
                    # 1. Price Chart
                    plot_candlestick(prices)
                    
                    # 2. Metrics Row
                    m_cols = st.columns(5)
                    curr_price = prices['close'][-1] if prices and prices.get('close') else "N/A"
                    m_cols[0].metric("Fiyat", f"{curr_price:.2f}" if isinstance(curr_price, float) else curr_price)
                    m_cols[1].metric("RSI", "64.2") # Mock or fetch
                    m_cols[2].metric("Sentiment", data.get("sentiment_trend", "Neutral").capitalize())
                    m_cols[3].metric("İnanç", f"{data.get('conviction_level', 0)}/10")
                    m_cols[4].metric("Hedef Fiyat", f"{data.get('analyst_target_mean', 'N/A')}")
                    
                    # 3. AI Summary
                    st.info(data.get("executive_summary", ""))
                    
                    # 4. Catalysts & Risks
                    c_left, c_right = st.columns(2)
                    with c_left:
                        st.subheader("🚀 Katalizörler")
                        for c in data.get("key_catalysts", []): st.markdown(f"- {c}")
                    with c_right:
                        st.subheader("⚠️ Riskler")
                        for r in data.get("risks", []): st.markdown(f"- {r}")
                    
                    # 5. Blind Spots
                    st.subheader("🔍 Gözden Kaçanlar")
                    for m in data.get("what_i_might_be_missing", []):
                        st.warning(m)
                    
                    # 6. Ne Değişti?
                    if diff:
                        st.markdown(f"""
                        <div style="background-color: rgba(0, 255, 204, 0.05); border: 1px solid #00ffcc; padding: 20px; border-radius: 10px; margin: 20px 0;">
                            <h3 style="color: #00ffcc;">🔄 Ne Değişti?</h3>
                            <p>{diff['narrative']}</p>
                            <b>İnanç Değişimi:</b> {diff['conviction_change']:+d} ({diff['days_between']} gün önceye göre)
                        </div>
                        """, unsafe_allow_html=True)

                    # 7. Analyst Data
                    if data.get("analyst_target_mean"):
                        st.subheader("🎯 Analist Verileri")
                        st.write(f"Konsensüs: **{data.get('recommendation_consensus', 'N/A').upper()}**")
                        prog = st.progress(0.7) # buy % mock
                    
                    # 8. History
                    with st.expander("Geçmiş Raporlar"):
                        st.write("Son 5 analiz burada listelenir.")

# ═══════════════════════════════════════════════════
# PAGE: TAVSİYELER
# ═══════════════════════════════════════════════════
elif st.session_state["page"] == "🎯 Tavsiyeler":
    st.title("Piyasa Taraması")
    
    with st.container():
        st.markdown("""
        <div style="background: rgba(255,255,255,0.05); padding: 20px; border-radius: 8px;">
            <h4>Tarama Başlat</h4>
            <p>Bu tarama BIST30 ve İzleme Listenizdeki toplam 45 sembolü analiz eder, 2-4 dakika sürer.</p>
        </div>
        """, unsafe_allow_html=True)
        
        scan_data = fetch_latest_scan()
        if scan_data:
            st.caption(f"Son tarama: {scan_data['scan_timestamp'][:16]} — {scan_data['symbols_scanned']} sembol tarandı")
        
        if st.button("Tarama Başlat", type="primary"):
            with st.spinner("Evren taranıyor..."):
                res = requests.post(f"{API_URL}/scan", json={"watchlist": fetch_symbols()})
                if res.status_code == 200:
                    st.rerun()

    if scan_data:
        t1, t2, t3 = st.tabs(["🏆 En İyi Fırsatlar", "📋 Watchlist", "🛑 Kaçınılacaklar"])
        
        with t1:
            for rec in scan_data.get('top_opportunities', []):
                with st.container():
                    st.subheader(f"{rec['symbol']} — {rec['recommendation'].upper()}")
                    st.info(rec['primary_thesis'])
                    st.markdown(f'<div class="devils-advocate"><b>Şeytanın Avukatı:</b><br>{rec["counter_thesis"]}</div>', unsafe_allow_html=True)
                    st.divider()
        
        with t2:
            st.write("İzleme listenizdeki güncel görünümler.")
        
        with t3:
            st.table(scan_data.get('symbols_to_avoid', []))

# ═══════════════════════════════════════════════════
# PAGE: SORU SOR
# ═══════════════════════════════════════════════════
elif st.session_state["page"] == "💬 Soru Sor":
    st.title("MyMind'a Sor")
    
    col_sym, col_hist = st.columns([1, 1])
    target = col_sym.selectbox("Sembol (Opsiyonel)", fetch_symbols(), index=0)
    use_hist = col_hist.toggle("Geçmiş raporları kullan", value=True)
    
    q = st.text_area("Yatırımlarınız hakkında bir şey sorun...", height=100)
    if st.button("Sor", type="primary"):
        with st.spinner("Düşünülüyor..."):
            endpoint = "/ask-with-history" if use_hist else "/ask"
            res = requests.post(f"{API_URL}{endpoint}", json={"symbol": target, "question": q, "lang": "tr"})
            if res.status_code == 200:
                st.markdown(res.json().get("answer", ""))
            else:
                st.error("Bir hata oluştu.")

# ═══════════════════════════════════════════════════
# PAGE: RAPORLAR
# ═══════════════════════════════════════════════════
elif st.session_state["page"] == "📋 Raporlar":
    st.title("Rapor Arşivi")
    
    col_filt, col_search = st.columns([1, 2])
    sym_f = col_filt.selectbox("Sembol Filtresi", ["Tümü"] + fetch_symbols())
    q_search = col_search.text_input("Rapor içeriğinde ara")
    
    st.write("---")
    
    reports = []
    if sym_f == "Tümü":
        # Just an example, maybe fetch for last few symbols
        for s in symbols[:3]:
            r_list = requests.get(f"{API_URL}/reports/{s}?limit=5").json()
            reports.extend(r_list)
    else:
        reports = requests.get(f"{API_URL}/reports/{sym_f}?limit=10").json()
        
    if reports:
        for r in sorted(reports, key=lambda x: x['created_at'], reverse=True):
            with st.expander(f"{r['created_at'][:10]} | {r['symbol']} | Conviction: {r['conviction_level']}/10"):
                st.markdown(f"**Özet:** {r['llm_summary']}")
                st.json(r)
    else:
        st.info("Eşleşen rapor bulunamadı.")
