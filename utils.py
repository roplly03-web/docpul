import os
import time
import re
import io
import requests
from PIL import Image, ExifTags
from PIL.ExifTags import TAGS, GPSTAGS
import streamlit as st
from google import genai
from google.genai import types
from google.genai.errors import APIError
from supabase import create_client, Client

def apply_global_styles():
    """잔상 없이 아주 빠르고 깔끔하게 사라지도록 설정"""
    st.markdown("""
        <style>
            /* 0.1초 만에 아주 빠르게 사라지게 만들어 잔상과 툭 끊기는 현상 동시 해결 */
            div[data-testid="stVerticalBlock"], 
            div.element-container, 
            div.stButton {
                transition: opacity 0.1s ease-out !important;
                animation: none !important;
            }
        </style>
    """, unsafe_allow_html=True)


# ==========================================
# 1. DB & API Initialization
# ==========================================
@st.cache_resource
def init_supabase() -> Client:
    # 안전하게 st.secrets에서 값 가져오기 (없으면 빈 문자열)
    url = st.secrets.get("SUPABASE_URL", "").strip()
    key = st.secrets.get("SUPABASE_KEY", "").strip()
    
    if not url or not key:
        # 배포 환경에서 키가 누락된 경우 경고를 띄워 원인 파악 도움
        st.warning("⚠️ Streamlit Secrets에 SUPABASE_URL 또는 SUPABASE_KEY가 설정되지 않았거나 비어 있습니다.")
        return None
        
    try:
        return create_client(url, key)
    except Exception as e:
        st.error(f"잠시 문제가 생겼어요. 다시 시도해 주세요.")
        return None

supabase = init_supabase()

@st.cache_resource
def get_gemini_api_keys():
    keys = []
    try:
        for k, v in st.secrets.items():
            if k.startswith("GEMINI_API_KEY"):
                keys.append(v)
    except Exception:
        pass
    return list(dict.fromkeys([k for k in keys if k]))

GEMINI_API_KEYS = get_gemini_api_keys()


# ==========================================
# IP 기반 위치 추정 (GPS 실패/타임아웃 시 백업용)
# ==========================================
def get_location_by_ip():
    """
    공인 IP를 기반으로 대략적인 위치 정보(위도, 경도, 도시, 지역)를 조회합니다.
    """
    try:
        # 무료로 공인 IP 위치를 제공하는 API 활용 (타임아웃 3초 설정)
        response = requests.get("https://ipapi.co/json/", timeout=3)
        if response.status_code == 200:
            data = response.json()
            lat = data.get("latitude")
            lon = data.get("longitude")
            
            if lat and lon:
                return {
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "city": data.get("city", ""),
                    "region": data.get("region", ""),
                    "country": data.get("country_name", ""),
                    "source": "ip"
                }
    except Exception as e:
        print(f"IP Geolocation Error: {e}")
    
    return None

# ==========================================
# Google Places Text Search (장소/키워드 검색)
# ==========================================
@st.cache_data(ttl=3600, show_spinner=False)
def search_google_places(query: str):
    if not query:
        return []
    
    google_key = st.secrets.get("GOOGLE_MAPS_API_KEY")
    if not google_key:
        st.error("❌ GOOGLE_MAPS_API_KEY가 설정되지 않았습니다.")
        return []

    url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query={query}&language=ko&key={google_key}"
    
    try:
        res = requests.get(url, timeout=3.0)
        if res.status_code == 200:
            data = res.json()
            status = data.get("status")
            
            # API 호출 결과가 OK가 아닐 경우 원인 출력
            if status != "OK" and status != "ZERO_RESULTS":
                st.warning(f"⚠️ Google API 응답 상태: {status} ({data.get('error_message', '')})")
            
            if status == "OK" and data.get("results"):
                places = []
                for item in data["results"][:5]:
                    loc = item["geometry"]["location"]
                    name = item.get("name", "")
                    address = item.get("formatted_address", "")
                    
                    label = f"{name} ({address})" if name and address and name not in address else (address or name)
                    
                    places.append({
                        "label": label,
                        "lat": loc["lat"],
                        "lon": loc["lng"]
                    })
                return places
    except Exception as e:
        st.error(f"장소를 찾지 못했어요. 잠시 후 다시 시도해 주세요.")
    return []
    
