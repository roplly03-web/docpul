import streamlit as st
import streamlit.components.v1 as components
import json
from collections import defaultdict
from utils import supabase, format_location_display, apply_global_styles

apply_global_styles()

st.session_state["last_active_tab"] = "other"

def get_local_health_status(score: int):
    try:
        score = int(score)
    except (ValueError, TypeError):
        score = 0

    if score >= 80:
        return {"text": "건강한 편이에요", "badge_class": "badge-healthy"}
    elif score >= 60:
        return {"text": "관찰이 필요해요", "badge_class": "badge-normal"}
    elif score >= 40:
        return {"text": "관리가 필요해요", "badge_class": "badge-warning"}
    else:
        return {"text": "도움이 필요해요", "badge_class": "badge-danger"}

def get_diagnosis_history():
    if not supabase:
        return []
    try:
        response = supabase.table("diagnosis_history") \
            .select("id, plant_name, health_score, location_name, latitude, longitude, image_url, created_at") \
            .not_.is_("latitude", "null") \
            .not_.is_("longitude", "null") \
            .order("created_at", desc=True) \
            .limit(100) \
            .execute()
        return response.data or []
    except Exception as e:
        st.error("식물 지도를 불러오지 못했어요. 잠시 후 다시 시도해주세요.")
        return []

