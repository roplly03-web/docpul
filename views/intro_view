import io
import requests
from PIL import Image
import streamlit as st

from utils import apply_global_styles, format_location_display, supabase

# 페이지 시작 시 스타일 적용
apply_global_styles()

# DB 조회 (VIEW 1 전용)
def get_recent_3_diagnoses():
    """DB에서 최근 진단 데이터 3건 불러오기"""
    if not supabase:
        return []
    try:
        res = supabase.table("diagnosis_history") \
            .select("id, plant_name, scientific_name, image_url, health_score, confidence, location_name, latitude, longitude, created_at") \
            .not_.is_("image_url", "null") \
            .order("created_at", desc=True) \
            .limit(3) \
            .execute()
        return res.data or []
    except Exception:
        return []

# 정사각형 중앙 크롭 처리 함수 (VIEW 1 전용)
def crop_to_square(img_url_or_bytes):
    """이미지를 다운로드하여 중앙 기준 1:1 정사각형으로 크롭"""
    try:
        response = requests.get(img_url_or_bytes, timeout=5)
        img = Image.open(io.BytesIO(response.content))
        
        width, height = img.size
        min_dim = min(width, height)
        
        left = (width - min_dim) / 2
        top = (height - min_dim) / 2
        right = (width + min_dim) / 2
        bottom = (height + min_dim) / 2
        
        return img.crop((left, top, right, bottom))
    except Exception:
        return None

