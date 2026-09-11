import streamlit as st
import streamlit.components.v1 as components
import json
from utils import supabase
from utils import apply_global_styles

# 페이지가 시작될 때 한 번만 호출
apply_global_styles()


# 다른 페이지 함수(예: show_map_page, show_history_page 등) 실행 직후 추가
st.session_state["last_active_tab"] = "other"  # 또는 각 페이지 이름

def get_local_health_status(score: int):
    try:
        score = int(score)
    except (ValueError, TypeError):
        score = 0

    if score >= 80:
        return {"text": "건강한 편이에요", "score_class": "healthy"}
    elif score >= 60:
        return {"text": "조금 살펴봐요", "score_class": "normal"}
    elif score >= 40:
        return {"text": "관리가 필요해요", "score_class": "warning"}
    else:
        return {"text": "도움이 필요해요", "score_class": "danger"}

def get_diagnosis_history():
    if not supabase:
        return []
    try:
        response = supabase.table("diagnosis_history") \
            .select("id, plant_name, health_score, location_name, latitude, longitude, image_url") \
            .not_.is_("latitude", "null") \
            .not_.is_("longitude", "null") \
            .order("created_at", desc=True) \
            .limit(100) \
            .execute()
        return response.data or []
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return []

def show_map_page():
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
        <h4 style="line-height: 1.3; margin-bottom: 0px; font-weight: 500;">우리 주변 식물을 지도에서 살펴봐요
        </h4>
        <p style="font-size: 0.9rem; line-height: 1.0; color: #75777e; margin-top: 0px; font-weight: 400;">닥풀에서 살펴본 식물들을 지도에서 만나볼 수 있어요.
        </p>
    """, unsafe_allow_html=True)

    st.divider()

    # 1. Google Maps API Key 확인
    google_maps_key = st.secrets.get("GOOGLE_MAPS_API_KEY")
    if not google_maps_key:
        st.error("⚠️ Secrets 설정에서 `GOOGLE_MAPS_API_KEY`를 찾을 수 없습니다.")
        return

    records = get_diagnosis_history()

    default_lat, default_lon = 37.5665, 126.9780
    if records:
        default_lat = records[0]["latitude"]
        default_lon = records[0]["longitude"]

    processed_markers = []
    for r in records:
        score = r.get("health_score", 0)
        status_info = get_local_health_status(score)
        
        processed_markers.append({
            "title": r.get("plant_name", "식물 이름을 알 수 없어요"),
            "score": score,
            "status_text": status_info["text"],
            "score_class": status_info["score_class"],
            "location": r.get("location_name", "위치를 알 수 없어요"),
            "lat": r["latitude"],
            "lng": r["longitude"],
            "image": r.get("image_url", "")
        })

    markers_data = json.dumps(processed_markers, ensure_ascii=False)

    # 2. Google Maps HTML / JS (Places API 연결)
    google_map_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
        <style>
            * {{ box-sizing: border-box; }}
            html, body {{ width:100%; height:100%; margin:0; padding:0; font-family: 'Pretendard', sans-serif; overflow: hidden; }}
            #map-wrapper {{ position: relative; width:100%; height:550px; }}
            #map {{ width:100%; height:100%; min-height: 550px; background-color: #e9ecef; }}
            
            /* 검색창 스타일링 */
            .search-input {{
                position: absolute;
                top: 10px;
                left: 10px;
                z-index: 10;
                width: 280px;
                padding: 10px 14px;
                font-size: 14px;
                border: 1px solid #ccc;
                border-radius: 8px;
                box-shadow: 0 2px 6px rgba(0,0,0,0.2);
                outline: none;
                background-color: #fff;
            }}

            .info-box {{ padding: 10px; border-radius: 8px; width: 220px; font-size: 13px; line-height: 1.4; }}
            .info-title {{ font-weight: bold; font-size: 15px; color: #1b5e20; margin-bottom: 4px; }}
            .info-score {{ font-weight: bold; margin-bottom: 4px; }}
            .info-score.healthy {{ color: #137333; }}
            .info-score.normal {{ color: #1a73e8; }}
            .info-score.warning {{ color: #b06000; }}
            .info-score.danger {{ color: #c5221f; }}
            .info-img {{ width: 100%; height: 110px; object-fit: cover; border-radius: 6px; margin-top: 6px; }}
        </style>
        <!-- 🌟 libraries=places 추가하여 Places API 활성화 -->
        <script src="https://maps.googleapis.com/maps/api/js?key={google_maps_key.strip()}&libraries=places&language=ko"></script>
    </head>
    <body>
        <div id="map-wrapper">
            <!-- 🌟 지도 내 장소 검색 입력창 -->
            <input id="pac-input" class="search-input" type="text" placeholder="🔍 지도에서 장소 검색..." />
            <div id="map"></div>
        </div>

        <script>
            function initMap() {{
                var centerLoc = {{ lat: {default_lat}, lng: {default_lon} }};
                
                var map = new google.maps.Map(document.getElementById('map'), {{
                    zoom: 14,
                    center: centerLoc,
                    mapTypeControl: true,
                    mapTypeControlOptions: {{
                        style: google.maps.MapTypeControlStyle.HORIZONTAL_BAR,
                        position: google.maps.ControlPosition.TOP_RIGHT
                    }}
                }});

                // 🌟 Places Autocomplete 검색 연동
                var input = document.getElementById('pac-input');
                var autocomplete = new google.maps.places.Autocomplete(input);
                autocomplete.bindTo('bounds', map);

                autocomplete.addListener('place_changed', function() {{
                    var place = autocomplete.getPlace();
                    if (!place.geometry || !place.geometry.location) {{
                        return;
                    }}

                    if (place.geometry.viewport) {{
                        map.fitBounds(place.geometry.viewport);
                    }} else {{
                        map.setCenter(place.geometry.location);
                        map.setZoom(16);
                    }}
                }});

                var markersData = {markers_data};
                var activeInfoWindow = null;

                markersData.forEach(function(item) {{
                    var pos = {{ lat: parseFloat(item.lat), lng: parseFloat(item.lng) }};
                    
                    var marker = new google.maps.Marker({{
                        position: pos,
                        map: map,
                        title: item.title
                    }});

                    var imgTag = item.image ? '<img src="' + item.image + '" class="info-img" />' : '';

                    var contentStr = 
                        '<div class="info-box">' +
                            '<div class="info-title">🌿 ' + item.title + '</div>' +
                            '<div class="info-score ' + item.score_class + '">' + item.score + '점 (' + item.status_text + ')</div>' +
                            '<div>' + item.location + '</div>' +
                            imgTag +
                        '</div>';

                    var infowindow = new google.maps.InfoWindow({{
                        content: contentStr
                    }});

                    marker.addListener('click', function() {{
                        if (activeInfoWindow) activeInfoWindow.close();
                        infowindow.open(map, marker);
                        activeInfoWindow = infowindow;
                    }});
                }});
            }}

            window.onload = initMap;
        </script>
    </body>
    </html>
    """

    components.html(google_map_html, height=600)