def show_map_page():
    st.markdown("""
        <h4 style="line-height: 1.3; margin-bottom: 0px; font-weight: 500;">주변 식물을 지도에서 살펴봐요
        </h4>
        <p style="font-size: 0.9rem; line-height: 1.0; color: #75777e; margin-top: 0px; font-weight: 400;">닥풀이 살펴본 식물이 어디에 있는지 지도에서 볼 수 있어요.
        </p>
    """, unsafe_allow_html=True)

    st.divider()

    google_maps_key = st.secrets.get("GOOGLE_MAPS_API_KEY")
    if not google_maps_key:
        st.error("지도를 불러오지 못했어요. 잠시 후 다시 시도해주세요.")
        return

    records = get_diagnosis_history()

    default_lat, default_lon = 37.5665, 126.9780
    if records:
        default_lat = records[0]["latitude"]
        default_lon = records[0]["longitude"]

    grouped_markers = defaultdict(list)

    for r in records:
        score = r.get("health_score", 0)
        status_info = get_local_health_status(score)
        
        raw_loc = r.get("location_name") or ""
        lat_val = r.get("latitude")
        lng_val = r.get("longitude")
        
        if lat_val is None or lng_val is None:
            continue

        formatted_loc = format_location_display(raw_loc, lat_val, lng_val)
        created_date = r.get("created_at", "")[:10] if r.get("created_at") else ""
        
        plant_item = {
            "id": r.get("id"),
            "title": r.get("plant_name", "식물 이름을 알 수 없어요"),
            "score": score,
            "status_text": status_info["text"],
            "badge_class": status_info["badge_class"],
            "location": formatted_loc,
            "created_date": created_date,
            "lat": float(lat_val),
            "lng": float(lng_val),
            "image": r.get("image_url", "")
        }

        coord_key = f"{round(float(lat_val), 3)}_{round(float(lng_val), 3)}"
        grouped_markers[coord_key].append(plant_item)

    final_marker_groups = list(grouped_markers.values())
    markers_data = json.dumps(final_marker_groups, ensure_ascii=False)

    google_map_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            * {{ box-sizing: border-box; }}
            html, body {{ width:100%; height:100%; margin:0; padding:0; font-family: 'Pretendard', -apple-system, sans-serif; background-color: #f8f9fa; overflow: hidden; }}
            
            #main-container {{ display: flex; flex-direction: column; height: 650px; }}
            
            #map-wrapper {{ position: relative; width:100%; height: 300px; flex-shrink: 0; }}
            #map {{ width:100%; height:100%; background-color: #e9ecef; }}
            
            .search-input {{
                position: absolute;
                top: 10px;
                left: 10px;
                z-index: 10;
                width: 240px;
                padding: 8px 12px;
                font-size: 13px;
                border: 1px solid #ccc;
                border-radius: 8px;
                box-shadow: 0 2px 6px rgba(0,0,0,0.15);
                outline: none;
                background-color: #fff;
            }}

            .split-container {{
                height: 350px;
                padding: 12px;
                background: #ffffff;
                border-top: 1px solid #e9ecef;
                display: flex;
                flex-direction: column;
            }}
            .split-header {{
                font-size: 0.9rem;
                font-weight: 600;
                margin-bottom: 10px;
                color: #343a40;
            }}
            .split-list {{
                flex-grow: 1;
                overflow-y: auto;
                display: flex;
                flex-direction: column;
                gap: 8px;
                padding-right: 4px;
            }}
            
            .list-card {{
                display: flex;
                align-items: center;
                gap: 12px;
                background: #fff;
                border: 1px solid #e9ecef;
                border-radius: 8px;
                padding: 10px;
                cursor: pointer;
                transition: all 0.2s;
            }}
            .list-card:hover, .list-card.selected {{
                background: #f1f3f5;
                border-color: #5ac451;
            }}

            .card-img {{ width: 55px; height: 55px; border-radius: 6px; object-fit: cover; flex-shrink: 0; }}
            .card-info {{ flex-grow: 1; min-width: 0; }}
            .card-title {{ font-size: 0.9rem; font-weight: 600; color: #212529; margin-bottom: 2px; }}
            .card-sub {{ font-size: 0.75rem; color: #868e96; margin-top: 4px; }}

            .plant-card-badge {{
                display: inline-block;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 0.75rem;
                font-weight: bold;
            }}
            .badge-healthy {{ background-color: #e6f4ea; color: #137333; }}
            .badge-normal {{ background-color: #e8f0fe; color: #1a73e8; }}
            .badge-warning {{ background-color: #fef7e0; color: #b06000; }}
            .badge-danger {{ background-color: #fce8e6; color: #c5221f; }}
        </style>
        <script src="https://maps.googleapis.com/maps/api/js?key={google_maps_key.strip()}&libraries=places&language=ko"></script>
    </head>
    <body>
        <div id="main-container">
            <div id="map-wrapper">
                <input id="pac-input" class="search-input" type="text" placeholder="🔍 장소 검색..." />
                <div id="map"></div>
            </div>

            <div class="split-container">
                <div class="split-header">📋 주변 식물 목록</div>
                <div id="split-list" class="split-list"></div>
            </div>
        </div>

        <script>
            var markerGroups = {markers_data};
            var map;
            
            // 🌟 무한 스크롤(오토 스크롤) 관련 변수
            var PAGE_SIZE = 10;
            var currentIndex = 0;
            var allItems = [];

            function buildCardHtml(item) {{
                var imgTag = item.image ? '<img src="' + item.image + '" class="card-img"/>' : '';
                return `
                    ${{imgTag}}
                    <div class="card-info">
                        <div class="card-title">${{item.title}}</div>
                        <span class="plant-card-badge ${{item.badge_class}}">${{item.score}}점 (${{item.status_text}})</span>
                        <div class="card-sub">${{item.location}} · ${{item.created_date}}</div>
                    </div>
                `;
            }}

            function createCardElement(item) {{
                var card = document.createElement('div');
                card.className = 'list-card';
                card.id = 'card-' + item.id;
                card.innerHTML = buildCardHtml(item);
                
                card.onclick = function() {{
                    map.setZoom(16);
                    map.panTo({{ lat: item.lat, lng: item.lng }});
                    document.querySelectorAll('.list-card').forEach(c => c.classList.remove('selected'));
                    card.classList.add('selected');
                }};
                return card;
            }}

            // 🌟 다음 10개 카드 덧붙이기 함수
            function appendNextPage() {{
                var listContainer = document.getElementById('split-list');
                var nextItems = allItems.slice(currentIndex, currentIndex + PAGE_SIZE);

                nextItems.forEach(function(item) {{
                    var card = createCardElement(item);
                    listContainer.appendChild(card);
                }});

                currentIndex += PAGE_SIZE;
            }}

            function initList() {{
                allItems = [];
                markerGroups.forEach(function(group) {{
                    group.forEach(function(item) {{
                        allItems.push(item);
                    }});
                }});

                // 초기 10개만 먼저 로드
                appendNextPage();

                // 🌟 스크롤 바닥 감지 (오토 스크롤 이벤트 등록)
                var listContainer = document.getElementById('split-list');
                listContainer.addEventListener('scroll', function() {{
                    if (listContainer.scrollTop + listContainer.clientHeight >= listContainer.scrollHeight - 50) {{
                        if (currentIndex < allItems.length) {{
                            appendNextPage();
                        }}
                    }}
                }});
            }}

            function highlightAndScrollTo(item) {{
                var el = document.getElementById('card-' + item.id);
                
                // 만약 아직 오토 스크롤로 로드되지 않은 카드라면, 찾아질 때까지 추가 로드
                while (!el && currentIndex < allItems.length) {{
                    appendNextPage();
                    el = document.getElementById('card-' + item.id);
                }}

                if (el) {{
                    document.querySelectorAll('.list-card').forEach(c => c.classList.remove('selected'));
                    el.classList.add('selected');
                    el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                }}
            }}

            function initMap() {{
                var centerLoc = {{ lat: {default_lat}, lng: {default_lon} }};
                
                map = new google.maps.Map(document.getElementById('map'), {{
                    zoom: 14,
                    center: centerLoc,
                    mapTypeControl: false,
                    zoomControl: true,
                    clickableIcons: false // 🌟 이 옵션을 추가하면 기본 장소 클릭 및 새창 팝업이 전면 차단됩니다!
                }});

                var input = document.getElementById('pac-input');
                var autocomplete = new google.maps.places.Autocomplete(input);
                autocomplete.bindTo('bounds', map);

                autocomplete.addListener('place_changed', function() {{
                    var place = autocomplete.getPlace();
                    if (!place.geometry || !place.geometry.location) return;
                    if (place.geometry.viewport) map.fitBounds(place.geometry.viewport);
                    else {{ map.setCenter(place.geometry.location); map.setZoom(16); }}
                }});

                markerGroups.forEach(function(group) {{
                    if (group.length === 0) return;
                    
                    var rep = group[0];
                    var marker = new google.maps.Marker({{
                        position: {{ lat: rep.lat, lng: rep.lng }},
                        map: map,
                        title: group.length > 1 ? rep.title + ' 외 ' + (group.length - 1) + '건' : rep.title,
                        label: group.length > 1 ? {{ text: String(group.length), color: "#ffffff", fontWeight: "bold" }} : null
                    }});

                    marker.addListener('click', function() {{
                        map.panTo({{ lat: rep.lat, lng: rep.lng }});
                        highlightAndScrollTo(rep);
                    }});
                }});

                initList();
            }}

            window.onload = initMap;
        </script>
    </body>
    </html>
    """

    components.html(google_map_html, height=650)
