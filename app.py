import os
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import streamlit as st
from supabase import create_client, Client

# diagnose 모듈 임포트 안전 처리
try:
    from diagnose import show_diagnose_page, clear_diagnosis_state
except ImportError:
    try:
        from views.diagnose_view import show_diagnose_page, clear_diagnosis_state
    except Exception as inner_e:
        st.error(f"닥풀을 불러오지 못했어요. 잠시 후 다시 시도해주세요.")

# 쿼리 파라미터 기반 탭 상태 동기화 및 홈(리셋) 처리
query_tab = st.query_params.get("tab")
if query_tab in ["닥풀 AI", "진단 기록", "식물 지도"]:
    st.session_state["current_page"] = query_tab

if st.query_params.get("reset") == "true":
    clear_diagnosis_state()
    st.session_state["current_page"] = "닥풀 AI"
    st.session_state["show_diagnosis_form"] = False
    st.query_params.clear()

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

# 🌟 [순수 HTML/CSS 탭 스타일 및 레이어 정렬]
st.markdown("""
    <style>
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
    }
    header[data-testid="stHeader"] {
        height: 2rem !important;
    }

    /* 탭 전체 바 컨테이너 */
    .pure-html-tabs {
        display: flex;
        gap: 20px;
        align-items: center;
        margin-top: 20px !important;
        margin-bottom: 0px !important;
    }

    /* 순수 텍스트 탭 링크 기본 스타일 (비활성) */
    .pure-html-tabs a {
        font-size: 18px !important;
        font-weight: 500 !important;
        color: #6c757d !important;
        text-decoration: none !important;
        padding: 4px 2px 10px 2px !important;
        display: inline-block;
        position: relative;
        z-index: 1;
    }

    .pure-html-tabs a:hover {
        color: #5ac451 !important;
    }

    /* 현재 활성화된 순수 텍스트 탭 스타일 */
    .pure-html-tabs a.is-active {
        font-size: 18px !important;
        font-weight: 700 !important;
        color: #5ac451 !important;
        border-bottom: 3px solid #5ac451 !important;
        padding-bottom: 10px !important;
        margin-bottom: -2px;
        position: relative;
        top: 2px;
        z-index: 2;
    }

    /* 화면 좌우 100%를 채우는 구분선 */
    .full-width-divider {
        width: 100%;
        border-bottom: 1px solid #d6d6d9;
        margin-top: 2px;
        margin-bottom: 1rem;
        position: relative;
        z-index: 1;
    }

    /* 🌙 다크모드 대응 설정 */
    @media (prefers-color-scheme: dark) {
        .pure-html-tabs a {
            color: #adb5bd !important;
        }
        .pure-html-tabs a:hover {
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

# 로고 이미지 링크
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

# 세션 상태 안전 초기화 ("닥풀 AI" 기준)
if "latest_report" not in st.session_state:
    st.session_state["latest_report"] = None
if "error_message" not in st.session_state:
    st.session_state["error_message"] = None
if "current_page" not in st.session_state:
    st.session_state["current_page"] = "닥풀 AI"
if "show_diagnosis_form" not in st.session_state:
    st.session_state["show_diagnosis_form"] = False

current_page = st.session_state.get("current_page", "닥풀 AI")

# ---------------------------------------------------------
# 🌟 탭 바 렌더링 (첫 번째 탭 이름 "닥풀 AI")
# ---------------------------------------------------------
pages = ["닥풀 AI", "진단 기록", "식물 지도"]

html_tabs = '<div class="pure-html-tabs">'
for page_name in pages:
    is_active = (current_page == page_name)
    active_class = "is-active" if is_active else ""
    html_tabs += f'<a href="/?tab={page_name}" target="_self" class="{active_class}">{page_name}</a>'
html_tabs += '</div>'

st.markdown(html_tabs, unsafe_allow_html=True)

# 탭 바로 아래 구분선
st.markdown('<div class="full-width-divider"></div>', unsafe_allow_html=True)

# 메인 페이지 렌더링
try:
    from views.history_view import show_history_page
    from views.map_view import show_map_page

    if current_page == "닥풀 AI":
        show_diagnose_page()
    elif current_page == "진단 기록":
        show_history_page()
    elif current_page == "식물 지도":
        show_map_page()

except Exception as e:
    st.error(f"페이지를 불러오지 못했어요. 잠시 후 다시 시도해주세요.")
    st.exception(e)
