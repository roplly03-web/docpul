import streamlit as st
import streamlit.components.v1 as components
import json
from utils import supabase, format_location_display, apply_global_styles

# 페이지가 시작될 때 한 번만 호출
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
        # created_at 필드 추가 조회
        response = supabase.table("diagnosis_history") \
            .select("id, plant_name, health_score, location_name, latitude, longitude, image_url, created_at") \
            .not_.is_("latitude", "null") \
            .not_.is_("longitude", "null") \
            .order("created_at", desc=True) \
            .limit(100) \
            .execute()
        return response.data or []
    except Exception as e:
        st.error(f"식물 지도를 불러오지 못했어요. 잠시 후 다시 시도해주세요.")
        return []

def show_map_page():
    #st.markdown("<br>", unsafe_allow_html=True)
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

    processed_markers = []
    for r in records:
        score = r.get("health_score", 0)
        status_info = get_local_health_status(score)
        
        # 1. DB에 저장된 location_name과 좌표(lat, lon)를 utils의 format_location_display로 전달
        # 2. 동/읍/면/도로명까지만 가공된 주소를 가져옴
        raw_loc = r.get("location_name") or ""
        lat_val = r.get("latitude")
        lng_val = r.get("longitude")
        
        formatted_loc = format_location_display(raw_loc, lat_val, lng_val)
        
        created_date = r.get("created_at", "")[:10] if r.get("created_at") else ""
        
        processed_markers.append({
            "title": r.get("plant_name", "식물 이름을 알 수 없어요"),
            "score": score,
            "status_text": status_info["text"],
            "badge_class": status_info["badge_class"],
            "location": formatted_loc,  # 🌟 동/읍/면 단위로 정리된 주소 전달
            "created_date": created_date,
            "lat": lat_val,
            "lng": lng_val,
            "image": r.get("image_url", "")
        })

    markers_data = json.dumps(processed_markers, ensure_ascii=False)

    google_map_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
        <style>
            * {{ box-sizing: border-box; }}
            html, body {{ width:100%; height:100%; margin:0; padding:0; font-family: 'Pretendard', -apple-system, sans-serif; overflow: hidden; }}
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

            /* 🌟 history_view.py와 완벽히 동일하게 맞춘 스타일 클래스 */
            .info-box {{
                padding: 4px;
                width: 200px;
                font-family: inherit;
            }}
            
            .map-title {{
                font-size: 1.05rem;
                font-weight: 600;
                margin-bottom: 4px;
            }}

            .plant-card-badge {{
                display: inline-block;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 0.85rem;
                font-weight: bold;
                margin-bottom: 6px;
            }}
            .badge-healthy {{ background-color: #e6f4ea; color: #137333; }}
            .badge-normal {{ background-color: #e8f0fe; color: #1a73e8; }}
            .badge-warning {{ background-color: #fef7e0; color: #b06000; }}
            .badge-danger {{ background-color: #fce8e6; color: #c5221f; }}

            .map-location {{
                font-size: 0.85rem;
                color: #75777e;
                font-weight: 400;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                display: block;
                width: 100%;
                margin-bottom: 2px;
            }}

            .map-date {{
                font-size: 0.85rem;
                color: #75777e;
                font-weight: 400;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                display: block;
                width: 100%;
            }}

            .info-img {{
                width: 100%;
                height: 110px;
                object-fit: cover;
                border-radius: 6px;
                margin-top: 8px;
            }}
        </style>
        <script src="https://maps.googleapis.com/maps/api/js?key={google_maps_key.strip()}&libraries=places&language=ko"></script>
    </head>
    <body>
        <div id="map-wrapper">
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

                var input = document.getElementById('pac-input');
                var autocomplete = new google.maps.places.Autocomplete(input);
                autocomplete.bindTo('bounds', map);

                autocomplete.addListener('place_changed', function() {{
                    var place = autocomplete.getPlace();
                    if (!place.geometry || !place.geometry.location) return;

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

                    /* 🌟 히스토리 카드의 구조와 클래스를 동일하게 적용한 HTML */
                    var contentStr = 
                        '<div class="info-box">' +
                            '<div class="map-title">' + item.title + '</div>' +
                            '<span class="plant-card-badge ' + item.badge_class + '">' + item.score + '점 (' + item.status_text + ')</span>' +
                            '<div class="map-location">' + item.location + '</div>' +
                            '<div class="map-date">' + item.created_date + '</div>' +
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

    components.html(google_map_html, height=550)
