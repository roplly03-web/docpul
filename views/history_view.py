from datetime import datetime
import streamlit as st
from utils import supabase, format_location_display, sanitize_and_format_markdown
from utils import apply_global_styles

apply_global_styles()

PAGE_SIZE = 9

@st.dialog("닥풀 진단 결과")
def show_detail_dialog(rec):
    # ---------------------------------------------------------
    # 모달 내부 전용 스타일 지정
    # ---------------------------------------------------------
    st.markdown("""
        <style>
        .modal-info-box {
            padding: 4px 8px 14px 8px !important; /* 상 우 하 좌 패딩 완벽 통일 */
            margin: 0 !important;
            display: flex;
            flex-direction: column;
            gap: 10px; /* 각 항목 간의 간격 */
        }
        .modal-info-row {
            font-size: 0.85rem;
            color: #75777e;
            display: flex;
            align-items: center;
            line-height: 1.4;
        }
        .modal-info-label {
            font-size: 0.85rem;
            color: #75777e;
            font-weight: 400;
        }
        .modal-location-full, .modal-date-full {
            font-size: 0.85rem;
            color: #75777e;
            font-weight: 400;
            word-break: break-all;
        }

        </style>
    """, unsafe_allow_html=True)

    if rec.get("image_url"):
        st.image(rec["image_url"], use_container_width=True)
    
    plant_name = rec.get('plant_name', '식물 이름을 알 수 없어요')
    scientific_name = rec.get('scientific_name') or '학명을 알 수 없어요'
    confidence = rec.get('confidence', 0)

    st.markdown(f"""
        <div class="modal-title-wrap" style="margin-bottom: 12px;">
            <div class="modal-plant-name" style="font-size:1.2rem; font-weight: 600;">
                {plant_name}
            </div>
            <div class="modal-scientific-name" style="font-size:0.95rem; color: #75777e;">{scientific_name}</div>
        </div>
    """, unsafe_allow_html=True)
    
    unified_location = format_location_display(rec.get("location_name", ""), rec.get("latitude"), rec.get("longitude"))
    created_date = rec.get('created_at', '')[:10] if rec.get('created_at') else ''

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

    # 테두리 박스 내부 HTML 구조 깔끔하게 정돈
    with st.container(border=True):
        st.markdown(f"""
            <div class="modal-info-box">
                <div class="modal-info-row">
                    <span style="margin-right: 8px;">🌱</span>
                    <span class="plant-card-badge {badge_class}" style="margin: 0;">{health_score}점 ({status_text})</span>
                </div>
                <div class="modal-info-row">
                    <span style="margin-right: 8px;">✨</span>
                    <span class="modal-location-full">이 식물일 가능성</span>&nbsp;&nbsp;<span style="font-size: 0.95rem;"><b>{confidence} %</b></span>
                </div>
                <div class="modal-info-row">
                    <span style="margin-right: 8px;">📍</span>
                    <span class="modal-location-full">{unified_location}</span>
                </div>
                <div class="modal-info-row">
                    <span style="margin-right: 8px;">📅</span>
                    <span class="modal-date-full">{created_date}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    full_report_text = rec.get("full_report")
    if full_report_text:
        report_body = full_report_text.split("---", 1)[1] if "---" in full_report_text else full_report_text
        st.markdown(sanitize_and_format_markdown(report_body))
    else:
        st.info("**상세 진단 내용을 확인할 수 없어요.**")


def show_history_page():
    #st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
        <h4 style="line-height: 1.3; margin-bottom: 0px; font-weight: 500;">살펴본 식물을 모았어요
        </h4>
        <p style="font-size: 0.9rem; line-height: 1.0; color: #75777e; margin-top: 0px; font-weight: 400;">닥풀이 살펴본 식물과 결과를 다시 확인할 수 있어요.
        </p>
    """, unsafe_allow_html=True)

    st.divider()

    if not supabase:
        st.warning("**진단 기록을 불러오지 못했어요.** 잠시 후 다시 시도해주세요.")
        return

    if "history_limit" not in st.session_state:
        st.session_state["history_limit"] = PAGE_SIZE

    st.markdown("""
        <style>
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

        .history-location {
            font-size: 0.85rem;
            color: #75777e;
            font-weight: 400;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            display: block;
            width: 100%;
        }
        .history-date {
            font-size: 0.85rem;
            color: #75777e;
            font-weight: 400;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            display: block;
            width: 100%;
        }
        </style>
    """, unsafe_allow_html=True)

    try:
        # 1. 전체 데이터 개수
        count_res = (
            supabase.table("diagnosis_history")
            .select("id", count="exact")
            .neq("plant_name", "진단 불가")
            .gt("health_score", 0)
            .execute()
        )
        total_count = count_res.count if count_res.count else 0

        # 2. 데이터 조회
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

        col_count = 3 if st.session_state.get("is_desktop", True) else 2

        # 🌟 3. 10개(페이지) 단위 세션으로 컬럼 그룹화
        # 기존 카드 위치는 고정되고, 더보기로 불러온 10개만 그 밑에 신규 그룹으로 차곡차곡 쌓입니다.
        for page_start in range(0, len(records), PAGE_SIZE):
            page_records = records[page_start : page_start + PAGE_SIZE]
            cols = st.columns(col_count)

            for idx, rec in enumerate(page_records):
                target_col = cols[idx % col_count]
                with target_col:
                    with st.container(border=True):
                        # 원본 이미지 바로 사용 (속도 최상)
                        img_url = rec.get("image_url")
                        if img_url:
                            st.image(img_url, use_container_width=True)

                        plant_name = rec.get("plant_name", "식물 이름을 알 수 없어요")
                        confidence = rec.get("confidence", 0)
                        st.markdown(
                            f"<span style='font-size:1.1rem; font-weight:600'>{plant_name}</span> "
                            f"<span style='font-size:0.9rem; color:#75777e;'>({confidence}%)</span>",
                            unsafe_allow_html=True
                        )

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

                        location_str = format_location_display(rec.get("location_name", ""), rec.get("latitude"), rec.get("longitude"))
                        st.markdown(f"<div class='history-location'>{location_str}</div>", unsafe_allow_html=True)

                        created_date = rec.get("created_at", "")[:10]
                        st.markdown(f"<div class='history-date'>{created_date}</div>", unsafe_allow_html=True)
                        st.markdown("<br>", unsafe_allow_html=True)

                        if st.button("**진단 결과 보기**", key=f"btn_detail_{rec['id']}", use_container_width=True):
                            show_detail_dialog(rec)

        # 4. 더보기 버튼
        if len(records) < total_count:
            st.markdown("<br>", unsafe_allow_html=True)
            col_b1, col_b2, col_b3 = st.columns([1, 2, 1])
            with col_b2:
                if st.button(f"➕ 더보기 ({len(records)} / {total_count})", key="btn_load_more", use_container_width=True):
                    st.session_state["history_limit"] += PAGE_SIZE
                    st.rerun()

    except Exception as e:
        st.error(f"**진단 기록을 불러오지 못했어요.** 잠시 후 다시 시도해주세요.")
