# ==========================================
# 안정적인 EXIF GPS 추출 (모바일 유연 파싱 최종 버전)
# ==========================================
def convert_to_degrees(value):
    try:
        if value is None:
            return None
        if isinstance(value, (str, bytes, float, int)):
            try:
                return float(value)
            except Exception:
                return None
        if not hasattr(value, "__iter__"):
            return None

        val_list = []
        for item in value:
            if item is None:
                return None
            
            # 문자열 'nan' 이나 빈 값 체크
            item_str = str(item).strip().lower()
            if item_str in ['nan', 'none', '', 'inf', '-inf']:
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
                try:
                    val_list.append(float(item))
                except Exception:
                    return None
                
        if len(val_list) == 0:
            return None
            
        # 폰에서 데이터 개수가 1개(도) 또는 2개(도, 분)로 들어오는 경우도 방어
        d = val_list[0]
        m = val_list[1] if len(val_list) > 1 else 0.0
        s = val_list[2] if len(val_list) > 2 else 0.0
        
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

        # 문자열 키와 표준 숫자 ID(2: 위도, 1: 위도참조, 4: 경도, 3: 경도참조) 모두 지원
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
