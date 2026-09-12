from datetime import datetime
import streamlit as st
from utils import supabase, format_location_display, sanitize_and_format_markdown
from utils import apply_global_styles

# 페이지가 시작될 때 한 번만 호출
apply_global_styles()

PAGE_SIZE = 10

# 🌟 카드 클릭 시 열리는 상세 진단서 모달 팝업 (상세에서는 전체 내용이 다 보이도록 구성)
@st.dialog("닥풀 진단 결과")
def show_detail_dialog(rec):
    if rec.get("image_url"):
        st.image(rec["image_url"], use_container_width=True)
    
    plant_name = rec.get('plant_name', '식물 이름을 알 수 없어요')
    scientific_name = rec.get('scientific_name') or '학명을 알 수 없어요'
    confidence = rec.get('confidence', 0)

    # 모달 상단 이름 및 학명
    st.markdown(f"""
        <div class="modal-title-wrap">
            <div class="modal-plant-name"; style="font-size:1.2rem;">{plant_name} <span class="modal-confidence"; style="font-size:0.85rem; color: #75777e">&nbsp&nbsp&nbsp이 식물일 가능성&nbsp&nbsp</span><span class="modal-confidence"; style="font-size:0.95rem; color: #75777e">{confidence}%</span></div>
            <div class="modal-scientific-name" style="font-size:1.0rem; color: #75777e">{scientific_name}</div>
        </div>
    """, unsafe_allow_html=True)
    
    unified_location = format_location_display(rec.get("location_name", ""), rec.get("latitude"), rec.get("longitude"))
    created_date = rec.get('created_at', '')[:10] if rec.get('created_at') else ''

    # 점수에 따른 뱃지 텍스트 및 클래스 판별 (목록과 동일)
    health_score = rec.get('health_score', 0)
    if health_score >= 80:
        badge_class = "badge-healthy"
        status_text = "건강한 편이에요"
    elif health_score >= 60:
        badge_class = "badge-normal"
        status_text = "관찰이 필요해요"
    elif health_score >= 40:
        badge_class = "badge-warning"
        status_text = "관리가 필요해요"
    else:
        badge_class = "badge-danger"
        status_text = "도움이 필요해요"

    # 진단 핵심 정보 요약 박스 (상세에서는 말줄임 없이 전체 내용 다 노출)
    with st.container(border=True):
        st.markdown(f"""
            <div class="modal-info-row">🌱&nbsp&nbsp&nbsp<span class="plant-card-badge {badge_class}">{health_score}점 ({status_text})</span></div>
            <div class="modal-info-row">📍&nbsp&nbsp&nbsp<span class="modal-location-full">{unified_location}</span></div>
            <div class="modal-info-row">📅&nbsp&nbsp&nbsp<span class="modal-date-full">{created_date}</span></div>
        """, unsafe_allow_html=True)

    # 상단 여백 추가
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
        <p style="font-size: 0.9rem; line-height: 1.0; color: #75777e; margin-top: 0px; font-weight: 400;">닥풀이 살펴본 식물과 결과를 다시 확인할 수 있어요.
        </p>
    """, unsafe_allow_html=True)

    st.divider()

    if not supabase:
        st.warning("**진단 기록을 불러오지 못했어요.** 잠시 후 다시 시도해주세요.")
        return

    # 세션 상태 초기화 (더보기 누적 개수 관리)
    if "history_limit" not in st.session_state:
        st.session_state["history_limit"] = PAGE_SIZE

    # 모바일 2열 / PC 3열 쇼핑몰 스타일 CSS 카드 및 말줄임(ellipsis) 스타일 정의
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
                grid-template-columns: repeat(3, 1fr);
                gap: 20px;
            }
        }
        /* 건강 점수 뱃지 스타일 (목록/모달 공통) */
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

        /* 🌟 목록 카드 전용: 한 줄을 넘지 않고 말줄임표(...) 처리하는 CSS */
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
        
        /* 모달 전용 클래스 (말줄임 없이 전체 노출) */
        .modal-title-wrap { margin-bottom: 12px; }
        .modal-plant-name { font-size: 1.1rem; font-weight: bold; }
        .modal-confidence { font-size: 0.9rem; color: #75777e; font-weight: normal; }
        .modal-scientific-name { font-size: 0.85rem; color: #75777e; margin-top: 2px; }
        .modal-bold-text { font-weight: bold; }
        .modal-info-row { margin-bottom: 8px; font-size: 0.95rem; }
        .modal-location-full { font-size: 0.95rem; color: #333; }
        .modal-date-full { font-size: 0.95rem; color: #333; }
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
            st.info("아직 살펴본 식물이 없어요.")
            return

        # 반응형 컬럼 배치 (PC: 3열, 모바일: 2열)
        cols = st.columns([1, 1, 1] if st.session_state.get("is_desktop", True) else [1, 1])
        col_count = len(cols)

        for idx, rec in enumerate(records):
            target_col = cols[idx % col_count]
            
            with target_col:
                with st.container(border=True):
                    # 1. 첨부 이미지 (사진이 없으면 영역을 생성하지 않음)
                    img_url = rec.get("image_url")
                    if img_url:
                        st.image(img_url, use_container_width=True)

                    # 2. 식물 이름 (이 식물일 가능성)
                    plant_name = rec.get("plant_name", "식물 이름을 알 수 없어요")
                    confidence = rec.get("confidence", 0)
                    st.markdown(
                        f"<span style='font-size:1.1rem; font-weight:700'>{plant_name}</span> "
                        f"<span style='font-size:0.9rem; color:#75777e;'>({confidence}%)</span>",
                        unsafe_allow_html=True
                    )

                    # 3. 식물 건강 점수 (4단계 뱃지 적용)
                    health_score = rec.get("health_score", 0)
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

                    # 4. 식물이 있는 곳 (목록에서는 한 줄 말줄임 적용)
                    location_str = format_location_display(rec.get("location_name", ""), rec.get("latitude"), rec.get("longitude"))
                    st.markdown(f"<div class='history-location'>{location_str}</div>", unsafe_allow_html=True)

                    # 5. 진단 일자 (목록에서는 한 줄 말줄임 적용)
                    created_date = rec.get("created_at", "")[:10]
                    st.markdown(f"<div class='history-date'>{created_date}</div>", unsafe_allow_html=True)
                    st.markdown("<br>", unsafe_allow_html=True)

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
        st.error(f"**진단 기록을 불러오지 못했어요.** 잠시 후 다시 시도해주세요.")
