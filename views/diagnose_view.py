import io
import math
import re
import threading
import time
from datetime import datetime
from PIL import Image
import requests
import streamlit as st
import streamlit.components.v1 as components

from utils import (
    apply_global_styles,
    call_gemini_structured_diagnosis,
    extract_gps_from_image,
    format_location_display,
    get_address_from_coords,
    get_location_by_ip,
    parse_primary_scientific_name,
    sanitize_and_format_markdown,
    save_to_supabase,
    search_google_places,
    supabase,
)

# 페이지가 시작될 때 한 번만 호출
apply_global_styles()

# 단말기 GPS 수집 모듈 안전 로드
try:
    from streamlit_js_eval import get_geolocation
except Exception:
    get_geolocation = lambda component_key=None: None

# 데이터 완전 초기화 함수 (홈 이동 및 초기화 시 호출)
def clear_diagnosis_state():
    """진단 관련 상태 및 업로드 파일 데이터 완전 초기화"""
    st.session_state["show_diagnosis_form"] = False
    
    current_key_idx = st.session_state.get("uploader_key_idx", 0)
    st.session_state["uploader_key_idx"] = current_key_idx + 1
    
    target_keys = [
        f"main_tree_uploader_{current_key_idx}", "cached_lat", "cached_lon", 
        "cached_loc_name", "search_keyword", "override_location", 
        "latest_report", "manual_keyword_input", "need_place_selection_error", 
        "is_diagnosing", "geo_step_state", "geo_try_count", "geo_failed_msg"
    ]
    for key in target_keys:
        if key in st.session_state:
            del st.session_state[key]