# ==========================================
# Google Maps Geocoding 역지오코딩
# ==========================================
@st.cache_data(ttl=86400, show_spinner=False)
def get_address_from_coords(lat: float, lon: float):
    if not lat or not lon:
        return None
        
    google_key = st.secrets.get("GOOGLE_MAPS_API_KEY")
    if not google_key:
        return None

    # Google Geocoding API (한글 주소 응답 설정)
    url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lon}&language=ko&key={google_key}"
    
    try:
        res = requests.get(url, timeout=3.0)
        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "OK" and data.get("results"):
                # 가장 상세하고 깔끔한 formatted_address 반환
                return data["results"][0]["formatted_address"]
    except Exception:
        pass
    return None

def format_location_display(loc_name: str, lat: float, lon: float) -> str:
    addr = get_address_from_coords(lat, lon) if lat and lon else None
    
    if addr:
        return addr
    elif loc_name:
        return loc_name
    elif lat and lon:
        return f"{lat:.4f}, {lon:.4f}"
    return "위치 정보 없음"

# ==========================================
# 안정적인 EXIF GPS 추출 (문자열/숫자 ID 통합 버전)
# ==========================================
def convert_to_degrees(value):
    try:
        if value is None or isinstance(value, (str, bytes, float, int)):
            return None
        if not hasattr(value, "__iter__"):
            return None

        val_list = []
        for item in value:
            if item is None or (isinstance(item, float) and str(item).lower() == 'nan'):
                return None
                
            if hasattr(item, "numerator") and hasattr(item, "denominator"):
                if item.denominator == 0:
                    return None
                val_list.append(float(item.numerator) / float(item.denominator))
            elif isinstance(item, tuple) and len(item) == 2:
                if item[1] == 0:
                    return None
                val_list.append(float(item[0]) / float(item[1]))
            else:
                val_list.append(float(item))
                
        if len(val_list) < 3:
            return None
            
        d = val_list[0]
        m = val_list[1]
        s = val_list[2]
        return d + (m / 60.0) + (s / 3600.0)
    except Exception:
        return None

def extract_gps_from_image(image):
    try:
        exif = image.getexif()
        if not exif:
            return None, None

        gps_info = None
        try:
            gps_info = exif.get_ifd(ExifTags.IFD.GPSInfo)
        except Exception:
            pass

        if not gps_info:
            for tag_id in [34853, 0x8825]:
                if tag_id in exif:
                    gps_info = exif.get(tag_id)
                    break

        if not gps_info:
            return None, None

        # 문자열 키와 표준 숫자 ID(2: 위도, 1: 위도참조, 4: 경도, 3: 경도참조)를 모두 허용
        lat = gps_info.get(2) or gps_info.get("GPSLatitude")
        lat_ref = gps_info.get(1) or gps_info.get("GPSLatitudeRef")
        lon = gps_info.get(4) or gps_info.get("GPSLongitude")
        lon_ref = gps_info.get(3) or gps_info.get("GPSLongitudeRef")

        if not all([lat, lat_ref, lon, lon_ref]):
            return None, None

        lat_val = convert_to_degrees(lat)
        lon_val = convert_to_degrees(lon)

        if lat_val is None or lon_val is None:
            return None, None

        if isinstance(lat_ref, bytes):
            lat_ref = lat_ref.decode(errors="ignore")
        if isinstance(lon_ref, bytes):
            lon_ref = lon_ref.decode(errors="ignore")

        if str(lat_ref).upper() != "N":
            lat_val = -lat_val

        if str(lon_ref).upper() != "E":
            lon_val = -lon_val

        return round(lat_val, 6), round(lon_val, 6)

    except Exception:
        return None, None
        
# ==========================================
# 한자 변환
# ==========================================
def clean_chinese_characters(text: str) -> str:
    if not text:
        return ""
    
    hanja_map = {
        "蒸": "증", "葉": "엽", "根": "근", "病": "병", "害": "해",
        "水": "수", "木": "목", "樹": "수", "枝": "지", "幹": "간",
        "花": "화", "果": "과", "菌": "균", "蟲": "충"
    }
    
    for hanja, kor in hanja_map.items():
        text = text.replace(hanja, kor)
        
    text = re.sub(r'[\u4e00-\u9fff]', '', text)
    return text