def show_intro_page():
    """VIEW 1: [ 닥풀 ] 홈 및 소개 화면"""
    
    # history_view_5.py와 동일한 카드 스타일 공통 CSS 주입
    st.markdown("""
        <style>
        /* 건강 점수 뱃지 스타일 */
        .plant-card-badge {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.85rem;
            font-weight: bold;
            margin-bottom: 4px;
        }
        .badge-healthy { background-color: #e6f4ea; color: #137333; }
        .badge-normal { background-color: #e8f0fe; color: #1a73e8; }
        .badge-warning { background-color: #fef7e0; color: #b06000; }
        .badge-danger { background-color: #fce8e6; color: #c5221f; }

        /* 목록 카드 전용: 한 줄을 넘지 않고 말줄임표(...) 처리하는 CSS */
        .history-location {
            font-size: 0.85rem;
            color: #555;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            display: block;
            width: 100%;
        }
        .history-date {
            font-size: 0.8rem;
            color: #888;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            display: block;
            width: 100%;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("""
        <h4 style="text-align: center; line-height: 1.5; margin-bottom: 10px; font-weight: 400;">
        <b>식물 이름</b>부터 <b>아픈 이유</b>까지...<br><b>사진 한 장</b>으로 살펴보세요
        </h4>
        <p style="font-size: 1.0rem; text-align: center; line-height: 1.4; color: #75777e; margin-bottom: 22px; font-weight: 400;">
        닥풀이 식물의 종류와 현재 상태를 살펴보고,<br><b>이상 증상 원인과 관리 방법</b>까지 함께 알려드려요.
        </p>   
    """, unsafe_allow_html=True)
    
    st.markdown("""
        <style>
            div.stButton {
                display: flex !important;
                justify-content: center !important;
                margin: 0 auto !important;
            }
            div.stButton > button {
                width: 100% !important;
            }
            div.stButton > button[kind="primary"] {
                font-size: 1.0rem !important;
                font-weight: 500 !important;
                height: 3.2rem !important;
                padding-left: 2.0rem !important;
                padding-right: 2.0rem !important;
                border-radius: 50px !important;
                background-color: #5ac451 !important;
                color: #ffffff !important;
                border: none !important;
                transition: all 0.2s ease-in-out !important;
            }
            div.stButton > button[kind="primary"] p {
                font-size: 1.0rem !important;
                font-weight: 500 !important;
                color: #ffffff !important;
            }
            div.stButton > button[kind="primary"]:hover {
                background-color: #ff4b4b !important;
                color: #ffffff !important;
            }
        </style>
    """, unsafe_allow_html=True)

    if st.button("🌱 내 식물 **진단 시작하기**", type="primary", key="btn_start_top", use_container_width=True):
        st.session_state["show_diagnosis_form"] = True
        st.rerun()

    st.divider()

    st.markdown("""
        <h4 style="text-align: center; line-height: 1.5; margin-bottom: 8px; font-weight: 400;"><b>식물 이름</b>만 알려주는게 아니에요
        </h4>
        <p style="font-size: 1.0rem; text-align: center; line-height: 1.4; color: #75777e; margin-top: 0px; font-weight: 400;">식물 사진을 보여주면 이름부터 궁금하죠.<br>하지만 이상한 부분이 보이면 <b>궁금한 건 따로</b> 있어요.
        </p>
        <br>
        <h5 style="text-align: center; line-height: 1.5; margin-top: 0px; font-weight: 400;">
        <b>왜</b> 이래요?<br><b>무슨 문제</b>인가요?<br><b>어떻게</b> 해야하나요?
        </h5>
        <br>
        <p style="font-size: 1.0rem; text-align: center; line-height: 1.4; color: #75777e; margin-top: 0px; font-weight: 400;">식물의 특징, 현재 상태, 이상 증상, 원인, 관리 방법<br><b>사진에서 확인되는 정보</b>를 바탕으로 하나씩 살펴봐요.
        </p>                
    """, unsafe_allow_html=True)
    
    st.markdown("---")

    st.markdown("""
        <h4 style="text-align: center; line-height: 1.5; margin-bottom: 8px; font-weight: 400;">닥풀은 <b>이렇게</b> 살펴봐요
        </h4>
        <p style="font-size: 1.0rem; text-align: center; line-height: 1.4; color: #75777e; margin-top: 0px; margin-bottom: 22px; font-weight: 400;">최근 <b>닥풀이 살펴본 식물</b>들을 만나보세요.
        </p> 
    """, unsafe_allow_html=True)
    
    recent_items = get_recent_3_diagnoses()
    if recent_items:
        cols = st.columns(3)
        for idx, item in enumerate(recent_items):
            with cols[idx]:
                with st.container(border=True):
                    img_url = item.get("image_url")
                    if img_url:
                        square_img = crop_to_square(img_url)
                        if square_img:
                            st.image(square_img, use_container_width=True)
                        else:
                            st.image(img_url, use_container_width=True)

                    # 1. 식물 이름
                    plant_name = item.get("plant_name", "식물 이름을 알 수 없어요")
                    confidence = item.get("confidence", 0)
                    st.markdown(f"<span style='font-size:1.1rem'>**{plant_name}**</span> <span style='font-size:0.9rem; color:#75777e;'>({confidence}%)</span>", unsafe_allow_html=True)

                    # 2. 식물 건강 점수
                    health_score = item.get("health_score", 0)
                    if health_score >= 80:
                        badge_class = "badge-healthy"
                        badge_text = "건강한 편이에요"
                    elif health_score >= 60:
                        badge_class = "badge-normal"
                        badge_text = "관찰이 필요해요"
                    elif health_score >= 40:
                        badge_class = "badge-warning"
                        badge_text = "관리가 필요해요"
                    else:
                        badge_class = "badge-danger"
                        badge_text = "도움이 필요해요"

                    st.markdown(f"<span class='plant-card-badge {badge_class}'>{health_score}점 ({badge_text})</span>", unsafe_allow_html=True)

                    # 3. 식물이 있는 곳
                    location_str = format_location_display(item.get("location_name", ""), item.get("latitude"), item.get("longitude"))
                    st.markdown(f"<div class='history-location'>{location_str}</div>", unsafe_allow_html=True)

                    # 4. 진단 일자
                    created_date = (item.get("created_at") or "")[:10]
                    st.markdown(f"<div class='history-date'>{created_date}</div>", unsafe_allow_html=True)
                    st.markdown("<br>", unsafe_allow_html=True)
    else:
        st.caption("아직 살펴본 식물이 없어요.")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("---")
    
    st.markdown("""
        <h4 style="text-align: center; line-height: 1.5; margin-bottom: 8px; font-weight: 400;">한 번의 진단에서 <b>끝나지 않아요</b>
        </h4>
        <p style="font-size: 1.0rem; text-align: center; line-height: 1.4; color: #75777e; margin-top: 0px; margin-bottom: 16px; font-weight: 400;">닥풀은 식물을 <b>한 번 살펴보고 끝내지 않아요.</b>
        </p> 
    """, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    m1, m2 = st.columns(2)
    with m1:
        st.markdown("""
            <div style="
                border: 1px solid #5ac451;
                border-radius: 80px;
                padding: 8px;
                min-height: 100px; 
                display: flex; 
                flex-direction: column; 
                justify-content: center; 
                align-items: center;
                margin-bottom: 16px;
            ">
                <h5 style="text-align: center; line-height: 1.4; margin-bottom: 3px; font-weight: 600;">
                🌳 진단 기록
                </h5>
                <p style="text-align: center; line-height: 1.3; color: #75777e; margin: 0; font-weight: 400; font-size: 0.85rem;">
                지금까지 <b>살펴본 식물과 진단 결과</b>를 확인할 수 있어요.
                </p>
            </div>
        """, unsafe_allow_html=True)

    with m2:
        st.markdown("""
            <div style="
                border: 1px solid #5ac451;
                border-radius: 80px;
                padding: 8px;
                min-height: 100px; 
                display: flex; 
                flex-direction: column; 
                justify-content: center; 
                align-items: center;
                margin-bottom: 16px;
            ">
                <h5 style="text-align: center; line-height: 1.4; margin-bottom: 3px; font-weight: 600;">
                📍 식물 지도
                </h5>
                <p style="text-align: center; line-height: 1.3; color: #75777e; margin: 0; font-weight: 400; font-size: 0.85rem;">
                진단한 식물이 <b>어디에 있는지</b> 지도로 볼 수 있어요.
                </p>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
        <h4 style="text-align: center; line-height: 1.5; margin-bottom: 8px; font-weight: 400;">닥풀이 만들고 있는 <b>식물 지도</b>
        </h4>
        <p style="font-size: 1.0rem; text-align: center; line-height: 1.4; color: #75777e; margin-top: 0px; margin-bottom: 0px; font-weight: 400;">지금은 한 그루의 식물을 살펴보지만,<br>진단이 쌓이면 <b>우리 동네의 식물 정보</b>가 됩니다.
        </p> 
        <br>
        <h5 style="text-align: center; line-height: 1.6; margin-top: 0px; font-weight: 400;">
        우리 동네에는 <b>어떤 식물</b>이 있을까?<br>
        어떤 <b>이상 증상과 병해충</b>이 많이 나타날까?<br>
        <b>계절</b>에 따라 식물은 어떻게 달라질까?
        </h5>
        <br>
        <p style="font-size: 1.0rem; text-align: center; line-height: 1.4; color: #75777e; margin-top: 0px; margin-bottom: 22px; font-weight: 400;">닥풀은 이런 질문에 답할 수 있는<br><b>지역 기반 식물 정보</b>를 만들어가고 있어요.
        </p>                
    """, unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("""
        <h4 style="text-align: center; line-height: 1.5; margin-bottom: 8px; font-weight: 400;"><b>내 식물이 궁금할 때</b>, 사진을 올려보세요
        </h4>
        <p style="font-size: 1.0rem; text-align: center; line-height: 1.4; color: #75777e; margin-top: 0px; margin-bottom: 22px; font-weight: 400;">닥풀이 식물 이름부터 현재 상태<br><b>이상 증상이 있다면 원인과 관리 방법까지</b><br>살펴볼게요.
        </p>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🌱 내 식물 **진단 시작하기**", type="primary", key="btn_start_bottom", use_container_width=True):
        st.session_state["show_diagnosis_form"] = True
        st.rerun()
