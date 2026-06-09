"""
📚 도서 영수증 자동 정리 에이전트
Streamlit 기반 웹 애플리케이션
"""

import os
import io
import logging
import time
import tempfile
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── 페이지 설정 ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="📚 도서 영수증 에이전트",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-title {
        font-size: 2rem;
        font-weight: 800;
        color: #1e40af;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        color: #64748b;
        font-size: 0.95rem;
        margin-bottom: 1.5rem;
    }
    .stat-box {
        background: #eff6ff;
        border-left: 4px solid #2563eb;
        border-radius: 8px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.5rem;
    }
    .stat-box .label { color: #475569; font-size: 0.85rem; }
    .stat-box .value { color: #1e40af; font-size: 1.6rem; font-weight: 700; }
    .log-success { color: #16a34a; }
    .log-error   { color: #dc2626; }
    .log-warning { color: #d97706; }
    .step-badge {
        display: inline-block;
        background: #dbeafe;
        color: #1d4ed8;
        border-radius: 999px;
        padding: 2px 10px;
        font-size: 0.78rem;
        font-weight: 600;
        margin-right: 6px;
    }
    div[data-testid="stExpander"] > div > div { padding: 0.5rem 0; }
</style>
""", unsafe_allow_html=True)


# ── session_state 초기화 ──────────────────────────────────────────────────────
def _init_state():
    defaults = {
        "results": [],        # list[ParsedReceipt]
        "failed": [],         # list[dict]
        "df": None,           # pd.DataFrame
        "excel_bytes": None,  # bytes
        "excel_name": "",
        "logs": [],           # list[dict]
        "processed": False,
        "processing": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()


# ── 사이드바 ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ 설정")
    api_key = st.text_input(
        "OpenAI API Key",
        value=os.getenv("OPENAI_API_KEY", ""),
        type="password",
        help="sk-... 형식의 OpenAI API 키를 입력하세요.",
    )

    st.markdown("---")
    st.markdown("### 처리 옵션")
    ocr_threshold = st.slider(
        "OCR 신뢰도 임계값",
        min_value=0.0, max_value=1.0, value=0.50, step=0.05,
        help="이 값 미만이면 OCR 재시도. 실제 영수증 사진은 0.3~0.5 권장.",
    )
    classify_threshold = st.slider(
        "분류 신뢰도 임계값",
        min_value=0.0, max_value=1.0, value=0.70, step=0.05,
        help="이 값 미만이면 '미확인' 태그 처리.",
    )
    model_name = st.selectbox(
        "LLM 모델",
        ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
        index=0,
    )

    st.markdown("---")
    st.markdown("### 도움말")
    with st.expander("지원 형식 / 제한"):
        st.markdown("""
- **형식**: JPG, PNG, WEBP, PDF
- **최대 크기**: 20MB / 파일
- **최대 파일 수**: 50개
- **OCR 언어**: 한국어 + 영어
        """)
    with st.expander("처리 단계"):
        st.markdown("""
1. 파일 검증
2. 이미지 전처리 (회전·노이즈·이진화)
3. OCR 텍스트 추출
4. GPT 영수증 파싱
5. 도서 장르 분류
6. 엑셀 3시트 생성
        """)


# ── 메인 타이틀 ───────────────────────────────────────────────────────────────
st.markdown('<div class="main-title">📚 도서 영수증 자동 정리 에이전트</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">영수증 이미지/PDF를 업로드하면 도서 목록 엑셀 파일을 자동으로 생성합니다.</div>', unsafe_allow_html=True)

# ── 탭 ───────────────────────────────────────────────────────────────────────
tab_upload, tab_result, tab_log = st.tabs(["📤 파일 업로드", "📊 결과 확인", "🗒️ 처리 로그"])


# ═══════════════════════════════════════════════════════════════════════
# TAB 1: 파일 업로드
# ═══════════════════════════════════════════════════════════════════════
with tab_upload:
    st.markdown("### 영수증 파일 업로드")

    uploaded_files = st.file_uploader(
        "파일을 선택하거나 드래그하세요 (최대 50개)",
        type=["jpg", "jpeg", "png", "webp", "pdf"],
        accept_multiple_files=True,
        key="file_uploader",
    )

    if uploaded_files:
        st.info(f"**{len(uploaded_files)}개** 파일이 선택되었습니다.")
        with st.expander("선택된 파일 목록"):
            for f in uploaded_files:
                size_kb = len(f.getbuffer()) / 1024
                st.write(f"- `{f.name}` ({size_kb:.1f} KB)")

    col_btn, col_reset = st.columns([1, 5])
    with col_btn:
        start_btn = st.button(
            "🚀 처리 시작",
            type="primary",
            disabled=not uploaded_files or not api_key,
            use_container_width=True,
        )
    with col_reset:
        if st.button("🔄 초기화", use_container_width=False):
            for k in ["results", "failed", "df", "excel_bytes", "excel_name", "logs", "processed", "processing"]:
                st.session_state[k] = [] if k in ("results", "failed", "logs") else (None if k in ("df", "excel_bytes") else ("" if k == "excel_name" else False))
            st.rerun()

    if not api_key:
        st.warning("⚠️ 사이드바에서 OpenAI API Key를 먼저 입력하세요.")

    # ── 처리 실행 ────────────────────────────────────────────────────────
    if start_btn and uploaded_files and api_key:
        from agent.models import BookItem, ParsedReceipt, BatchResult
        from modules.validator import validate_format, validate_size, validate_quality
        from modules.preprocessor import preprocess_image, pdf_to_images
        from modules.ocr import run_ocr
        from modules.llm_parser import parse_receipt_text
        from modules.classifier import classify_book, GENRE_CATEGORIES
        from modules.merger import merge_results
        from modules.excel_generator import generate_excel
        from utils.session import generate_session_id, create_temp_dir, cleanup_temp_dir, save_uploaded_file
        from errors.error_codes import get_error

        # 파일 수 제한
        if len(uploaded_files) > 50:
            st.error(get_error("ERR-13").message_ko)
            st.stop()

        st.session_state["results"] = []
        st.session_state["failed"] = []
        st.session_state["logs"] = []
        st.session_state["processed"] = False
        st.session_state["excel_bytes"] = None

        session_id = generate_session_id()
        temp_dir = create_temp_dir()
        pre_dir = os.path.join(temp_dir, "preprocessed")
        out_dir = os.path.join(temp_dir, "output")
        os.makedirs(pre_dir, exist_ok=True)
        os.makedirs(out_dir, exist_ok=True)

        start_ts = time.time()

        progress_bar = st.progress(0, text="처리를 시작합니다...")
        status_placeholder = st.empty()

        def log(filename, step, message, level="info"):
            icon = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}.get(level, "ℹ️")
            st.session_state["logs"].append({
                "file": filename,
                "step": step,
                "message": message,
                "level": level,
                "icon": icon,
            })

        total = len(uploaded_files)

        for idx, uploaded_file in enumerate(uploaded_files):
            fname = uploaded_file.name
            pct = int((idx / total) * 100)
            progress_bar.progress(pct, text=f"처리 중: {fname} ({idx+1}/{total})")
            status_placeholder.info(f"**{fname}** 처리 중...")

            try:
                # ── 1. 파일 저장 ─────────────────────────────────────────
                raw_path = save_uploaded_file(uploaded_file, temp_dir)
                file_size = os.path.getsize(raw_path)
                ext = Path(fname).suffix.lstrip(".").lower()
                log(fname, "검증", f"파일 저장 완료 ({file_size/1024:.1f} KB)")

                # ── 2. 형식 검증 ──────────────────────────────────────────
                if not validate_format(fname):
                    raise ValueError(get_error("ERR-01").message_ko)
                if not validate_size(file_size):
                    raise ValueError(get_error("ERR-02").message_ko)
                log(fname, "검증", "형식·크기 검증 통과", "success")

                # ── 3. 이미지 목록 구성 (PDF → 페이지별) ────────────────────
                if ext == "pdf":
                    log(fname, "전처리", "PDF → 이미지 변환 중...")
                    try:
                        image_paths = pdf_to_images(raw_path, pre_dir)
                        log(fname, "전처리", f"PDF {len(image_paths)}페이지 변환 완료", "success")
                    except RuntimeError as e:
                        log(fname, "전처리", f"PDF 변환 실패: {e}", "error")
                        raise
                else:
                    # 품질 검사
                    ok, err_code = validate_quality(raw_path)
                    if not ok:
                        log(fname, "검증", get_error(err_code).message_ko, "warning")
                    image_paths = [raw_path]

                # ── 4. 전처리 + OCR ───────────────────────────────────────
                all_text_parts = []
                total_confidence = 0.0

                for img_path in image_paths:
                    pre_out = os.path.join(pre_dir, f"pre_{os.path.basename(img_path)}")
                    try:
                        pre_path = preprocess_image(img_path, pre_out)
                        log(fname, "전처리", f"전처리 완료: {os.path.basename(img_path)}", "success")
                    except RuntimeError as e:
                        log(fname, "전처리", f"전처리 실패, 원본으로 OCR 시도: {e}", "warning")
                        pre_path = img_path

                    ocr_text = ""
                    ocr_conf = 0.0
                    ocr_retry = 0
                    max_ocr_retry = 3

                    while ocr_retry < max_ocr_retry:
                        try:
                            ocr_text, ocr_conf = run_ocr(pre_path)
                            break
                        except RuntimeError as e:
                            ocr_retry += 1
                            log(fname, "OCR", f"OCR 실패 (시도 {ocr_retry}/{max_ocr_retry}): {e}", "warning")
                            if ocr_retry >= max_ocr_retry:
                                raise

                    if ocr_conf < ocr_threshold:
                        log(fname, "OCR", f"OCR 신뢰도 낮음 ({ocr_conf:.1%}) — 계속 진행", "warning")
                    else:
                        log(fname, "OCR", f"OCR 완료 (신뢰도 {ocr_conf:.1%})", "success")

                    all_text_parts.append(ocr_text)
                    total_confidence += ocr_conf

                combined_text = "\n\n".join(all_text_parts)
                avg_confidence = total_confidence / len(image_paths) if image_paths else 0.0

                if not combined_text.strip():
                    raise ValueError("OCR 결과가 비어있습니다. 이미지를 확인하세요.")

                # ── 5. LLM 파싱 ───────────────────────────────────────────
                log(fname, "파싱", "GPT로 도서 정보 추출 중...")
                parsed = parse_receipt_text(combined_text, api_key, model=model_name)

                books_raw = parsed.get("books", [])
                if not books_raw:
                    raise ValueError(get_error("ERR-09").message_ko)
                log(fname, "파싱", f"도서 {len(books_raw)}권 추출 완료", "success")

                # ── 6. 도서 분류 ───────────────────────────────────────────
                log(fname, "분류", "장르 분류 중...")
                book_items = []
                for b in books_raw:
                    title = b.get("title", "")
                    price = b.get("price", 0)
                    if not title:
                        continue
                    if price <= 0:
                        log(fname, "분류", f"'{title}' 가격 이상 (price={price}) — 0으로 처리", "warning")

                    try:
                        cls = classify_book(title, b.get("isbn"), api_key, model=model_name)
                    except Exception as e:
                        log(fname, "분류", f"'{title}' 분류 실패: {e}", "warning")
                        cls = {"genre": "기타", "subgenre": "", "confidence": 0.0,
                               "author": "", "publisher": "", "needs_review": True}

                    book_items.append(BookItem(
                        title=title,
                        price=max(0, price),
                        quantity=b.get("quantity", 1) or 1,
                        discount=b.get("discount", 0) or 0,
                        isbn=b.get("isbn"),
                        genre=cls["genre"],
                        subgenre=cls.get("subgenre", ""),
                        classify_confidence=cls["confidence"],
                        needs_review=cls["needs_review"],
                        author=cls.get("author", ""),
                        publisher=cls.get("publisher", ""),
                    ))

                log(fname, "분류", f"장르 분류 완료 ({len(book_items)}권)", "success")

                # ── 7. ParsedReceipt 생성 ─────────────────────────────────
                from datetime import date as date_type
                rdate = None
                if parsed.get("receipt_date"):
                    try:
                        parts = str(parsed["receipt_date"]).split("-")
                        rdate = date_type(int(parts[0]), int(parts[1]), int(parts[2]))
                    except Exception:
                        pass

                receipt_id = f"RCP-{datetime.now().strftime('%Y%m%d')}-{idx+1:03d}"
                receipt = ParsedReceipt(
                    receipt_id=receipt_id,
                    source_file=fname,
                    receipt_date=rdate,
                    store_name=parsed.get("store_name"),
                    total_amount=parsed.get("total_amount"),
                    books=book_items,
                    ocr_confidence=avg_confidence,
                    parse_confidence=0.9,
                )
                st.session_state["results"].append(receipt)
                log(fname, "완료", f"처리 완료 ✅ ({len(book_items)}권)", "success")

            except Exception as e:
                msg = str(e)
                st.session_state["failed"].append({"file": fname, "error": msg})
                log(fname, "오류", msg, "error")

        # ── 8. 병합 + 엑셀 생성 ────────────────────────────────────────────
        progress_bar.progress(95, text="엑셀 파일 생성 중...")

        if st.session_state["results"]:
            from modules.merger import merge_results
            from modules.excel_generator import generate_excel

            df = merge_results(st.session_state["results"])
            st.session_state["df"] = df

            excel_name = f"도서목록_{datetime.now().strftime('%Y%m%d')}_{session_id[:8]}.xlsx"
            excel_path = os.path.join(out_dir, excel_name)
            generate_excel(df, excel_path)

            with open(excel_path, "rb") as f:
                st.session_state["excel_bytes"] = f.read()
            st.session_state["excel_name"] = excel_name
            log("시스템", "생성", f"엑셀 파일 생성 완료: {excel_name}", "success")
        else:
            log("시스템", "생성", "처리된 영수증이 없어 엑셀을 생성하지 않았습니다.", "warning")

        elapsed = time.time() - start_ts
        st.session_state["processed"] = True
        progress_bar.progress(100, text=f"완료! (소요 시간: {elapsed:.1f}초)")

        success_count = len(st.session_state["results"])
        fail_count = len(st.session_state["failed"])
        status_placeholder.success(
            f"처리 완료: **성공 {success_count}개** / 실패 {fail_count}개 / 소요 {elapsed:.1f}초"
        )

        try:
            cleanup_temp_dir(temp_dir)
        except Exception:
            pass

        if st.session_state["excel_bytes"]:
            st.info("👉 **결과 확인** 탭에서 도서 목록을 확인하고 엑셀을 다운로드하세요.")


# ═══════════════════════════════════════════════════════════════════════
# TAB 2: 결과 확인
# ═══════════════════════════════════════════════════════════════════════
with tab_result:
    if not st.session_state["processed"]:
        st.info("아직 처리된 결과가 없습니다. **파일 업로드** 탭에서 영수증을 처리하세요.")
    else:
        df = st.session_state.get("df")

        if df is None or len(df) == 0:
            st.warning("추출된 도서 데이터가 없습니다. 처리 로그를 확인하세요.")
        else:
            # ── 요약 통계 ────────────────────────────────────────────────
            total_books = len(df)
            total_amount = int(df["amount"].sum())
            review_cnt = int(df["needs_review"].sum())
            success_rate = (total_books - review_cnt) / total_books * 100 if total_books else 0

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("📚 총 도서 수", f"{total_books}권")
            with c2:
                st.metric("💰 총 구매 금액", f"{total_amount:,}원")
            with c3:
                st.metric("✅ 분류 성공률", f"{success_rate:.1f}%")
            with c4:
                st.metric("⚠️ 검토 필요", f"{review_cnt}건")

            st.markdown("---")

            # ── 엑셀 다운로드 버튼 ────────────────────────────────────────
            if st.session_state["excel_bytes"]:
                st.download_button(
                    label="⬇️ 엑셀 파일 다운로드 (.xlsx)",
                    data=st.session_state["excel_bytes"],
                    file_name=st.session_state["excel_name"],
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=False,
                )

            st.markdown("---")

            # ── 데이터 필터 ──────────────────────────────────────────────
            st.markdown("### 📋 전체 도서 목록")

            col_f1, col_f2 = st.columns([1, 2])
            with col_f1:
                genre_options = ["전체"] + sorted(df["genre"].unique().tolist())
                selected_genre = st.selectbox("장르 필터", genre_options)
            with col_f2:
                search_query = st.text_input("도서명 검색", placeholder="검색어를 입력하세요...")

            filtered_df = df.copy()
            if selected_genre != "전체":
                filtered_df = filtered_df[filtered_df["genre"] == selected_genre]
            if search_query:
                filtered_df = filtered_df[
                    filtered_df["title"].str.contains(search_query, case=False, na=False)
                ]

            # 표시용 컬럼 이름 변경
            display_df = filtered_df.rename(columns={
                "title": "도서명", "author": "저자", "publisher": "출판사",
                "isbn": "ISBN", "genre": "장르", "subgenre": "세부장르",
                "price": "정가", "quantity": "수량", "amount": "금액",
                "receipt_date": "구매일", "store_name": "서점명",
                "receipt_id": "영수증ID", "confidence": "신뢰도", "needs_review": "검토필요",
            })

            st.dataframe(
                display_df,
                use_container_width=True,
                height=min(600, 60 + 35 * len(filtered_df)),
                column_config={
                    "정가": st.column_config.NumberColumn(format="%d원"),
                    "금액": st.column_config.NumberColumn(format="%d원"),
                    "신뢰도": st.column_config.NumberColumn(format="%.1%"),
                    "검토필요": st.column_config.CheckboxColumn(),
                },
            )

            st.caption(f"표시: {len(filtered_df)}건 / 전체: {total_books}건")

            # ── 장르별 분포 ──────────────────────────────────────────────
            if len(df) > 0:
                st.markdown("---")
                st.markdown("### 📊 장르별 분포")
                import pandas as pd
                genre_counts = df.groupby("genre").agg(
                    도서수=("title", "count"),
                    총금액=("amount", "sum")
                ).reset_index().rename(columns={"genre": "장르"})
                genre_counts["총금액"] = genre_counts["총금액"].astype(int)

                col_chart1, col_chart2 = st.columns(2)
                with col_chart1:
                    st.bar_chart(genre_counts.set_index("장르")["도서수"])
                with col_chart2:
                    st.bar_chart(genre_counts.set_index("장르")["총금액"])


# ═══════════════════════════════════════════════════════════════════════
# TAB 3: 처리 로그
# ═══════════════════════════════════════════════════════════════════════
with tab_log:
    logs = st.session_state.get("logs", [])

    if not logs:
        st.info("아직 처리 로그가 없습니다. 파일을 처리하면 여기에 기록됩니다.")
    else:
        # 요약
        success_logs = [l for l in logs if l["level"] == "success"]
        error_logs = [l for l in logs if l["level"] == "error"]
        warning_logs = [l for l in logs if l["level"] == "warning"]

        c1, c2, c3 = st.columns(3)
        c1.metric("✅ 성공", len(success_logs))
        c2.metric("⚠️ 경고", len(warning_logs))
        c3.metric("❌ 오류", len(error_logs))

        st.markdown("---")

        # 필터
        level_filter = st.selectbox(
            "로그 레벨",
            ["전체", "success", "warning", "error", "info"],
            format_func=lambda x: {"전체": "전체", "success": "✅ 성공", "warning": "⚠️ 경고",
                                    "error": "❌ 오류", "info": "ℹ️ 정보"}.get(x, x),
        )

        filtered_logs = logs if level_filter == "전체" else [l for l in logs if l["level"] == level_filter]

        # 로그 출력
        prev_file = None
        for entry in filtered_logs:
            if entry["file"] != prev_file:
                st.markdown(f"**📄 {entry['file']}**")
                prev_file = entry["file"]

            icon = entry["icon"]
            step = entry["step"]
            msg = entry["message"]
            color_map = {
                "success": "#16a34a",
                "error": "#dc2626",
                "warning": "#d97706",
                "info": "#475569",
            }
            color = color_map.get(entry["level"], "#475569")
            st.markdown(
                f'<span style="color:{color}">{icon} '
                f'<span style="background:#f1f5f9;border-radius:4px;padding:1px 7px;font-size:0.78rem;color:#1d4ed8">{step}</span>'
                f' {msg}</span>',
                unsafe_allow_html=True,
            )

        # 실패 파일 목록
        if st.session_state.get("failed"):
            st.markdown("---")
            st.markdown("### ❌ 처리 실패 파일")
            for item in st.session_state["failed"]:
                with st.expander(f"❌ {item['file']}"):
                    st.error(item["error"])