def show_diagnose_page():
    if "uploader_key_idx" not in st.session_state:
        st.session_state["uploader_key_idx"] = 0

    uploader_key = f"main_tree_uploader_{st.session_state['uploader_key_idx']}"

    #st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
        <h4 style="line-height: 1.3; margin-bottom: 0px; font-weight: 500;">내 식물, 닥풀이 한 번 살펴볼게요
        </h4>
        <p style="font-size: 0.9rem; line-height: 1.0; color: #75777e; margin-top: 0px; font-weight: 400;">사진 한 장으로 식물의 이름부터 증상까지 살펴봐요.
        </p>
    """, unsafe_allow_html=True)

    st.divider()

    # 1. 식물 사진 업로드
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
        for k in ["cached_lat", "cached_lon", "cached_loc_name", "search_keyword", "override_location", "latest_report", "manual_keyword_input", "need_place_selection_error", "is_diagnosing", "geo_step_state", "geo_try_count", "geo_failed_msg"]:
            st.session_state.pop(k, None)
        return

    # 2. 이미지 표시 및 위치 변수 선언
    try:
        image = Image.open(uploaded_file)

        # JPEG 원본을 가능한 한 작은 해상도로 디코딩
        if image.format == "JPEG":
            image.draft("RGB", (1600, 1600))

        image.thumbnail((800, 800), Image.Resampling.LANCZOS)

        st.image(image, use_container_width=True)

    except Exception as e:
        st.error("사진을 확인할 수 없어요. **다시 업로드해 주세요.**")
        return

    # 위치 관련 변수 초기 선언
    lat = st.session_state.get("cached_lat")
    lon = st.session_state.get("cached_lon")
    selected_loc_name = st.session_state.get("cached_loc_name", "")

    has_report = bool(st.session_state.get("latest_report"))
    is_diagnosing = st.session_state.get("is_diagnosing", False)

    # 파일이 바뀌면 위치 관련 캐시 초기화
    current_file_name = uploaded_file.name if uploaded_file else "no_file"
    
    if st.session_state.get("last_file_name") != current_file_name:
        st.session_state["last_file_name"] = current_file_name
        for key in ["cached_lat", "cached_lon", "cached_loc_name", "override_location", "geo_step_state", "geo_try_count", "geo_failed_msg"]:
            st.session_state.pop(key, None)
        lat, lon, selected_loc_name = None, None, ""

    def is_valid(val):
        try:
            return val is not None and not math.isnan(float(val)) and not math.isinf(float(val))
        except:
            return False

    # 1차 시도: 사진 내부 EXIF GPS 자동 추출
    if not has_report and not is_diagnosing and not is_valid(lat) and not st.session_state.get("override_location"):
        try:
            p_lat, p_lon = extract_gps_from_image(image)
            
            if is_valid(p_lat) and is_valid(p_lon):
                current_lat = float(p_lat)
                current_lon = float(p_lon)
                
                if (st.session_state.get("cached_lat") != current_lat or 
                    st.session_state.get("cached_lon") != current_lon):
                    
                    st.session_state["cached_lat"] = current_lat
                    st.session_state["cached_lon"] = current_lon
                    
                    addr = None
                    try:
                        addr = get_address_from_coords(current_lat, current_lon)
                    except Exception:
                        pass
                        
                    st.session_state["cached_loc_name"] = addr if addr else f"사진 속 위치 ({current_lat:.4f}, {current_lon:.4f})"
                    st.rerun()
                    
        except Exception:
            pass

    # 화면 표시 UI (조건별 위치 선택 UI)
    if not has_report and not is_diagnosing:
        st.markdown("---")
        
        st.markdown("""
            <h4 style="line-height: 1.5; margin-bottom: 0px; font-weight: 500;"><b>식물이 있는 곳</b>도 함께 살펴봐요
            </h4>
            <p style="font-size: 0.95rem; line-height: 1.5; color: #75777e; margin-top: 0px; font-weight: 400; padding-bottom: 10px;"><b>식물이 있는 곳</b>도 알려주면 <b>더 정확</b>하게 살펴볼 수 있어요.<br>같은 식물도 <b>지역과 계절</b>에 따라 나타나는 <b>이상 증상</b>이 다를 수 있어요.
            </p>
        """, unsafe_allow_html=True)

        # CASE 1: 이미 위치가 지정된 경우
        if is_valid(lat):
            disp_loc = format_location_display(selected_loc_name, lat, lon)
            st.success(f"📍 식물이 있는 곳: **{disp_loc}**")
            if st.button("📌 위치 직접 검색하기", type="secondary", key="btn_reset_loc"):
                st.session_state.pop("cached_lat", None)
                st.session_state.pop("cached_lon", None)
                st.session_state.pop("cached_loc_name", None)
                st.session_state["override_location"] = True
                st.session_state["geo_step_state"] = "ready"
                st.session_state["geo_try_count"] = 0
                st.rerun()

        # CASE 2: 수동 검색 선택 또는 3회 실패 후 자동 전환된 경우
        elif st.session_state.get("override_location"):
            if st.session_state.get("geo_failed_msg"):
                st.warning(st.session_state.pop("geo_failed_msg"))

            keyword_input = st.text_input(
                "식물이 있는 곳을 찾지 못했어요. **장소를 직접 검색**해 주세요.",
                placeholder="예: 서울숲, 푸른수목원, 우리집 주소",
                key="manual_keyword_input"
            )
            
            if keyword_input and keyword_input.strip():
                try:
                    results = search_google_places(keyword_input.strip())
                    if results:
                        st.markdown("""
                            <p style="font-size: 0.95rem; line-height: 1.5; color: #75777e; margin-top: 0px; font-weight: 400; padding-top: 16px;">검색 결과에서 <b>식물이 있는 곳</b>를 선택해 주세요.
                            </p>
                        """, unsafe_allow_html=True)
                        
                        st.markdown("""
                            <style>
                                div[data-testid="stButton"] > button {
                                    width: 100% !important;
                                    text-align: left !important;
                                    justify-content: flex-start !important;
                                    padding-left: 16px !important;
                                }
                            </style>
                        """, unsafe_allow_html=True)

                        for idx, r in enumerate(results):
                            if st.button(f"📍 {r['label']}", type="secondary", key=f"place_btn_{idx}", use_container_width=True):
                                st.session_state["cached_lat"] = r["lat"]
                                st.session_state["cached_lon"] = r["lon"]
                                st.session_state["cached_loc_name"] = r["label"]
                                st.session_state["override_location"] = False
                                st.rerun()
                    else:
                        st.caption("검색 결과가 없어요. 다른 장소를 입력해 보세요.")
                except Exception:
                    pass

        # CASE 3: 위치 선택 버튼 및 GPS 진행 상태
        else:
            if "geo_step_state" not in st.session_state:
                st.session_state["geo_step_state"] = "ready"
            if "geo_try_count" not in st.session_state:
                st.session_state["geo_try_count"] = 0

            if st.session_state.get("geo_step_state") == "requesting":
                try_cnt = st.session_state.get("geo_try_count", 1)
                st.info(f"브라우저 상단의 **위치 권한 허용**을 눌러주세요.")

            col1, col2 = st.columns(2)

            with col1:
                if st.button("📍 현재 위치 가져오기", key="btn_fetch_geo_real"):
                    st.session_state["geo_step_state"] = "requesting"
                    st.session_state["geo_try_count"] = 1
                    st.rerun()

            with col2:
                if st.button("📌 위치 직접 검색하기", key="btn_skip_to_manual"):
                    st.session_state["override_location"] = True
                    st.session_state["geo_step_state"] = "ready"
                    st.session_state["geo_try_count"] = 0
                    st.rerun()
                    
    # 이미지 압축 처리
    img_bytes = None
    try:
        img_byte_arr = io.BytesIO()
        if image.mode != "RGB":
            image = image.convert("RGB")
        image.save(img_byte_arr, format='JPEG', quality=85)
        img_bytes = img_byte_arr.getvalue()
    except Exception as e:
        st.error("사진을 처리하지 못했어요. 다시 업로드해 주세요.")
        return

    # ---------------------------------------------------------
    # 백그라운드 위치 수집 및 자동 수동 전환 로직 (배포 환경 팝업 차단 대응)
    # ---------------------------------------------------------
    if not has_report and not is_diagnosing and st.session_state.get("geo_step_state") == "requesting":
        try_cnt = st.session_state.get("geo_try_count", 1)
        
        loc = None
        try:
            # 매 시도마다 컴포넌트를 다시 불러와 브라우저 권한 재요청
            loc = get_geolocation(component_key=f"get_geo_eval_try_{try_cnt}")
        except Exception:
            pass

        # 1. GPS 수집 성공시
        if loc and isinstance(loc, dict) and "coords" in loc:
            coords = loc.get("coords", {})
            lat_val = coords.get("latitude")
            lon_val = coords.get("longitude")

            if is_valid(lat_val) and is_valid(lon_val):
                st.session_state["cached_lat"] = float(lat_val)
                st.session_state["cached_lon"] = float(lon_val)

                try:
                    addr = get_address_from_coords(lat_val, lon_val)
                    st.session_state["cached_loc_name"] = addr if (addr and addr.strip()) else f"현재 위치 ({lat_val:.4f}, {lon_val:.4f})"
                except Exception:
                    st.session_state["cached_loc_name"] = f"현재 위치 ({lat_val:.4f}, {lon_val:.4f})"

                st.session_state["geo_step_state"] = "done"
                st.rerun()

        # 2. GPS 수집 실패, 브라우저 차단/거부 에러, 또는 3회 시도 초과 시
        elif (loc and isinstance(loc, dict) and "error" in loc) or try_cnt >= 5:
            # IP 기반 대략 위치 Fallback 저장
            try:
                ip_lat, ip_lon, ip_addr = get_location_by_ip()
                if is_valid(ip_lat) and is_valid(ip_lon):
                    st.session_state["cached_lat"] = float(ip_lat)
                    st.session_state["cached_lon"] = float(ip_lon)
                    st.session_state["cached_loc_name"] = ip_addr if (ip_addr and "****" not in str(ip_addr)) else f"대략적인 위치 ({float(ip_lat):.2f}, {float(ip_lon):.2f})"
            except Exception:
                pass

            st.session_state["geo_step_state"] = "failed"
            st.session_state["override_location"] = True
            st.rerun()

        # 3. 브라우저 응답 대기 중 (1초 후 카운트 올려 재시도)
        else:
            time.sleep(1.0)
            st.session_state["geo_try_count"] = try_cnt + 1
            st.rerun()

    # 3. AI 진단 시작 버튼
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

            if st.button("🌱 식물 **진단 시작하기**", type="primary", key="btn_run_diagnosis", use_container_width=True):
                if not img_bytes:
                    st.error("사진을 확인할 수 없어요. **다시 업로드해 주세요.**")
                    st.stop()

                keyword_input_val = st.session_state.get("manual_keyword_input", "")
                has_cached_lat = is_valid(st.session_state.get("cached_lat"))

                if keyword_input_val.strip() and not has_cached_lat:
                    st.stop()
                
                st.session_state["is_diagnosing"] = True
                action_container.empty()
                st.rerun()
            
    # 4. 진단 진행 중 상태 처리
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
            <h4 style="line-height: 1.5; margin-bottom: 0px; font-weight: 500;">식물을 <b>꼼꼼하게</b> 살펴보고 있어요
            </h4>
            <p style="font-size: 0.9rem; line-height: 1.5; color: #75777e; margin-top: 0px; font-weight: 400;">사진에서 <b>식물의 이름과 상태</b>를 하나씩 확인하고 있어요.<br><b>잠시만 기다려주세요.</b>
            </p>
        """, unsafe_allow_html=True)
  
        progress_bar = st.progress(0)
        status_text = st.empty()

        res_box = {}

        def run_diagnosis():
            res_box["data"] = call_gemini_structured_diagnosis(
                img_bytes=img_bytes,
                location_name=st.session_state.get("cached_loc_name", ""),
                lat=st.session_state.get("cached_lat"),
                lon=st.session_state.get("cached_lon"),
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
                status_text.caption(f"식물의 상태를 살펴보고 있어요... ({current_progress}%)")
            else:
                status_text.caption(f"진단 결과를 정리하고 있어요... 잠시만 기다려주세요. ({MAX_HOLD_PERCENT}%)")

            time.sleep(0.1)

        progress_bar.progress(100)
        status_text.caption("분석을 마쳤어요!")
        time.sleep(0.3)

        res = res_box.get("data", {"status": "ERROR", "message": "결과를 준비하지 못했어요."})
        st.session_state["is_diagnosing"] = False

        if res.get("status") != "SUCCESS":
            st.error(f"식물을 살펴보지 못했어요. 잠시 후 다시 시도해 주세요.")
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
                symptoms_match = re.search(r'#+\s*이상\s*증상\s*및\s*상태\s*분석\s*\n+(.*?)(?=\n+#+|\Z)', ai_raw_result, re.DOTALL)
                symptoms_text = symptoms_match.group(1).strip() if symptoms_match else ""

                details_match = re.search(r'#+\s*시각적\s*특징\s*및\s*식별\s*근거\s*\n+(.*?)(?=\n+#+|\Z)', ai_raw_result, re.DOTALL)
                details_text = details_match.group(1).strip() if details_match else ""

                urgent_match = re.search(r'#+\s*먼저\s*해주세요\s*\n+(.*?)(?=\n+#+|\Z)', ai_raw_result, re.DOTALL)
                urgent_text = urgent_match.group(1).strip() if urgent_match else ""

                try:
                    save_to_supabase(
                        image_bytes=img_bytes, 
                        file_name=uploaded_file.name, 
                        sci_name=sci_name, 
                        plant_name=estimated_plant_name,
                        health_score=health_score, 
                        confidence=confidence, 
                        lat=st.session_state.get("cached_lat"), 
                        lon=st.session_state.get("cached_lon"), 
                        loc_name=st.session_state.get("cached_loc_name", ""), 
                        report=ai_raw_result,
                        symptoms=symptoms_text,
                        details=details_text,
                        urgent=urgent_text
                    )
                except Exception as e:
                    st.error(f"진단 결과를 저장하지 못했어요.")

            st.session_state["latest_report"] = {
                "health_score": health_score,
                "confidence": confidence,
                "plant_name": estimated_plant_name,
                "scientific_name": sci_name,
                "one_line_summary": one_line_summary,
                "lat": st.session_state.get("cached_lat"),
                "lon": st.session_state.get("cached_lon"),
                "location_name": st.session_state.get("cached_loc_name", ""),
                "raw_report": ai_raw_result
            }
            st.rerun()

    # 5. 정밀 리포트 출력
    if st.session_state.get("latest_report"):
        rep = st.session_state["latest_report"]
        st.markdown("---")
        
        is_not_plant = (rep['confidence'] == 0) or ("식물 아님" in rep['plant_name']) or ("비식물" in rep['plant_name'])

        if is_not_plant:
            st.markdown(sanitize_and_format_markdown(rep['raw_report']))
        else:
            st.subheader("닥풀 AI 진단 요약")
            
            with st.container(border=True):
                score = rep['health_score']
                if score >= 80:
                    status_text, badge_bg, badge_fg = "건강한 편이에요", "#E6F4EA", "#137333"
                elif score >= 60:
                    status_text, badge_bg, badge_fg = "관찰이 필요해요", "#F1F3F4", "#3C4043"
                elif score >= 40:
                    status_text, badge_bg, badge_fg = "관리가 필요해요", "#FCE8E6", "#C5221F"
                else:
                    status_text, badge_bg, badge_fg = "도움이 필요해요", "#FCE8E6", "#C5221F"

                m1, m2 = st.columns(2)

                with m1:
                    st.markdown(f"""
                        <div style="border: 1px solid #e0e0e0; border-radius: 10px; padding: 14px 8px; text-align: center; min-height: 145px; display: flex; flex-direction: column; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                            <div style="font-size: 0.85rem; color: #666; font-weight: 400; margin-bottom: 6px;">식물 건강 점수</div>
                            <div style="font-size: 2.0rem; font-weight: 700; ; margin-bottom: 8px; line-height: 1.2;">{score}점</div>
                            <div style="display: inline-block; background-color: {badge_bg}; color: {badge_fg}; font-size: 0.85rem; font-weight: 500; padding: 3px 10px; border-radius: 12px;">
                                {status_text}
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

                with m2:
                    st.markdown(f"""
                        <div style="border: 1px solid #e0e0e0; border-radius: 10px; padding: 14px 8px; text-align: center; min-height: 145px; display: flex; flex-direction: column; justify-content: space-between; align-items: center; box-sizing: border-box; margin-bottom: 16px;">
                            <div style="font-size: 0.85rem; color: #666; font-weight: 400; margin-bottom: 6px;">추정 식물</div>
                            <div style="width: 100%; display: flex; align-items: center; justify-content: center; min-height: 2.0rem; margin: 4px 0; line-height: 1.2;">
                                <span style="font-size: clamp(0.85rem, 3.5cqw + 0.2rem, 1.3rem); font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; display: inline-block;">
                                    {rep['plant_name']}
                                </span>
                            </div>
                            <div style="display: inline-block; background-color: #E6F4EA; color: #137333; font-size: 0.85rem; font-weight: 500; padding: 3px 10px; border-radius: 12px;">
                                이 식물일 가능성 {rep['confidence']}%
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                
                st.markdown('<hr style="margin: 16px 0 20px 0; border: none; border-top: 1px solid #e6e6e6;">', unsafe_allow_html=True)
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**학명** `{rep['scientific_name'] or '학명을 알 수 없어요'}`")
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;**식물이 있는 곳** `{format_location_display(rep['location_name'], rep['lat'], rep['lon'])}`")
                
                summary_text = rep.get("one_line_summary")
                if summary_text:
                    st.info(f"💡 **닥풀의 한마디**\n\n {summary_text}")

            raw_text = rep['raw_report']
            DETAIL_REPORT_MARKER = "### 닥풀 AI 진단 리포트"
            report_body = (DETAIL_REPORT_MARKER + raw_text.split(DETAIL_REPORT_MARKER, 1)[1]) if DETAIL_REPORT_MARKER in raw_text else "상세 진단 내용을 확인할 수 없어요."

            st.divider()
            st.markdown(sanitize_and_format_markdown(report_body))
