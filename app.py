import os
import sys
from pathlib import Path
import streamlit as st
from supabase import create_client, Client

# 1. 최상위 루트 경로 등록
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# 2. 뷰 모듈 불러오기
from views.intro_view import show_intro_page
from views.diagnose_view import show_diagnose_page, clear_diagnosis_state
from views.history_view import show_history_page
from views.map_view import show_map_page

# 홈(리셋) 쿼리 파라미터 처리
if st.query_params.get("reset") == "true":
    clear_diagnosis_state()
    st.session_state["show_diagnosis_form"] = False
    st.session_state["current_page"] = "닥풀 AI"
    st.query_params.clear()

# Supabase 클라이언트 초기화
@st.cache_resource
def init_supabase():
    url = st.secrets.get("SUPABASE_URL") or st.secrets.get("supabase", {}).get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY") or st.secrets.get("supabase", {}).get("SUPABASE_KEY")
    return create_client(url, key) if url and key else None

supabase = init_supabase()

# 기본 페이지 설정
st.set_page_config(
    page_title="닥풀 AI 식물주치의",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 커스텀 탭 CSS
st.markdown("""
    <style>
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
    }
    header[data-testid="stHeader"] {
        height: 2rem !important;
    }

    div[data-testid="stRadio"] > div {
        display: flex !important;
        flex-direction: row !important;
        gap: 20px !important;
        align-items: center !important;
        margin-top: 20px !important;
        margin-bottom: 0px !important;
    }

    div[data-testid="stRadio"] label {
        font-size: 18px !important;
        font-weight: 500 !important;
        color: #6c757d !important;
        cursor: pointer !important;
        padding: 4px 2px 10px 2px !important;
        background-color: transparent !important;
        border: none !important;
    }

    div[data-testid="stRadio"] label:hover {
        color: #5ac451 !important;
    }

    div[data-testid="stRadio"] label[data-checked="true"] {
        font-size: 18px !important;
        font-weight: 700 !important;
        color: #5ac451 !important;
        border-bottom: 3px solid #5ac451 !important;
        padding-bottom: 10px !important;
        margin-bottom: -2px !important;
        position: relative !important;
        top: 2px !important;
        z-index: 2 !important;
    }

    div[data-testid="stRadio"] input[type="radio"] {
        display: none !important;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] > label > div:first-child {
        display: none !important;
    }

    .full-width-divider {
        width: 100%;
        border-bottom: 1px solid #d6d6d9;
        margin-top: 2px;
        margin-bottom: 1rem;
        position: relative;
        z-index: 1;
    }

    @media (prefers-color-scheme: dark) {
        div[data-testid="stRadio"] label {
            color: #adb5bd !important;
        }
        div[data-testid="stRadio"] label:hover {
            color: #5ac451 !important;
        }
        .full-width-divider {
            border-bottom: 1px solid #343a40 !important;
            margin-top: 2px !important;
            margin-bottom: 1rem !important;
            position: relative;
            z-index: 1;
        }
    }
    </style>
""", unsafe_allow_html=True)

# 로고 상단 배치
light_logo_url = "https://oqppdobtnpoyqpruyjba.supabase.co/storage/v1/object/public/tree-images/light_logo.png"
dark_logo_url = "https://oqppdobtnpoyqpruyjba.supabase.co/storage/v1/object/public/tree-images/dark_logo.png"

st.markdown(
    f"""
    <style>
        .logo-img {{
            width: 200px;
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
    <div style="margin-top: 22px;">
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
if "show_diagnosis_form" not in st.session_state:
    st.session_state["show_diagnosis_form"] = False
if "current_page" not in st.session_state:
    st.session_state["current_page"] = "닥풀 AI"

# ---------------------------------------------------------
# 상단 탭 라디오 렌더링
# ---------------------------------------------------------
pages = ["닥풀 AI", "진단 기록", "식물 지도"]
current_page = st.session_state.get("current_page", "닥풀 AI")

try:
    default_index = pages.index(current_page)
except ValueError:
    default_index = 0

selected_page = st.radio(
    "navigation",
    pages,
    index=default_index,
    label_visibility="collapsed",
    key="nav_radio"
)

# 탭 선택 시 라우팅 logic
if selected_page != current_page:
    st.session_state["current_page"] = selected_page
    # 어떤 탭을 누르든 이동 시 진단 모드를 해제하여 항상 깔끔한 기본 탭 화면으로 진입
    st.session_state["show_diagnosis_form"] = False
    st.rerun()

st.markdown('<div class="full-width-divider"></div>', unsafe_allow_html=True)

# ---------------------------------------------------------
# 메인 페이지 분기 라우팅
# ---------------------------------------------------------
try:
    if current_page == "닥풀 AI":
        if st.session_state.get("show_diagnosis_form", False):
            show_diagnose_page()
        else:
            show_intro_page()
            
    elif current_page == "진단 기록":
        show_history_page()
        
    elif current_page == "식물 지도":
        show_map_page()

except Exception as e:
    st.error("페이지를 불러오지 못했어요. 잠시 후 다시 시도해주세요.")
    st.exception(e)
