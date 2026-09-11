from datetime import datetime
import streamlit as st
from utils import supabase, format_location_display, sanitize_and_format_markdown
from utils import apply_global_styles

# 페이지가 시작될 때 한 번만 호출
apply_global_styles()


# 다른 페이지 함수(예: show_map_page, show_history_page 등) 실행 직후 추가
st.session_state["last_active_tab"] = "other"  # 또는 각 페이지 이름

PAGE_SIZE = 10

# 🌟 카드 클릭 시 열리는 상세 진단서 모달 팝업
@st.dialog("상세 진단 리포트")
def show_detail_dialog(rec):
    if rec.get("image_url"):
        st.image(rec["image_url"], use_container_width=True)
    st.subheader(f"🌿 {rec.get('plant_name', '식물 이름을 알 수 없어요')}")
    st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; {rec.get('scientific_name') or '학명을 알 수 없어요'}")
    
    unified_location = format_location_display(rec.get("location_name", ""), rec.get("latitude"), rec.get("longitude"))
    created_date = rec.get('created_at', '')[:10] if rec.get('created_at') else ''

    # 🌟 점수에 따른 뱃지 텍스트 판별
    health_score = rec.get('health_score', 0)
    if health_score >= 80:
        status_text = "건강한 편이에요"
    elif health_score >= 60:
        status_text = "조금 살펴봐요"
    elif health_score >= 40:
        status_text = "관리가 필요해요"
    else:
        status_text = "도움이 필요해요"

    # 🌟 진단 핵심 정보를 요약 박스로 감싸기
    with st.container(border=True):
        st.markdown(f"**식물 건강 점수:** `{health_score}점 ({status_text})`")
        st.markdown(f"**이 식물일 가능성:** `{rec.get('confidence', 0)}%`")
        st.markdown(f"**식물이 있는 곳:** `{unified_location}`")
        st.markdown(f"**진단일:** `{created_date}`")



    # 🌟 상단 여백 추가
    with st.container():
        st.markdown("<br>", unsafe_allow_html=True)

    full_report_text = rec.get("full_report")
    if full_report_text:
        report_body = full_report_text.split("---", 1)[1] if "---" in full_report_text else full_report_text
        st.markdown(sanitize_and_format_markdown(report_body))
    else:
        st.info("**상세 진단 내용을 확인할 수 없어요.**")


def show_history_page():
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
        <h4 style="line-height: 1.3; margin-bottom: 0px; font-weight: 500;">지금까지 살펴본 식물들을 모았어요
        </h4>
        <p style="font-size: 0.9rem; line-height: 1.0; color: #75777e; margin-top: 0px; font-weight: 400;">진단했던 식물을 다시 확인할 수 있어요.
        </p>
    """, unsafe_allow_html=True)

    st.divider()

    if not supabase:
        st.warning("⚠️ **진단 기록을 불러오지 못했어요.** 잠시 후 다시 시도해주세요.")
        return

    # 세션 상태 초기화 (더보기 누적 개수 관리)
    if "history_limit" not in st.session_state:
        st.session_state["history_limit"] = PAGE_SIZE

    # 모바일 2열 / PC 4열 쇼핑몰 스타일 CSS 카드 스타일링
    st.markdown("""
        <style>
        .card-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
            margin-bottom: 20px;
        }
        @media (min-width: 768px) {
            .card-grid {
                grid-template-columns: repeat(4, 1fr);
                gap: 20px;
            }
        }
        .plant-card-badge {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: bold;
            margin-bottom: 4px;
        }
        .badge-healthy { background-color: #e6f4ea; color: #137333; }
        .badge-normal { background-color: #e8f0fe; color: #1a73e8; }
        .badge-warning { background-color: #fef7e0; color: #b06000; }
        .badge-danger { background-color: #fce8e6; color: #c5221f; }
        </style>
    """, unsafe_allow_html=True)

    try:
        # 데이터베이스 전체 개수 조회
        count_res = supabase.table("diagnosis_history").select("id", count="exact").execute()
        total_count = count_res.count if count_res.count else 0

        # N개(기본 10개 + 더보기 누적) 데이터 로딩
        current_limit = st.session_state["history_limit"]
        response = (
            supabase.table("diagnosis_history")
            .select("*")
            .neq("plant_name", "진단 불가")
            .gt("health_score", 0)
            .order("created_at", desc=True)
            .limit(current_limit)
            .execute()
        )
        records = response.data

        if not records:
            st.info("아직 저장된 진단 이력이 없습니다.")
            return

        # 반응형 컬럼 배치 (PC: 4열, 모바일: 2열)
        cols = st.columns([1, 1, 1, 1] if st.session_state.get("is_desktop", True) else [1, 1])
        col_count = len(cols)

        for idx, rec in enumerate(records):
            target_col = cols[idx % col_count]
            
            with target_col:
                with st.container(border=True):
                    # 1. 첨부 이미지
                    img_url = rec.get("image_url")
                    if img_url:
                        st.image(img_url, use_container_width=True)
                    else:
                        st.markdown("<div style='height:120px; background:#f0f0f0; border-radius:8px; text-align:center; line-height:120px; color:#888;'>사진 없음</div>", unsafe_allow_html=True)

                    # 2. 식물 이름 (이 식물일 가능성)
                    plant_name = rec.get("plant_name", "식물 이름을 알 수 없어요")
                    confidence = rec.get("confidence", 0)
                    st.markdown(f"🌿 **{plant_name}** <span style='font-size:0.8rem; color:#666;'>({confidence}%)</span>", unsafe_allow_html=True)

                    # 3. 식물 건강 점수 (4단계 뱃지 적용)
                    health_score = rec.get("health_score", 0)
                    if health_score >= 80:
                        badge_class = "badge-healthy"
                        badge_text = "건강한 편이에요"
                    elif health_score >= 60:
                        badge_class = "badge-normal"
                        badge_text = "조금 살펴봐요"
                    elif health_score >= 40:
                        badge_class = "badge-warning"
                        badge_text = "관리가 필요해요"
                    else:
                        badge_class = "badge-danger"
                        badge_text = "도움이 필요해요"

                    st.markdown(f"<span class='plant-card-badge {badge_class}'>{health_score}점 ({badge_text})</span>", unsafe_allow_html=True)

                    # 4. 식물이 있는 곳
                    location_str = format_location_display(rec.get("location_name", ""), rec.get("latitude"), rec.get("longitude"))
                    st.caption(f"{location_str}")

                    # 5. 진단 일자
                    created_date = rec.get("created_at", "")[:10]
                    st.caption(f"{created_date}")

                    # 6. 카드 클릭 시 상세 모달 오픈 버튼
                    if st.button("**진단 결과 보기**", key=f"btn_detail_{rec['id']}", use_container_width=True):
                        show_detail_dialog(rec)

        # 🌟 10개씩 더보기 버튼 처리
        if len(records) < total_count:
            st.markdown("<br>", unsafe_allow_html=True)
            col_b1, col_b2, col_b3 = st.columns([1, 2, 1])
            with col_b2:
                if st.button(f"➕ 더보기 ({len(records)} / {total_count})", key="btn_load_more", use_container_width=True):
                    st.session_state["history_limit"] += PAGE_SIZE
                    st.rerun()

    except Exception as e:
        st.error(f"⚠️ **진단 기록을 불러오지 못했어요.** 잠시 후 다시 시도해주세요.: {e}")
