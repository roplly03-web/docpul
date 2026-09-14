import os
import sys
from pathlib import Path
import streamlit as st
from supabase import create_client, Client

# 현재 app.py 파일이 있는 최상위 폴더 경로를 파이썬 모듈 검색 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# 뷰 모듈 불러오기
try:
    from views.intro_view import show_intro_page
    from views.diagnose_view import show_diagnose_page, clear_diagnosis_state
    from views.history_view import show_history_page
    from views.map_view import show_map_page
except ModuleNotFoundError:
    from views.intro import show_intro_page
    from views.diagnose import show_diagnose_page, clear_diagnosis_state
    from views.history import show_history_page
    from views.map import show_map_page

# 홈(리셋) 쿼리 파라미터 처리
if st.query_params.get("reset") == "true":
    clear_diagnosis_state()
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

# 기본 여백 조절 CSS
st.markdown("""
    <style>
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
    }
    header[data-testid="stHeader"] {
        height: 2rem !important;
    }
    </style>
""", unsafe_allow_html=True)

# 로고 이미지 및 라이트/다크모드 대응
light_logo_url = "https://oqppdobtnpoyqpruyjba.supabase.co/storage/v1/object/public/tree-images/light_logo.png"
dark_logo_url = "https://oqppdobtnpoyqpruyjba.supabase.co/storage/v1/object/public/tree-images/dark_logo.png"

st.markdown(
    f"""
    <style>
        .logo-img {{
            width: 200px;
            cursor: pointer;
            display: block;
            margin-bottom: 20px;
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
if "show_diagnosis_form" not in st.session_state:
    st.session_state["show_diagnosis_form"] = False

# ---------------------------------------------------------
# 상단 st.tabs 렌더링 및 페이지 라우팅
# ---------------------------------------------------------
tab_intro, tab_history, tab_map = st.tabs(["닥풀 AI", "진단 기록", "식물 지도"])

with tab_intro:
    # 소개 화면 내 [진단 시작하기] 버튼 클릭 시 view2 (진단 폼)로 전환
    if st.session_state.get("show_diagnosis_form", False):
        show_diagnose_page()
    else:
        show_intro_page()

with tab_history:
    show_history_page()

with tab_map:
    show_map_page()
