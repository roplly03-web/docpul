# ==========================================
# 안정적인 EXIF GPS 추출 (모바일/PC 키 매칭 완벽 통합 버전)
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

        # 기기/플랫폼별로 다른 키 타입(숫자, 문자열 이름, 문자열 숫자)을 모두 대응하도록 정규화
        gps = {}
        for k, v in gps_info.items():
            tag_name = ExifTags.GPSTAGS.get(k, str(k))
            gps[k] = v
            gps[tag_name] = v
            if isinstance(k, int):
                gps[str(k)] = v

        # 위도/경도 및 참조값에 대한 모든 가능한 키 후보군 탐색
        lat = gps.get(2) or gps.get("GPSLatitude") or gps.get("2")
        lat_ref = gps.get(1) or gps.get("GPSLatitudeRef") or gps.get("1")
        lon = gps.get(4) or gps.get("GPSLongitude") or gps.get("4")
        lon_ref = gps.get("GPSLongitudeRef") or gps.get(3) or gps.get("3")

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