def save_to_supabase(image_bytes, file_name, sci_name, plant_name, health_score, confidence, lat, lon, loc_name, report, symptoms="", details="", urgent=""):
    if not supabase:
        st.error("❌ Supabase 클라이언트가 연결되지 않았습니다.")
        return None
    try:
        time_prefix = int(time.time())
        clean_name = re.sub(r'[^a-zA-Z0-9._-]', '_', file_name)
        storage_path = f"diagnoses/{time_prefix}_{clean_name}.jpg"
        
        supabase.storage.from_("tree-images").upload(
            path=storage_path,
            file=image_bytes,
            file_options={"content-type": "image/jpeg"}
        )
        
        public_url = supabase.storage.from_("tree-images").get_public_url(storage_path)

        data = {
            "scientific_name": sci_name or "학명을 알 수 없어요",
            "plant_name": plant_name or "식물 이름을 알 수 없어요",
            "health_score": int(health_score) if health_score else 0,
            "confidence": int(confidence) if confidence else 0,
            "latitude": float(lat) if lat else None,
            "longitude": float(lon) if lon else None,
            "location_name": loc_name or "",
            "image_url": public_url,
            "full_report": report or "",
            "symptoms": symptoms or "",
            "diagnosis_details": details or "",
            "urgent_action": urgent or ""
        }
        
        supabase.table("diagnosis_history").insert(data).execute()
        return public_url

    except Exception as e:
        st.error(f"❌ Supabase 저장 실패 상세 원인: {type(e).__name__} - {str(e)}")
        return None

def sanitize_and_format_markdown(text):
    if not text:
        return ""
    text = clean_chinese_characters(text)
    clean_text = text.replace("~", " 에서 ")
    clean_text = re.sub(r'\n(?!\n)', '\n\n', clean_text)
    return clean_text

def parse_primary_scientific_name(text):
    if not text:
        return None
    matches = re.findall(r'\b([A-Z][a-z]{2,}\s+(?:[×x]\s+)?[a-z]{2,}(?:\s+\'[^\']+\')?)\b', text)
    return matches[0] if matches else None

