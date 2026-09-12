import io
import re
from datetime import datetime
from PIL import Image
import requests
import streamlit as st
import time
import threading
from utils import apply_global_styles
import math
import streamlit.components.v1 as components

# 페이지가 시작될 때 한 번만 호출
apply_global_styles()

# 단말기 GPS 수집 모듈 안전 로드
try:
    from streamlit_js_eval import get_geolocation
except Exception:
    get_geolocation = lambda: None

from utils import (
    extract_gps_from_image, get_address_from_coords, format_location_display,
    search_google_places, call_gemini_structured_diagnosis,
    parse_primary_scientific_name, save_to_supabase, sanitize_and_format_markdown,
    get_location_by_ip, supabase  
)

# DB 조회
def get_recent_3_diagnoses():
    """DB에서 최근 진단 데이터 3건 불러오기 (점수, 위치 추가)"""
    if not supabase:
        return []
    try:
        res = supabase.table("diagnosis_history") \
            .select("id, plant_name, image_url, health_score, location_name, created_at") \
            .not_.is_("image_url", "null") \
            .order("created_at", desc=True) \
            .limit(3) \
            .execute()
        return res.data or []
    except Exception:
        return []
        
# 정사각형 중앙 크롭 처리 함수
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

# 데이터 완전 초기화 함수 (홈 이동 및 초기화 시 호출)
def clear_diagnosis_state():
    """진단 관련 상태 및 업로드 파일 데이터 완전 초기화 (경량화 적용)"""
    st.session_state["show_diagnosis_form"] = False
    
    # file_uploader 키 변경으로 업로드 파일 리셋
    current_key_idx = st.session_state.get("uploader_key_idx", 0)
    st.session_state["uploader_key_idx"] = current_key_idx + 1
    
    # 제거할 대상 키 목록 (pop 대신 del 활용)
    target_keys = [
        f"main_tree_uploader_{current_key_idx}", "cached_lat", "cached_lon", 
        "cached_loc_name", "search_keyword", "override_location", 
        "latest_report", "manual_keyword_input", "need_place_selection_error", 
        "is_diagnosing", "geo_step"
    ]
    for key in target_keys:
        if key in st.session_state:
            del st.session_state[key]

