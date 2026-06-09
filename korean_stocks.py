import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

# 페이지 설정
st.set_page_config(
    page_title="국내 주식 대시보드",
    page_icon="📈",
    layout="wide",
)

# 국내 주식 10개 (코스피/코스닥 대표 종목)
STOCKS = {
    "삼성전자": "005930.KS",
    "SK하이닉스": "000660.KS",
    "LG에너지솔루션": "373220.KS",
    "삼성바이오로직스": "207940.KS",
    "현대차": "005380.KS",
    "셀트리온": "068270.KS",
    "POSCO홀딩스": "005490.KS",
    "카카오": "035720.KS",
    "네이버": "035420.KS",
    "기아": "000270.KS",
}

PERIOD_OPTIONS = {
    "1개월": "1mo",
    "3개월": "3mo",
    "6개월": "6mo",
    "1년": "1y",
    "2년": "2y",
}

st.title("📈 국내 주식 대시보드")
st.caption("yfinance 기반 · 코스피 대표 10종목")

# 사이드바
with st.sidebar:
    st.header("설정")
    selected_names = st.multiselect(
        "종목 선택",
        options=list(STOCKS.keys()),
        default=list(STOCKS.keys()),
    )
    period_label = st.selectbox("조회 기간", list(PERIOD_OPTIONS.keys()), index=2)
    period = PERIOD_OPTIONS[period_label]
    chart_type = st.radio("차트 유형", ["캔들스틱", "라인"])
    st.divider()
    refresh = st.button("새로고침", use_container_width=True)

if not selected_names:
    st.warning("종목을 하나 이상 선택해 주세요.")
    st.stop()

selected_tickers = {name: STOCKS[name] for name in selected_names}


@st.cache_data(ttl=300, show_spinner=False)
def fetch_all(tickers: dict, period: str):
    results = {}
    for name, ticker in tickers.items():
        try:
            df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
            if df is not None and not df.empty:
                # MultiIndex 컬럼 처리
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                results[name] = df
        except Exception:
            pass
    return results


@st.cache_data(ttl=300, show_spinner=False)
def fetch_info(tickers: dict):
    info_list = []
    for name, ticker in tickers.items():
        try:
            t = yf.Ticker(ticker)
            info = t.fast_info
            info_list.append({
                "종목명": name,
                "티커": ticker,
                "현재가": getattr(info, "last_price", None),
                "전일종가": getattr(info, "previous_close", None),
                "시가총액(억)": round(getattr(info, "market_cap", 0) / 1e8) if getattr(info, "market_cap", None) else None,
                "52주최고": getattr(info, "year_high", None),
                "52주최저": getattr(info, "year_low", None),
            })
        except Exception:
            info_list.append({"종목명": name, "티커": ticker})
    return pd.DataFrame(info_list)


if refresh:
    st.cache_data.clear()

with st.spinner("데이터 수집 중..."):
    stock_data = fetch_all(selected_tickers, period)
    info_df = fetch_info(selected_tickers)

# 등락률 계산
def calc_change(df):
    if df is None or df.empty or len(df) < 2:
        return None, None
    latest = float(df["Close"].iloc[-1])
    prev = float(df["Close"].iloc[-2])
    change_pct = (latest - prev) / prev * 100
    return latest, change_pct


# ── 요약 카드 ──────────────────────────────────────────────
st.subheader("현재가 요약")
cols = st.columns(5)
for i, name in enumerate(selected_names):
    df = stock_data.get(name)
    latest, change_pct = calc_change(df)
    with cols[i % 5]:
        if latest is not None:
            delta_str = f"{change_pct:+.2f}%"
            st.metric(label=name, value=f"{latest:,.0f}원", delta=delta_str)
        else:
            st.metric(label=name, value="N/A")

st.divider()

# ── 종목 정보 테이블 ────────────────────────────────────────
with st.expander("종목 기본 정보", expanded=False):
    display_df = info_df.copy()
    for col in ["현재가", "전일종가", "52주최고", "52주최저"]:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(
                lambda x: f"{x:,.0f}원" if pd.notna(x) else "-"
            )
    if "시가총액(억)" in display_df.columns:
        display_df["시가총액(억)"] = display_df["시가총액(억)"].apply(
            lambda x: f"{x:,}억" if pd.notna(x) else "-"
        )
    st.dataframe(display_df.set_index("종목명"), use_container_width=True)