# ==========================================
# 3. 닥풀 AI 진단
# ==========================================
def call_gemini_structured_diagnosis(img_bytes, location_name=None, lat=None, lon=None, datetime_str=None):
    try:
        if not img_bytes:
            return {"status": "ERROR", "message": "전달된 이미지 데이터가 없습니다."}

        loc_info = f"{location_name} (위도: {lat}, 경도: {lon})" if lat and lon else (location_name or "위치 정보 미지정")
        time_info = datetime_str or "시점 정보 미지정"

        prompt = f"""
당신은 따뜻하고 전문적인 AI 식물주치의 '닥풀'입니다.

제시된 식물 사진을 자세히 살펴보고, 사진에서 확인되는 특징과 검사 요청 위치 및 시점 정보를 종합하여 식물의 종류, 현재 상태, 이상 증상, 병해충 가능성 및 관리 방법을 판단하세요.

일반 사용자가 이해하기 쉬운 자연스러운 한국어로 작성하세요.
불필요하게 어려운 전문 용어는 피하고, 전문 용어가 필요한 경우에는 이해하기 쉬운 표현을 함께 사용하세요.
학명은 공식적인 라틴어 학명을 그대로 사용하세요.

사진이나 제공된 정보만으로 확인할 수 없는 내용은 사실처럼 단정하지 마세요.
판단이 불확실한 경우에는 불확실성을 명확하게 표현하고, 가능한 원인은 가능성이 높은 순서로 설명하세요.


==================================================
[진단 환경 정보]
==================================================

식물이 있는 곳: {loc_info}
사진을 찍은 시점: {time_info}

사진에서 확인되는 정보와 위의 위치 및 시점 정보를 함께 고려하세요.

특히 다음 정보를 진단에 반영하세요.

- 해당 지역의 기후와 환경 특성
- 현재 계절과 시점에 나타날 수 있는 생육 변화
- 해당 지역과 시기에 발생 가능성이 높은 병해충
- 햇빛, 통풍, 온도, 습도 등 식물이 자라는 환경의 영향
- 사진에서 확인되는 증상과 지역 및 계절적 환경 사이의 연관성

단, 위치나 시점 정보만을 근거로 병해충이나 특정 원인을 단정하지 마세요.
사진을 자세히 살펴보고,
사진에서 확인되는 특징과 식물이 있는 곳 및 사진을 찍은 시점의 정보를 함께 고려하여
식물의 종류, 현재 상태, 이상 증상, 병해충 가능성 및 관리 방법을 살펴보세요.


==================================================
[식물 여부 및 예외 처리]
==================================================

먼저 업로드된 사진이 식물 또는 식물에 피해를 주는 병해충을 확인할 수 있는 사진인지 판단하세요.

다음과 같은 경우에는 정상 진단을 하지 마세요.

- 식물과 관계없는 사진인 경우
- 식물인지 판단하기 어려운 사진인 경우
- 사진이 지나치게 흐리거나 어두워 식물의 특징을 확인하기 어려운 경우
- 식물이나 병해충으로 판단할 만한 특징을 찾을 수 없는 경우

위와 같은 경우에는 아래의 예외 형식만 출력하세요.


==================================================
[비식물 예외 출력 형식]
==================================================

### 닥풀 AI 진단 결과

#### 식물을 확인하지 못했어요

업로드해 주신 사진에서 식물이나 병해충으로 판단할 만한 특징을 찾지 못했어요.

식물 전체가 잘 보이고, 잎이나 줄기 등 상태를 확인할 수 있는 사진으로 다시 올려주세요.

예외 결과에서는 추정 식물, 학명, 이 식물일 가능성, 식물 건강 점수 및 상세 진단 리포트를 출력하지 마세요.


==================================================
[정상 진단의 기본 정보]
==================================================

식물 또는 병해충을 정상적으로 확인할 수 있는 경우에만 아래 5개 항목을 가장 먼저 출력하세요.

■ 추정 식물:
■ 학명:
■ 이 식물일 가능성:
■ 식물 건강 점수:
■ 닥풀의 한마디:

위 5개 항목의 제목과 순서를 변경하거나 생략하지 마세요.

각 항목에는 실제 진단 결과만 작성하세요.
대괄호, placeholder, 설명 문구 또는 예시를 출력하지 마세요.


[추정 식물]

사진에서 확인되는 형태적 특징을 바탕으로 가장 가능성이 높은 식물의 일반적인 한국 이름을 작성하세요.

병해충을 식별한 경우에는 병해충의 이름을 작성하세요.

정확한 식물 종류를 판단하기 어려운 경우에는 특정 종으로 억지로 단정하지 말고 다음 문구를 사용하세요.

식물 이름을 알 수 없어요


[학명]

식물의 종류를 신뢰할 수 있는 수준으로 식별할 수 있는 경우에만 공식적인 라틴어 학명을 작성하세요.

정확한 학명을 판단하기 어려운 경우에는 다음 문구를 사용하세요.

학명을 알 수 없어요


[이 식물일 가능성]

사진에서 확인되는 형태적 특징을 기준으로 추정 식물이 맞을 가능성을 0점부터 100점 사이의 정수로 판단하세요.

사진에서 식별 근거가 충분한 경우에는 높은 값을 사용할 수 있습니다.
식별 근거가 부족하거나 비슷한 식물이 많아 구분하기 어려운 경우에는 낮은 값을 사용하세요.

가능성이 낮은데 임의로 높은 값을 주지 마세요.
사진의 품질이나 촬영 범위 때문에 식별이 어려운 경우에도 이를 반영하세요.


==================================================
[식물 건강 점수 판단 기준]
==================================================

식물 건강 점수는 현재 사진에서 확인할 수 있는 식물의 전반적인 상태를 0점부터 100점까지 평가한 값입니다.

사진에서 확인할 수 있는 상태를 가장 중요하게 판단하고, 검사 요청 위치와 시점 정보는 현재 상태를 해석하는 보조적인 맥락으로 사용하세요.

다음 세 가지 요소를 종합하여 최종 점수를 판단하세요.

1. 현재 상태 및 손상 정도: 50점

잎, 줄기, 꽃, 열매 등의 상태를 평가하세요.
변색, 시듦, 반점, 잎마름, 손상, 뒤틀림, 낙엽, 생장 상태 등 사진에서 확인되는 이상 여부와 심각도를 고려하세요.

2. 병해충 의심 증상: 30점

병이나 해충으로 의심되는 증상의 유무, 범위 및 심각도를 평가하세요.

명확한 병해충 증상이 없다면 이 항목 때문에 불필요하게 감점하지 마세요.

3. 전반적인 생육 활력: 20점

식물 전체의 균형, 잎의 활력, 생장 상태 및 전반적으로 건강해 보이는 정도를 평가하세요.

위 세 항목을 단순히 기계적으로 계산하지 말고 사진에서 확인되는 상태를 종합하여 최종 점수를 결정하세요.

사진에서 확인할 수 없는 다음 사항은 추측하여 감점하지 마세요.

- 뿌리의 상태
- 흙이나 토양 내부의 상태
- 실제 물 주기
- 최근의 환경 변화
- 사진에 나타나지 않는 병해충
- 사진에서 확인할 수 없는 생육 상태

사진의 품질이나 촬영 범위 때문에 특정 상태를 확인하기 어려운 경우에는 확인되지 않는 부분을 근거로 건강 점수를 과도하게 낮추지 마세요.

건강 점수는 현재 사진에서 확인되는 상태를 기준으로 판단하며, 단순히 병해충이 보이지 않는다는 이유만으로 지나치게 높은 점수를 주지도 마세요.

건강 점수의 구간은 다음 기준을 참고하세요.

80~100점: 건강한 편
60~79점: 가벼운 이상이 있거나 살펴볼 부분이 있음
40~59점: 관리가 필요한 상태
0~39점: 상태가 좋지 않아 적극적인 관리가 필요한 상태

이 구간의 설명은 사용자에게 별도로 출력하지 마세요.
기본 진단 정보에서는 건강 점수 숫자만 출력하세요.


==================================================
[닥풀의 한마디 작성 기준]
==================================================

현재 식물의 상태와 가장 중요한 원인 또는 관리 포인트를 일반 사용자가 이해하기 쉬운 말로 한두 문장으로 요약하세요.

사진에서 확인되지 않는 내용을 단정하지 마세요.
현재 상태에서 가장 중요한 내용을 우선하여 간결하게 작성하세요.


==================================================
[상세 진단 리포트]
==================================================

기본 정보 5개 항목을 모두 출력한 다음 반드시 아래 구분선을 하나 출력하세요.

---

그 다음부터 상세 진단을 시작하세요.

상세 진단의 시작 제목은 반드시 다음 문구를 그대로 사용하세요.

### 닥풀 AI 진단 리포트

상세 진단에서는 기본 정보에서 이미 출력한 다음 5개 항목을 다시 반복하지 마세요.

- 추정 식물
- 학명
- 이 식물일 가능성
- 식물 건강 점수
- 닥풀의 한마디

상세 진단은 다음 순서와 제목을 반드시 유지하세요.


#### 시각적 특징 및 식별 근거

- **잎과 수형 특징**
사진에서 실제로 확인되는 잎의 모양, 배열, 색상, 크기, 수형 등의 특징을 설명하고 식물 식별에 어떤 근거가 되는지 설명하세요.

- **꽃 및 줄기 특징**
꽃, 줄기, 가지, 열매 등이 사진에서 확인되는 경우 형태와 상태를 설명하세요.
사진에서 확인할 수 없는 부분은 추측해서 작성하지 마세요.


---

#### 이상 증상 및 상태 분석

- **발생 증상**
사진에서 실제로 관찰되는 반점, 변색, 시듦, 잎마름, 손상, 뒤틀림, 벌레 흔적 등의 이상 증상을 구체적으로 설명하세요.

이상 증상이 뚜렷하지 않은 경우에는 정상적으로 보이는 상태를 설명하고, 불필요하게 병해충을 만들어내지 마세요.

- **원인으로 보이는 점**
관찰된 증상을 바탕으로 가능한 원인을 설명하세요.

검사 요청 위치와 시점 정보를 함께 고려하여 환경적 원인이나 해당 시기에 발생하기 쉬운 병해충과의 연관성을 설명하세요.

원인이 명확하지 않은 경우에는 하나의 원인으로 단정하지 말고 가능성이 높은 원인부터 설명하세요.


---

### 맞춤형 관리 가이드

#### 먼저 해주세요

- **지금 바로 해야 할 일**
현재 상태에서 우선적으로 해야 할 관리 방법을 1~2가지 중심으로 설명하세요.

긴급하게 조치할 필요가 없는 경우에는 과도한 응급 처치를 권하지 마세요.


---

#### 자라는 환경 및 물 주기

- **물 주기 가이드**
해당 식물의 특성과 현재 상태를 고려하여 물을 주는 방법과 주의할 점을 설명하세요.

단순히 며칠마다 물을 주라는 식으로 고정된 주기를 제시하기보다 흙의 상태와 계절 및 환경을 함께 고려하도록 설명하세요.

- **햇빛 및 통풍**
현재 식물에 적합한 햇빛, 통풍 및 배치 환경을 설명하세요.


---

#### 병해충 예방 및 영양 관리

- **약제 및 영양제 관리**
병해충이 의심되는 경우 필요한 관리 방법과 약제 사용 시 주의사항을 설명하세요.

병해충이 명확하지 않은 경우에는 불필요한 약제 사용을 권하지 마세요.

영양제 역시 현재 상태에 필요한 경우에만 권장하세요.

- **우선 확인할 것**
앞으로 상태를 관찰할 때 특히 확인해야 할 증상이나 변화, 그리고 현재 계절에 주의할 사항을 설명하세요.

---



==================================================
[출력 형식 및 구분선 규칙]
==================================================

정상 진단 결과는 반드시 다음 순서로 작성하세요.

1. 기본 정보 5개 항목
2. '---' 구분선
3. '### 닥풀 AI 진단 리포트'
4. 시각적 특징 및 식별 근거
5. '---' 구분선
6. 이상 증상 및 상태 분석
7. '---' 구분선
8. 맞춤형 관리 가이드
9. '---' 구분선
10. 먼저 해주세요
11. '---' 구분선
12. 자라는 환경 및 물 주기
13. '---' 구분선
14. 병해충 예방 및 영양 관리

위의 순서와 제목을 변경하거나 생략하지 마세요.

프롬프트 안에서 '===='로 표시된 구분선은 지시사항을 구분하기 위한 것이므로 사용자에게 출력하지 마세요.

실제 진단 리포트에서 지정한 '---' 구분선은 사용자에게 출력하세요.

프롬프트 안의 설명, 지시사항, 예시, placeholder 및 대괄호로 표시된 내용은 사용자에게 출력하지 마세요.

각 항목과 단락은 읽기 쉽게 구분하여 작성하세요.
서로 다른 내용의 단락 사이에는 빈 줄을 한 줄 넣으세요.

문장마다 강제로 줄을 바꾸지 말고, 하나의 내용 단위가 자연스럽게 이어지도록 작성하세요.

'\\n' 또는 '\\n\\n'이라는 문자열 자체를 출력하지 마세요.
실제 줄바꿈을 사용하세요.

사진에서 확인되지 않는 내용을 사실처럼 만들어내지 마세요.
불확실한 판단은 불확실하다고 표현하세요.

정상 진단에서는 지정된 형식 외의 별도 안내 문구나 맺음말을 추가하지 마세요.
"""
        
        last_error_log = ""
        
        for key_idx, current_key in enumerate(GEMINI_API_KEYS):
            try:
                client = genai.Client(api_key=current_key)
                for attempt in range(3):
                    try:
                        response = client.models.generate_content(
                            model="gemini-3.6-flash",
                            contents=[
                                types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
                                prompt
                            ],
                            config=types.GenerateContentConfig(temperature=0.1)
                        )
                        if response and response.text:
                            cleaned_text = clean_chinese_characters(response.text)
                            return {"status": "SUCCESS", "data": cleaned_text}
                            
                    except APIError as e:
                        # APIError의 상세 메시지나 전체 객체 문자열을 확실하게 담음
                        last_error_log = f"APIError (Code: {getattr(e, 'code', 'unknown')}) - {e.message if hasattr(e, 'message') else str(e)}"
                        if "429" in last_error_log or "QUOTA" in last_error_log or "EXHAUSTED" in last_error_log:
                            st.toast(f"API Key #{key_idx + 1} 할당량 소진. 다음 Key로 자동 스위칭합니다.", icon="⚠️")
                            break
                        if "503" in last_error_log or "UNAVAILABLE" in last_error_log:
                            if attempt < 2:
                                time.sleep(2 * (attempt + 1))
                                continue
                        break

            except Exception as e:
                # 일반 예외 발생 시 클래스 이름과 에러 메시지를 모두 기록
                last_error_log = f"{type(e).__name__}: {str(e)}"
                continue

        return {
            "status": "ERROR", 
            "message": f"모든 API Key의 사용량이 소진되었거나 AI 호출에 실패했습니다. (상세 원인: {last_error_log})"
        }

    except Exception as e:
        return {"status": "ERROR", "message": f"시스템 오류: {str(e)}"}