def show_diagnose_page():
    # ---------------------------------------------------------
    # 0. 화면 전환 및 업로더 키 초기 상태 처리
    # ---------------------------------------------------------
    if "show_diagnosis_form" not in st.session_state:
        st.session_state["show_diagnosis_form"] = False

    if "uploader_key_idx" not in st.session_state:
        st.session_state["uploader_key_idx"] = 0

    uploader_key = f"main_tree_uploader_{st.session_state['uploader_key_idx']}"

    # 메인 렌더링용 빈 컨테이너 생성
    main_container = st.empty()

    with main_container.container():
        # ---------------------------------------------------------
        # VIEW 1: [ 닥풀 ] 홈 및 소개 화면
        # ---------------------------------------------------------
        if not st.session_state["show_diagnosis_form"]:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("""
                <h4 style="text-align: center; line-height: 1.5; margin-bottom: 10px; font-weight: 400;">
                식물의 <b>이름부터 아픈 이유</b>까지...<br><b>사진 한장</b>으로 식물을 살펴보세요
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
                        background-color: #9ebd70 !important;
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
                        background-color: #8dae61 !important;
                        color: #ffffff !important;
                    }
                </style>
            """, unsafe_allow_html=True)

            if st.button("🌱 내 식물 **진단 시작하기**", type="primary", key="btn_start_top", use_container_width=True):
                st.session_state["show_diagnosis_form"] = True
                main_container.empty()
                st.rerun()

            st.divider()

            st.markdown("""
                <h4 style="text-align: center; line-height: 1.5; margin-bottom: 8px; font-weight: 400;"><b>식물 이름</b>만 알려주는게 아니에요
                </h4>
                <p style="font-size: 1.0rem; text-align: center; line-height: 1.4; color: #75777e; margin-top: 0px; font-weight: 400;">식물 사진을 보여주면 이름부터 궁금하죠.<br>하지만 막상 이상한 부분이 보이면 <b>궁금한 건 따로</b> 있어요.
                </p>
                <br>
                <h5 style="text-align: center; line-height: 1.6; color: #555555; margin-top: 0px; font-weight: 400;">
                <b>왜</b> 이래요?<br><b>무슨 문제</b>인가요?<br><b>어떻게</b> 해야하나요?
                </h5>
                <br>
                <p style="font-size: 1.0rem; text-align: center; line-height: 1.4; color: #75777e; margin-top: 0px; font-weight: 400;">닥풀은 식물의 이름을 찾는 것에서 끝나지 않아요.
                </p>
                <p style="font-size: 1.0rem; text-align: center; line-height: 1.4; color: #75777e; margin-top: 0px; font-weight: 400;">식물의 특징, 현재 상태, 이상 증상, 원인 및 관리 방법<br><b>사진에서 확인되는 정보</b>를 바탕으로 하나씩 살펴봐요.
                </p>                
            """, unsafe_allow_html=True)
            
            st.markdown("---")

            st.markdown("""
                <h4 style="text-align: center; line-height: 1.5; margin-bottom: 8px; font-weight: 400;">닥풀은 <b>이렇게</b> 살펴봐요
                </h4>
                <p style="font-size: 1.0rem; text-align: center; line-height: 1.4; color: #75777e; margin-top: 0px; margin-bottom: 22px; font-weight: 400;">최근 <b>닥풀이 진단한 식물</b>들을 만나보세요.
                </p> 
            """, unsafe_allow_html=True)
            
            recent_items = get_recent_3_diagnoses()
            if recent_items:
                cols = st.columns(3)
                for idx, item in enumerate(recent_items):
                    with cols[idx]:
                        with st.container(border=True):
                            img_url = item.get("image_url")
                            plant_name = item.get("plant_name", "식물")
                            health_score = item.get("health_score", 0)
                            location_name = item.get("location_name") or "위치 정보 없음"

                            if img_url:
                                square_img = crop_to_square(img_url)
                                if square_img:
                                    st.image(square_img, use_container_width=True)
                                else:
                                    st.image(img_url, use_container_width=True)

                            st.markdown(f"**{plant_name}**")
                            
                            if health_score >= 80:
                                status_text = "건강한 편이에요"
                                score_color = "#137333"
                            elif health_score >= 60:
                                status_text = "조금 살펴봐요"
                                score_color = "#3C4043"
                            elif health_score >= 40:
                                status_text = "관리가 필요해요"
                                score_color = "#C5221F"
                            else:
                                status_text = "도움이 필요해요"
                                score_color = "#C5221F"

                            st.markdown(
                                f"<b style='color:{score_color};'>{health_score}점 ({status_text})</b>", 
                                unsafe_allow_html=True
                            )
                            st.caption(f"{location_name}")
            else:
                st.caption("등록된 최근 진단 사진이 없습니다.")

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("---")
            
            st.markdown("""
                <h4 style="text-align: center; line-height: 1.5; margin-bottom: 8px; font-weight: 400;">한 번의 진단에서 <b>끝나지 않아요</b>
                </h4>
                <p style="font-size: 1.0rem; text-align: center; line-height: 1.4; color: #75777e; margin-top: 0px; margin-bottom: 16px; font-weight: 400;">닥풀은 식물을 <b>한 번 살펴보고 끝나는 서비스가 아니에요.</b>
                </p> 
            """, unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            
            m1, m2 = st.columns(2)
            with m1:
                st.markdown("""
                    <div style="
                        border: 1px solid rgba(49, 51, 63, 0.2);
                        border-radius: 80px;
                        padding: 8px;
                        min-height: 100px; 
                        display: flex; 
                        flex-direction: column; 
                        justify-content: center; 
                        align-items: center;
                        margin-bottom: 16px;
                    ">
                        <h5 style="text-align: center; line-height: 1.4; margin-bottom: 0px; font-weight: 600;">
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
                        border: 1px solid rgba(49, 51, 63, 0.2);
                        border-radius: 80px;
                        padding: 8px;
                        min-height: 100px; 
                        display: flex; 
                        flex-direction: column; 
                        justify-content: center; 
                        align-items: center;
                        margin-bottom: 16px;
                    ">
                        <h5 style="text-align: center; line-height: 1.4; margin-bottom: 0px; font-weight: 600;">
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
                <p style="font-size: 1.0rem; text-align: center; line-height: 1.4; color: #75777e; margin-top: 0px; margin-bottom: 0px; font-weight: 400;">지금은 한 그루의 식물을 살펴보지만,<br>진단이 쌓이면 <b>우리동네의 식물 정보</b>가 됩니다.
                </p> 
                <br>
                <h5 style="text-align: center; line-height: 1.6; color: #555555; margin-top: 0px; font-weight: 400;">
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
                <p style="font-size: 1.0rem; text-align: center; line-height: 1.4; color: #75777e; margin-top: 0px; margin-bottom: 22px; font-weight: 400;">닥풀이 식물의 이름부터 현재 상태, 이상 증상이 있다면<br><b>원인과 관리 방법까지</b> 살펴볼게요.
                </p>
            """, unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🌱 내 식물 **진단 시작하기**", type="primary", key="btn_start_bottom", use_container_width=True):
                st.session_state["show_diagnosis_form"] = True
                main_container.empty()
                st.rerun()

        # ---------------------------------------------------------
        # VIEW 2: 식물 진단 UI
        # ---------------------------------------------------------
        else:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("""
                <h4 style="line-height: 1.3; margin-bottom: 0px; font-weight: 500;">내 식물, 닥풀이 한 번 살펴볼게요
                </h4>
                <p style="font-size: 0.9rem; line-height: 1.0; color: #75777e; margin-top: 0px; font-weight: 400;">사진 한 장으로 식물의 이름부터 증상까지 살펴봐요.
                </p>
            """, unsafe_allow_html=True)

            st.divider()

            # 1. 식물 사진 업로드 (동적 uploader_key 사용)
            st.markdown("""
                    <h4 style="line-height: 1.5; margin-bottom: 0px; font-weight: 500;">일단 <b>사진</b>부터 보여주세요
                    </h4>
                    <p style="font-size: 0.95rem; line-height: 1.5; color: #75777e; margin-top: 0px; font-weight: 400;">잎이나 줄기, 이상한 부분이 잘 보이는 사진을 올려주세요.<br><b>식물 전체와 궁금한 부분</b>이 잘 보이면 더 정확하게 살펴볼 수 있어요.
                    </p>
                """, unsafe_allow_html=True)
            
            uploaded_file = st.file_uploader(
                "",
                type=["jpg", "jpeg", "png", "webp"],
                key=uploader_key
            )

            if uploaded_file is None:
                st.session_state.pop("cached_lat", None)
                st.session_state.pop("cached_lon", None)
                st.session_state.pop("cached_loc_name", None)
                st.session_state.pop("search_keyword", None)
                st.session_state.pop("override_location", None)
                st.session_state.pop("latest_report", None)
                st.session_state.pop("manual_keyword_input", None)
                st.session_state.pop("need_place_selection_error", None)
                st.session_state.pop("is_diagnosing", None)
                return

            # 2. 이미지 표시
            try:
                image = Image.open(uploaded_file)
                st.image(image, use_container_width=True)
            except Exception as e:
                st.error(f"❌ 이미지를 읽는 중 오류가 발생했습니다: {e}")
                return

            import math

            import math

            import math

            # ---------------------------------------------------------
            # 🌟 [요청하신 완벽한 3단계 흐름] EXIF ➔ 브라우저 GPS 버튼 ➔ 수동 검색
            # ---------------------------------------------------------
            has_report = bool(st.session_state.get("latest_report"))
            is_diagnosing = st.session_state.get("is_diagnosing", False)

            # 파일이 바뀌면 위치 관련 캐시 초기화
            current_file_name = uploaded_file.name if uploaded_file else "no_file"
            if st.session_state.get("last_file_name") != current_file_name:
                st.session_state["last_file_name"] = current_file_name
                for key in ["cached_lat", "cached_lon", "cached_loc_name", "override_location", "geo_failed"]:
                    st.session_state.pop(key, None)

            def is_valid(val):
                try:
                    return not math.isnan(float(val)) and not math.isinf(float(val))
                except:
                    return False

            # [1단계] 사진 내부 EXIF GPS 추출 시도 (최초 1회)
            if not is_valid(st.session_state.get("cached_lat")) and not st.session_state.get("override_location"):
                try:
                    p_lat, p_lon = extract_gps_from_image(image)
                    if is_valid(p_lat) and is_valid(p_lon):
                        st.session_state["cached_lat"] = float(p_lat)
                        st.session_state["cached_lon"] = float(p_lon)
                        addr = get_address_from_coords(p_lat, p_lon)
                        st.session_state["cached_loc_name"] = addr if addr else f"좌표 ({p_lat:.4f}, {p_lon:.4f})"
                except:
                    pass

            lat = st.session_state.get("cached_lat")
            lon = st.session_state.get("cached_lon")
            loc_name = st.session_state.get("cached_loc_name", "")

            # ---------------------------------------------------------
            # 🖥️ UI 영역: 3단계 흐름 반영
            # ---------------------------------------------------------
            keyword_input = ""
            
            if not has_report and not is_diagnosing:
                st.markdown("---")
                st.markdown("""
                    <h4 style="line-height: 1.5; margin-bottom: 0px; font-weight: 500;"><b>식물이 있는 곳</b>도 함께 살펴봐요
                    </h4>
                    <p style="font-size: 0.95rem; line-height: 1.5; color: #75777e; margin-top: 0px; font-weight: 400;">지역과 계절에 따른 환경 특성을 반영하여 진단합니다.
                    </p>
                """, unsafe_allow_html=True)

                # 1. URL 쿼리 파라미터로 GPS 좌표가 전달되어 왔는지 우선 확인
                query_params = st.query_params
                if "lat" in query_params and "lon" in query_params:
                    try:
                        b_lat = float(query_params["lat"])
                        b_lon = float(query_params["lon"])
                        if "cached_lat" not in st.session_state:
                            st.session_state["cached_lat"] = b_lat
                            st.session_state["cached_lon"] = b_lon
                            addr = get_address_from_coords(b_lat, b_lon)
                            st.session_state["cached_loc_name"] = addr if addr else f"좌표 ({b_lat:.4f}, {b_lon:.4f})"
                            st.query_params.clear()
                            st.rerun()
                    except Exception:
                        pass

                # 2. 위치가 없고, 수동 모드가 아닐 때: Streamlit 네이티브 버튼 + 안전한 JS 브리지 활용
                elif not st.session_state.get("override_location"):
                    st.info("💡 사진에 위치 정보가 없습니다. 버튼을 눌러 정확한 기기 GPS 위치를 가져오세요.")
                    
                    # 배포 환경에서도 확실하게 동작하는 Streamlit 네이티브 버튼
                    if st.button("📍 기기 GPS 현재 위치 가져오기", type="primary", key="btn_get_browser_geo_native"):
                        # Streamlit 프론트엔드 레벨에서 브라우저 geolocation을 호출하는 안전한 스크립트 주입
                        geo_trigger_js = """
                        <script>
                        if (navigator.geolocation) {
                            navigator.geolocation.getCurrentPosition(
                                function(position) {
                                    const lat = position.coords.latitude;
                                    const lon = position.coords.longitude;
                                    // 현재 페이지 주소에 좌표를 붙여서 리로드 (부모창 탈출 및 중첩 방지)
                                    const targetUrl = window.location.pathname + "?lat=" + lat + "&lon=" + lon;
                                    window.location.href = targetUrl;
                                },
                                function(error) {
                                    alert("⚠️ 위치 권한이 거부되었거나 GPS를 사용할 수 없습니다. (설정을 확인해주세요)");
                                },
                                { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
                            );
                        } else {
                            alert("❌ 이 브라우저는 위치 정보를 지원하지 않습니다.");
                        }
                        </script>
                        """
                        components.html(geo_trigger_js, height=0, width=0)

                    # 수동 검색 전환 버튼
                    if st.button("수동으로 장소 직접 입력하기", type="secondary", key="btn_switch_manual"):
                        st.session_state["override_location"] = True
                        st.rerun()

                # 3. [최후의 보루] 수동 검색창 노출 (위치 정보를 도저히 가져올 수 없을 때만)
                if st.session_state.get("override_location"):
                    st.warning("⚠️ **현재 위치를 가져올 수 없으니 정밀 진단을 위해 식물 위치를 지정해 주세요.**")
                    keyword_input = st.text_input(
                        "장소 검색",
                        placeholder="예: 강릉시 중앙동, 속초 수목원, 우리집 주소",
                        label_visibility="collapsed",
                        key="manual_keyword_input"
                    )
                    
                    # (이하 검색 결과 버튼 처리 로직)
                    if keyword_input.strip():
                        try:
                            results = search_google_places(keyword_input.strip())
                            if results:
                                st.markdown("검색 결과에서 **식물이 있는 장소를 선택**해주세요.")
                                
                                st.markdown("""
                                    <style>
                                        div[data-testid="stButton"] {
                                            width: 100% !important;
                                            max-width: 100% !important;
                                            display: block !important;
                                        }
                                        div[data-testid="stButton"] > button {
                                            width: 100% !important;
                                            max-width: 100% !important;
                                            text-align: left !important;
                                            justify-content: flex-start !important;
                                            padding-left: 16px !important;
                                        }
                                        div[data-testid="stButton"] > button p {
                                            text-align: left !important;
                                            width: 100% !important;
                                        }
                                    </style>
                                """, unsafe_allow_html=True)

                                for idx, r in enumerate(results):
                                    if st.button(
                                        f"📍 {r['label']}", 
                                        type="secondary", 
                                        key=f"place_btn_{idx}", 
                                        use_container_width=True
                                    ):
                                        st.session_state["cached_lat"] = r["lat"]
                                        st.session_state["cached_lon"] = r["lon"]
                                        st.session_state["cached_loc_name"] = r["label"]
                                        st.session_state["override_location"] = False
                                        st.session_state.pop("need_place_selection_error", None)
                                        st.rerun()
                            else:
                                st.warning("⚠️ 검색 결과가 없어요. 다른 장소를 검색해보세요.")
                        except Exception as e:
                            st.warning(f"장소 검색 오류: {e}")

            # 이미지 압축 처리
            img_bytes = None
            try:
                img_byte_arr = io.BytesIO()
                if image.mode != "RGB":
                    image = image.convert("RGB")
                image.thumbnail((800, 800), Image.Resampling.LANCZOS)
                image.save(img_byte_arr, format='JPEG', quality=85)
                img_bytes = img_byte_arr.getvalue()
            except Exception as e:
                st.error(f"이미지 변환 실패: {e}")
                return

            # ---------------------------------------------------------
            # 3. AI 진단 시작 버튼 (진단 진행 중이 아니고, 리포트가 없을 때만 표시)
            # ---------------------------------------------------------
            action_container = st.empty()

            with action_container.container():
                if not has_report and not is_diagnosing:
                    st.markdown("---")
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
                                background-color: #9ebd70 !important;
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
                                background-color: #8dae61 !important;
                                color: #ffffff !important;
                            }
                        </style>
                    """, unsafe_allow_html=True)

                    if st.button("🌱 식물 **진단 시작하기**", type="primary", key="btn_run_diagnosis", use_container_width=True):
                        if not img_bytes:
                            st.error("⚠️ 사진을 확인할 수 없어요. **다시 업로드해 주세요.**")
                            st.stop()

                        unsubmitted_text = st.session_state.get("manual_keyword_input", "").strip()
                        if not selected_loc_name and unsubmitted_text:
                            st.session_state["need_place_selection_error"] = True
                            st.rerun()

                        # 🌟 즉시 상태 변경 및 버튼 영역 비우기 처리
                        st.session_state["is_diagnosing"] = True
                        action_container.empty()
                        st.rerun()
                    
            # ---------------------------------------------------------
            # 4. 진단 진행 중 상태 처리 (버튼이 숨겨진 상태에서만 실행)
            # ---------------------------------------------------------
            if is_diagnosing and not has_report:
                st.markdown("---")
                current_time_str = datetime.now().strftime("%Y년 %m월 %d일 %H시 %M분")

                st.markdown("""
                    <style>
                    div[data-testid="stSpinner"] {
                        margin-top: 30px !important;
                        margin-bottom: 20px !important;
                    }
                    </style>
                """, unsafe_allow_html=True)
                
                st.markdown("""
                    <h4 style="line-height: 1.5; margin-bottom: 0px; font-weight: 500;">식물을 <b>꼼꼼하게</b> 살펴보고 있어요...
                    </h4>
                    <p style="font-size: 0.9rem; line-height: 1.5; color: #75777e; margin-top: 0px; font-weight: 400;">사진과 식물이 있는 지역과 계절 정보를 함께 살펴보고 있어요. <br><b>잠시만 기다려주세요.</b>
                    </p>
                """, unsafe_allow_html=True)
          
                progress_bar = st.progress(0)
                status_text = st.empty()

                res_box = {}

                def run_diagnosis():
                    res_box["data"] = call_gemini_structured_diagnosis(
                        img_bytes=img_bytes,
                        location_name=selected_loc_name,
                        lat=lat,
                        lon=lon,
                        datetime_str=current_time_str
                    )

                api_thread = threading.Thread(target=run_diagnosis)
                api_thread.start()

                TARGET_SECONDS = 50.0
                MAX_HOLD_PERCENT = 85

                start_time = time.time()

                while api_thread.is_alive():
                    elapsed = time.time() - start_time
                    calculated_progress = int((elapsed / TARGET_SECONDS) * MAX_HOLD_PERCENT)
                    current_progress = min(calculated_progress, MAX_HOLD_PERCENT)
                    
                    progress_bar.progress(current_progress)
                    
                    if current_progress < MAX_HOLD_PERCENT:
                        status_text.caption(f"식물 상태 분석 중... ({current_progress}%)")
                    else:
                        status_text.caption(f"닥풀이 진단 리포트를 정리하는 중입니다... 잠시만 기다려주세요 ({MAX_HOLD_PERCENT}%)")

                    time.sleep(0.1)

                progress_bar.progress(100)
                status_text.caption("분석 완료!")
                time.sleep(0.3)

                res = res_box.get("data", {"status": "ERROR", "message": "응답을 받아오지 못했습니다."})
                st.session_state["is_diagnosing"] = False

                if res.get("status") != "SUCCESS":
                    st.error(f"❌ 진단 실패: {res.get('message', '⚠️ 사진을 제대로 확인하지 못했어요. 식물이 잘 보이는 사진으로 다시 시도해주세요.')}")
                else:
                    ai_raw_result = res["data"]

                    plant_match = re.search(r'(?:추정\s*식물|추정\s*수종|식물\s*종류|수종명?|식물명?)\s*[:=\-]\s*([^\n]+)', ai_raw_result)
                    estimated_plant_name = plant_match.group(1).strip() if plant_match else "식물 이름을 알 수 없어요"
                    estimated_plant_name = re.sub(r'[\[\]]', '', estimated_plant_name)

                    score_match = re.search(r'(?:식물\s*건강\s*점수|건강\s*점수|건강도)\s*[:=]\s*(\d+)', ai_raw_result)
                    health_score = int(score_match.group(1)) if score_match else 0

                    conf_match = re.search(r'(?:이\s*식물일\s*가능성|식물\s*이름\s*확신도|식별\s*확신도|확신도)\s*[:=]\s*(\d+)', ai_raw_result)
                    confidence = int(conf_match.group(1)) if conf_match else 0

                    summary_match = re.search(r'(?:닥풀의\s*한마디|한\s*줄\s*종합\s*소견)\s*[:=]\s*([^\n]+)', ai_raw_result)
                    one_line_summary = summary_match.group(1).strip() if summary_match else ""

                    sci_name = parse_primary_scientific_name(ai_raw_result)

                    is_not_plant = (confidence == 0) or ("식물 아님" in estimated_plant_name) or ("비식물" in estimated_plant_name)

                    if not is_not_plant:
                        symptoms_match = re.search(
                            r'#+\s*이상\s*증상\s*및\s*상태\s*분석\s*\n+(.*?)(?=\n+#+|\Z)', 
                            ai_raw_result, re.DOTALL
                        )
                        symptoms_text = symptoms_match.group(1).strip() if symptoms_match else ""

                        details_match = re.search(
                            r'#+\s*시각적\s*특징\s*및\s*식별\s*근거\s*\n+(.*?)(?=\n+#+|\Z)', 
                            ai_raw_result, re.DOTALL
                        )
                        details_text = details_match.group(1).strip() if details_match else ""

                        urgent_match = re.search(
                            r'#+\s*먼저\s*해주세요\s*\n+(.*?)(?=\n+#+|\Z)', 
                            ai_raw_result, re.DOTALL
                        )
                        urgent_text = urgent_match.group(1).strip() if urgent_match else ""         

                        try:
                            save_to_supabase(
                                image_bytes=img_bytes, 
                                file_name=uploaded_file.name, 
                                sci_name=sci_name, 
                                plant_name=estimated_plant_name,
                                health_score=health_score, 
                                confidence=confidence, 
                                lat=lat, 
                                lon=lon, 
                                loc_name=selected_loc_name, 
                                report=ai_raw_result,
                                symptoms=symptoms_text,
                                details=details_text,
                                urgent=urgent_text
                            )
                        except Exception as e:
                            st.error(f"DB 저장 중 오류 발생: {e}")

                    st.session_state["latest_report"] = {
                        "health_score": health_score,
                        "confidence": confidence,
                        "plant_name": estimated_plant_name,
                        "scientific_name": sci_name,
                        "one_line_summary": one_line_summary,
                        "lat": lat,
                        "lon": lon,
                        "location_name": selected_loc_name,
                        "raw_report": ai_raw_result
                    }
                    st.rerun()

            # ---------------------------------------------------------
            # 5. 정밀 리포트 출력
            # ---------------------------------------------------------
            if st.session_state.get("latest_report"):
                rep = st.session_state["latest_report"]
                
                st.markdown("---")
                
                is_not_plant = (rep['confidence'] == 0) or ("식물 아님" in rep['plant_name']) or ("비식물" in rep['plant_name'])

                if is_not_plant:
                    raw_text = rep['raw_report']
                    st.markdown(sanitize_and_format_markdown(raw_text))

                else:
                    st.subheader("닥풀 AI 진단 요약")
                    
                    with st.container(border=True):
                        score = rep['health_score']
                        if score >= 80:
                            status_text = "건강한 편이에요"
                            badge_bg, badge_fg = "#E6F4EA", "#137333"
                        elif score >= 60:
                            status_text = "조금 살펴봐요"
                            badge_bg, badge_fg = "#F1F3F4", "#3C4043"
                        elif score >= 40:
                            status_text = "관리가 필요해요"
                            badge_bg, badge_fg = "#FCE8E6", "#C5221F"
                        else:
                            status_text = "도움이 필요해요"
                            badge_bg, badge_fg = "#FCE8E6", "#C5221F"

                        m1, m2 = st.columns(2)

                        with m1:
                            st.markdown(f"""
                                <div style="border: 1px solid #e0e0e0; border-radius: 10px; padding: 14px 8px; text-align: center; min-height: 145px; display: flex; flex-direction: column; justify-content: space-between; align-items: center;">
                                    <div style="font-size: 0.85rem; color: #666; font-weight: 400; margin-bottom: 6px;">식물 건강 점수</div>
                                    <div style="font-size: 2.0rem; font-weight: 700; color: #111; margin-bottom: 8px; line-height: 1.2;">{score}점</div>
                                    <div style="display: inline-block; background-color: {badge_bg}; color: {badge_fg}; font-size: 0.85rem; font-weight: 500; padding: 3px 10px; border-radius: 12px;">
                                        ↑ {status_text}
                                    </div>
                                </div>
                            """, unsafe_allow_html=True)

                        with m2:
                            st.markdown(f"""
                                <div style="border: 1px solid #e0e0e0; border-radius: 10px; padding: 14px 8px; text-align: center; min-height: 145px; display: flex; flex-direction: column; justify-content: space-between; align-items: center; box-sizing: border-box;">
                                    <div style="font-size: 0.85rem; color: #666; font-weight: 400; margin-bottom: 6px;">추정 식물</div>
                                    <div style="width: 100%; display: flex; align-items: center; justify-content: center; min-height: 2.0rem; margin: 4px 0; line-height: 1.2;">
                                        <span style="
                                            font-size: clamp(0.85rem, 3.5cqw + 0.2rem, 1.3rem);
                                            font-weight: 700;
                                            color: #111;
                                            white-space: nowrap;
                                            overflow: hidden;
                                            text-overflow: ellipsis;
                                            max-width: 100%;
                                            display: inline-block;
                                        " title="{rep['plant_name']}">
                                            {rep['plant_name']}
                                        </span>
                                    </div>
                                    <div style="display: inline-block; background-color: #E6F4EA; color: #137333; font-size: 0.85rem; font-weight: 500; padding: 3px 10px; border-radius: 12px;">
                                        ↑ 이 식물일 가능성 {rep['confidence']}%
                                    </div>
                                </div>
                            """, unsafe_allow_html=True)
                        
                        st.markdown('<hr style="margin: 16px 0 20px 0; border: none; border-top: 1px solid #e6e6e6;">', unsafe_allow_html=True)

                        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**학명** `{rep['scientific_name'] or '학명을 알 수 없어요'}`")
                        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**식물이 있는 곳** `{format_location_display(rep['location_name'], rep['lat'], rep['lon'])}`")
                        
                        summary_text = rep.get("one_line_summary")
                        if not summary_text and rep.get("raw_report"):
                            match = re.search(r'(?:닥풀의\s*한마디|한\s*줄\s*종합\s*소견|한줄소견)\s*[:=]\s*([^\n]+)', rep["raw_report"])
                            if match:
                                summary_text = match.group(1).strip()

                        if summary_text:
                            st.info(f"💡 **닥풀의 한마디**\n\n {summary_text}")

                    raw_text = rep['raw_report']
                    DETAIL_REPORT_MARKER = "### 닥풀 AI 진단 리포트"
                    if DETAIL_REPORT_MARKER in raw_text:
                        report_body =(
                             DETAIL_REPORT_MARKER
                             + raw_text.split(DETAIL_REPORT_MARKER, 1)[1]
                        )
                    else:
                        report_body = "상세 진단 내용을 확인할 수 없어요."

                    st.divider()
                    
                    with st.container(border=False):
                        st.markdown(sanitize_and_format_markdown(report_body))
