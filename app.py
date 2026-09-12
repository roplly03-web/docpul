import os
import sys
from pathlib import Path

# 1. 프로젝트 루트 경로 sys.path 추가
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import streamlit as st
from supabase import create_client, Client

# diagnose 모듈 임포트
try:
    from diagnose import show_diagnose_page, clear_diagnosis_state
except ImportError:
    from views.diagnose_view import show_diagnose_page, clear_diagnosis_state

# 🌟 탭이나 다른 렌더링보다 "최상단"에서 query_params(reset)를 먼저 감지하여 처리
if st.query_params.get("reset") == "true":
    clear_diagnosis_state()
    st.query_params.clear()
    # 탭 상태도 첫 번째 탭("식물 진단")으로 강제 이동시키고 싶다면 여기서 세션 제어 가능


# Supabase 클라이언트 초기화
@st.cache_resource
def init_supabase():
    url = st.secrets.get("SUPABASE_URL") or st.secrets.get("supabase", {}).get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY") or st.secrets.get("supabase", {}).get("SUPABASE_KEY")
    
    if not url or not key:
        return None
    
    return create_client(url, key)

supabase = init_supabase()

# 기본 페이지 설정
st.set_page_config(
    page_title="닥풀 AI 식물주치의",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# UI 스타일 설정
st.markdown("""
    <style>
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
    }
    header[data-testid="stHeader"] {
        height: 2rem !important;
    }
    div[data-testid="stTabs"] {
        margin-top: 12px !important;
    }
    [data-testid="stTab"] {
        height: 55px !important;
        border-radius: 8px 8px 0px 0px !important;
    }
    [data-testid="stTab"] [data-testid="stMarkdownContainer"] p {
        font-size: 18px !important;
        color: #495057 !important;
        margin: 0 !important;
    }
    [data-testid="stTab"][aria-selected="true"] [data-testid="stMarkdownContainer"] p {
        font-size: 20px !important;
        font-weight: 700 !important;
    }
    </style>
""", unsafe_allow_html=True)

# 🌟 로고 이미지 링크 (어떤 탭에 있든 최상단에서 DOM으로 동작)
light_logo_url = "https://oqppdobtnpoyqpruyjba.supabase.co/storage/v1/object/public/tree-images/light_logo.png"
dark_logo_url = "https://oqppdobtnpoyqpruyjba.supabase.co/storage/v1/object/public/tree-images/dark_logo.png"

st.markdown(
    f"""
    <style>
        .logo-img {{
            width: 250px;
            cursor: pointer;
            display: block;
            margin-bottom: 15px;
        }}
        .light-logo {{ display: block; }}
        .dark-logo {{ display: none; }}

        @media (prefers-color-scheme: dark) {{
            .light-logo {{ display: none; }}
            .dark-logo {{ display: block; }}
        }}
    </style>
    <div style="margin-top: 16px;">
        <a href="/?reset=true" target="_self">
            <img src="{light_logo_url}" class="logo-img light-logo">
            <img src="{dark_logo_url}" class="logo-img dark-logo">
        </a>
    </div>
    """,
    unsafe_allow_html=True
)

# 세션 상태 안전 초기화
if "latest_report" not in st.session_state:
    st.session_state["latest_report"] = None
if "error_message" not in st.session_state:
    st.session_state["error_message"] = None

# 메인 탭 및 모듈 로드
# 메인 탭 및 모듈 로드
try:
    from views.history_view import show_history_page
    from views.map_view import show_map_page

    # 🟢 [추가] 탭 글씨 색상 가독성 개선용 CSS (라이트/다크모드 대응)
    st.markdown(
        """
        <style>
            [data-testid="stTabs"] button[data-baseweb="tab"] p {
                color: #333333 !important;
                font-weight: 500;
            }
            @media (prefers-color-scheme: dark) {
                [data-testid="stTabs"] button[data-baseweb="tab"] p {
                    color: #f0f0f0 !important;
                }
            }
        </style>
        """,
        unsafe_allow_html=True
    )

    tab1, tab2, tab3 = st.tabs(["식물 진단", "진단 기록", "식물 지도"])

    with tab1:
        show_diagnose_page()

    with tab2:
        show_history_page()

    with tab3:
        show_map_page()

except Exception as e:
    st.error(f"⚠️ 앱 구동 중 오류가 발생했습니다: {e}")
    st.exception(e)