# ── 개별 종목 차트 ──────────────────────────────────────────
st.subheader("종목별 주가 차트")
tabs = st.tabs(selected_names)

for tab, name in zip(tabs, selected_names):
    df = stock_data.get(name)
    with tab:
        if df is None or df.empty:
            st.error(f"{name} 데이터를 불러올 수 없습니다.")
            continue

        col1, col2 = st.columns([3, 1])

        with col1:
            if chart_type == "캔들스틱":
                fig = go.Figure(
                    go.Candlestick(
                        x=df.index,
                        open=df["Open"],
                        high=df["High"],
                        low=df["Low"],
                        close=df["Close"],
                        increasing_line_color="#FF4B4B",
                        decreasing_line_color="#4B94FF",
                        name=name,
                    )
                )
            else:
                fig = px.line(df, x=df.index, y="Close", labels={"Close": "종가(원)", "index": "날짜"})
                fig.update_traces(line_color="#FF4B4B")

            fig.update_layout(
                title=f"{name} ({period_label})",
                xaxis_title="날짜",
                yaxis_title="주가 (원)",
                height=400,
                xaxis_rangeslider_visible=False,
                margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown("**거래량**")
            vol_fig = px.bar(
                df.tail(60),
                x=df.tail(60).index,
                y="Volume",
                labels={"Volume": "거래량", "index": "날짜"},
                color_discrete_sequence=["#888888"],
            )
            vol_fig.update_layout(height=200, margin=dict(l=5, r=5, t=10, b=5), showlegend=False)
            st.plotly_chart(vol_fig, use_container_width=True)

            st.markdown("**최근 5일 종가**")
            recent = df[["Close", "Volume"]].tail(5).copy()
            recent.index = recent.index.strftime("%m/%d")
            recent.columns = ["종가(원)", "거래량"]
            recent["종가(원)"] = recent["종가(원)"].apply(lambda x: f"{x:,.0f}")
            recent["거래량"] = recent["거래량"].apply(lambda x: f"{x:,.0f}")
            st.dataframe(recent, use_container_width=True)

st.divider()

# ── 수익률 비교 ─────────────────────────────────────────────
st.subheader("기간 수익률 비교")
returns = {}
for name in selected_names:
    df = stock_data.get(name)
    if df is not None and not df.empty and len(df) >= 2:
        start = float(df["Close"].iloc[0])
        end = float(df["Close"].iloc[-1])
        returns[name] = round((end - start) / start * 100, 2)

if returns:
    ret_df = pd.DataFrame.from_dict(returns, orient="index", columns=["수익률(%)"])
    ret_df = ret_df.sort_values("수익률(%)", ascending=True)
    colors = ["#FF4B4B" if v >= 0 else "#4B94FF" for v in ret_df["수익률(%)"]]
    fig_ret = go.Figure(
        go.Bar(
            x=ret_df["수익률(%)"],
            y=ret_df.index,
            orientation="h",
            marker_color=colors,
            text=[f"{v:+.2f}%" for v in ret_df["수익률(%)"]],
            textposition="outside",
        )
    )
    fig_ret.update_layout(
        title=f"{period_label} 기간 수익률",
        xaxis_title="수익률 (%)",
        height=max(300, len(returns) * 45),
        margin=dict(l=10, r=60, t=40, b=10),
    )
    st.plotly_chart(fig_ret, use_container_width=True)

# ── 정규화 주가 비교 ────────────────────────────────────────
st.subheader("정규화 주가 비교 (기준일=100)")
norm_fig = go.Figure()
for name in selected_names:
    df = stock_data.get(name)
    if df is not None and not df.empty:
        normalized = df["Close"] / float(df["Close"].iloc[0]) * 100
        norm_fig.add_trace(go.Scatter(x=df.index, y=normalized, mode="lines", name=name))

norm_fig.update_layout(
    xaxis_title="날짜",
    yaxis_title="지수 (시작=100)",
    height=420,
    margin=dict(l=10, r=10, t=20, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
)
st.plotly_chart(norm_fig, use_container_width=True)

st.caption(f"데이터 출처: Yahoo Finance  |  마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
