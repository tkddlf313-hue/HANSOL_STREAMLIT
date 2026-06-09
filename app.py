import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

# Set page config
st.set_page_config(
    page_title="K-Stock Dashboard | 국내 10대 기업 주식 분석",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Premium Styling
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Noto+Sans+KR:wght@300;400;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', 'Noto Sans KR', sans-serif;
    }
    
    /* Main Background & Text Color */
    .stApp {
        background: linear-gradient(135deg, #0e1117 0%, #161a24 100%);
        color: #e2e8f0;
    }
    
    /* Metric container styling */
    div[data-testid="stMetric"] {
        background: rgba(30, 41, 59, 0.45);
        border: 1px solid rgba(255, 255, 255, 0.08);
        padding: 1.5rem;
        border-radius: 16px;
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.2);
        backdrop-filter: blur(5px);
        transition: transform 0.3s ease, border-color 0.3s ease;
    }
    
    div[data-testid="stMetric"]:hover {
        transform: translateY(-4px);
        border-color: rgba(99, 102, 241, 0.4);
    }
    
    /* Custom headers */
    .main-title {
        font-size: 3rem;
        font-weight: 800;
        background: linear-gradient(90deg, #6366f1 0%, #a855f7 50%, #ec4899 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
        letter-spacing: -0.05em;
    }
    
    .subtitle {
        font-size: 1.1rem;
        color: #94a3b8;
        margin-bottom: 2rem;
        font-weight: 300;
    }
    
    /* Sidebar customization */
    section[data-testid="stSidebar"] {
        background-color: #0b0d13 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    /* Tab formatting */
    button[data-baseweb="tab"] {
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        color: #94a3b8 !important;
        transition: all 0.3s;
    }
    
    button[aria-selected="true"] {
        color: #6366f1 !important;
        border-bottom-color: #6366f1 !important;
    }
    
    /* Card Container */
    .card {
        background: rgba(30, 41, 59, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# Define the Top 10 Stocks
STOCKS = {
    "삼성전자": "005930.KS",
    "SK하이닉스": "000660.KS",
    "LG에너지솔루션": "373220.KS",
    "삼성바이오로직스": "207940.KS",
    "현대자동차": "005380.KS",
    "기아": "000270.KS",
    "셀트리온": "068270.KS",
    "KB금융": "105560.KS",
    "POSCO홀딩스": "005490.KS",
    "NAVER": "035420.KS"
}

# Sidebar inputs
st.sidebar.markdown("<h2 style='color: #6366f1; font-weight: 700; margin-bottom: 1rem;'>⚙️ 대시보드 설정</h2>", unsafe_allow_html=True)

selected_stock_name = st.sidebar.selectbox(
    "📊 분석할 종목 선택",
    list(STOCKS.keys()),
    index=0
)
ticker = STOCKS[selected_stock_name]

# Date range selector
st.sidebar.markdown("---")
st.sidebar.markdown("<p style='font-weight: 600; color: #e2e8f0; margin-bottom: 0.5rem;'>📅 조회 기간</p>", unsafe_allow_html=True)
date_options = {
    "1개월": 30,
    "3개월": 90,
    "6개월": 180,
    "1년": 365,
    "3년": 365 * 3,
    "5년": 365 * 5
}
selected_period = st.sidebar.selectbox("기간 설정", list(date_options.keys()), index=2)
days_to_subtract = date_options[selected_period]

start_date = datetime.today() - timedelta(days=days_to_subtract)
end_date = datetime.today()

# Function to fetch stock data helper
@st.cache_data(ttl=600)
def load_stock_data(ticker, start, end):
    try:
        data = yf.download(ticker, start=start, end=end)
        if data.empty:
            return None
        # Reset index to make Date a column
        data = data.reset_index()
        return data
    except Exception as e:
        return None

@st.cache_data(ttl=3600)
def load_stock_info(ticker):
    try:
        info = yf.Ticker(ticker).info
        return info
    except:
        return {}

# Load main data
data = load_stock_data(ticker, start_date, end_date)
info = load_stock_info(ticker)

# Header
st.markdown(f"<h1 class='main-title'>{selected_stock_name} ({ticker})</h1>", unsafe_allow_html=True)
st.markdown("<p class='subtitle'>국내 Top 10 시가총액 기업 실시간 주가 데이터 & 인터랙티브 시각화 대시보드</p>", unsafe_allow_html=True)

if data is not None and not data.empty:
    # Latest statistics
    latest_row = data.iloc[-1]
    prev_row = data.iloc[-2] if len(data) > 1 else latest_row
    
    current_price = float(latest_row['Close'])
    prev_price = float(prev_row['Close'])
    price_change = current_price - prev_price
    price_change_percent = (price_change / prev_price) * 100
    
    # 3-Column Key Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="현재가 (종가 기준)",
            value=f"{current_price:,.0f} 원",
            delta=f"{price_change:,.0f} 원 ({price_change_percent:+.2f}%)"
        )
        
    with col2:
        high_price = float(latest_row['High'])
        st.metric(
            label="오늘 고가",
            value=f"{high_price:,.0f} 원",
            delta=f"저가 대비 {(high_price - float(latest_row['Low'])):+,.0f} 원",
            delta_color="normal"
        )
        
    with col3:
        volume = float(latest_row['Volume'])
        st.metric(
            label="거래량",
            value=f"{volume:,.0f} 주",
            delta=f"전일 대비 {volume - float(prev_row['Volume']):+,.0f} 주",
            delta_color="off"
        )
        
    with col4:
        # Market Cap formatting
        market_cap = info.get('marketCap', 0)
        if market_cap > 0:
            market_cap_trillion = market_cap / 1_000_000_000_000
            market_cap_str = f"{market_cap_trillion:,.1f} 조원"
        else:
            market_cap_str = "정보 없음"
        
        st.metric(
            label="시가총액",
            value=market_cap_str,
            delta="코스피 기준"
        )

    # Main Tabs
    tab1, tab2, tab3 = st.tabs(["📈 차트 분석", "🔍 상세 재무 및 기업 정보", "⚖️ 10대 기업 비교"])
    
    with tab1:
        # Technical Indicator Controls
        st.markdown("<h3 style='color: #a855f7; font-weight: 600;'>주가 추이 및 지표 분석</h3>", unsafe_allow_html=True)
        col_ctrl1, col_ctrl2 = st.columns(2)
        with col_ctrl1:
            chart_type = st.radio("차트 종류 선택", ["봉 차트 (Candlestick)", "선 차트 (Line)"], horizontal=True)
        with col_ctrl2:
            show_ma = st.multiselect("이동평균선(MA) 추가", ["MA 20", "MA 50", "MA 120"], default=["MA 20", "MA 50"])
            
        # Add MAs to dataframe
        df_chart = data.copy()
        if "MA 20" in show_ma:
            df_chart['MA20'] = df_chart['Close'].rolling(window=20).mean()
        if "MA 50" in show_ma:
            df_chart['MA50'] = df_chart['Close'].rolling(window=50).mean()
        if "MA 120" in show_ma:
            df_chart['MA120'] = df_chart['Close'].rolling(window=120).mean()
            
        fig = go.Figure()
        
        # Draw base stock chart
        if chart_type == "봉 차트 (Candlestick)":
            fig.add_trace(go.Candlestick(
                x=df_chart['Date'],
                open=df_chart['Open'],
                high=df_chart['High'],
                low=df_chart['Low'],
                close=df_chart['Close'],
                name="주가",
                increasing_line_color='#ef4444', # Red for Korea stock increase
                decreasing_line_color='#3b82f6'  # Blue for decrease
            ))
        else:
            fig.add_trace(go.Scatter(
                x=df_chart['Date'],
                y=df_chart['Close'],
                mode='lines',
                name="종가",
                line=dict(color='#6366f1', width=3)
            ))
            
        # Add MAs to Plotly figure
        ma_colors = {"MA20": "#10b981", "MA50": "#f59e0b", "MA120": "#a855f7"}
        for ma in ["MA20", "MA50", "MA120"]:
            if ma in df_chart.columns:
                fig.add_trace(go.Scatter(
                    x=df_chart['Date'],
                    y=df_chart[ma],
                    mode='lines',
                    name=ma.replace('MA', '이동평균선 '),
                    line=dict(width=1.5, color=ma_colors[ma])
                ))
                
        fig.update_layout(
            template="plotly_dark",
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            xaxis_rangeslider_visible=False,
            height=500,
            margin=dict(l=10, r=10, t=20, b=20),
            xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
            yaxis=dict(gridcolor='rgba(255,255,255,0.05)', tickformat=",.0f")
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Volume Chart
        volume_fig = px.bar(
            df_chart, 
            x='Date', 
            y='Volume', 
            title="거래량 추이",
            color_discrete_sequence=['#475569']
        )
        volume_fig.update_layout(
            template="plotly_dark",
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            height=200,
            margin=dict(l=10, r=10, t=40, b=10),
            xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
            yaxis=dict(gridcolor='rgba(255,255,255,0.05)', tickformat=",.0f")
        )
        st.plotly_chart(volume_fig, use_container_width=True)

    with tab2:
        st.markdown("<h3 style='color: #ec4899; font-weight: 600;'>기업 기본 정보</h3>", unsafe_allow_html=True)
        
        if info:
            # Display summary description
            summary = info.get('longBusinessSummary', '설명 정보가 없습니다.')
            st.markdown(f"<div class='card'>{summary}</div>", unsafe_allow_html=True)
            
            # Key statistics in grid
            col_info1, col_info2 = st.columns(2)
            
            with col_info1:
                stats_left = {
                    "기업 영문명": info.get('longName', 'N/A'),
                    "웹사이트": info.get('website', 'N/A'),
                    "업종 (Sector)": info.get('sector', 'N/A'),
                    "주요 산업 (Industry)": info.get('industry', 'N/A'),
                }
                df_left = pd.DataFrame(list(stats_left.items()), columns=["항목", "내용"])
                st.dataframe(df_left, hide_index=True, use_container_width=True)
                
            with col_info2:
                stats_right = {
                    "PER (Trailing PE)": f"{info.get('trailingPE', 0):.2f}" if info.get('trailingPE') else 'N/A',
                    "PBR (Price to Book)": f"{info.get('priceToBook', 0):.2f}" if info.get('priceToBook') else 'N/A',
                    "52주 최고가": f"{info.get('fiftyTwoWeekHigh', 0):,.0f} 원" if info.get('fiftyTwoWeekHigh') else 'N/A',
                    "52주 최저가": f"{info.get('fiftyTwoWeekLow', 0):,.0f} 원" if info.get('fiftyTwoWeekLow') else 'N/A',
                }
                df_right = pd.DataFrame(list(stats_right.items()), columns=["항목", "내용"])
                st.dataframe(df_right, hide_index=True, use_container_width=True)
        else:
            st.warning("이 종목에 대한 실시간 기업 상세 프로필 정보를 불러올 수 없습니다. (API 한계 또는 인터넷 미연결)")

    with tab3:
        st.markdown("<h3 style='color: #6366f1; font-weight: 600;'>국내 10대 기업 주가 동향 비교 (최근 1개월 기준)</h3>", unsafe_allow_html=True)
        
        # Load last 30 days of all stocks to compare performance
        compare_data = []
        comp_start = datetime.today() - timedelta(days=30)
        
        with st.spinner("비교 데이터 로딩 중..."):
            for name, ticker_code in STOCKS.items():
                hist = load_stock_data(ticker_code, comp_start, end_date)
                if hist is not None and not hist.empty:
                    # Calculate cumulative return starting from 0% at the start of period
                    first_price = float(hist.iloc[0]['Close'])
                    hist = hist.copy()
                    hist['StockName'] = name
                    # Cumulative Return = (Price / First Price - 1) * 100
                    hist['CumulativeReturn'] = (hist['Close'] / first_price - 1) * 100
                    compare_data.append(hist[['Date', 'StockName', 'CumulativeReturn', 'Close']])
                    
        if compare_data:
            df_compare = pd.concat(compare_data)
            
            # Interactive Line chart of cumulative returns
            comp_fig = px.line(
                df_compare,
                x='Date',
                y='CumulativeReturn',
                color='StockName',
                title="10대 기업 최근 1개월 누적 수익률 비교 (%)",
                labels={'CumulativeReturn': '누적 수익률 (%)', 'Date': '날짜', 'StockName': '종목명'}
            )
            comp_fig.update_layout(
                template="plotly_dark",
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                height=450,
                yaxis=dict(ticksuffix="%", gridcolor='rgba(255,255,255,0.05)'),
                xaxis=dict(gridcolor='rgba(255,255,255,0.05)')
            )
            st.plotly_chart(comp_fig, use_container_width=True)
            
            # Summary Table
            latest_returns = []
            for name in STOCKS.keys():
                sub = df_compare[df_compare['StockName'] == name]
                if not sub.empty:
                    latest_val = sub.iloc[-1]
                    latest_returns.append({
                        "종목명": name,
                        "현재 주가": f"{float(latest_val['Close']):,.0f} 원",
                        "최근 1개월 수익률": f"{float(latest_val['CumulativeReturn']):+.2f}%"
                    })
            df_returns = pd.DataFrame(latest_returns)
            st.markdown("<p style='font-weight: 600;'>📊 기업별 요약 표</p>", unsafe_allow_html=True)
            st.dataframe(df_returns, hide_index=True, use_container_width=True)
        else:
            st.error("비교 데이터를 불러올 수 없습니다.")

else:
    st.error(f"{selected_stock_name} ({ticker}) 데이터를 가져올 수 없습니다. 인터넷 상태 또는 야후 파이낸스 서비스 상태를 확인해 주세요.")
