import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps, ExifTags
import io
import os
import re

def get_font(size, bold=False):
    base_dir = os.path.dirname(__file__)
    font_file = "fonts/Pretendard-Bold.ttf" if bold else "fonts/Pretendard-Regular.ttf"
    bundled_font = os.path.join(base_dir, font_file)
    if os.path.exists(bundled_font):
        try:
            return ImageFont.truetype(bundled_font, size)
        except Exception:
            pass

    if bold:
        candidates = [
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    else:
        candidates = [
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()

def fit_font(text, max_width, initial_size, bold=False):
    """텍스트가 지정된 너비를 초과하지 않도록 폰트 크기 자동 축소"""
    size = max(14, int(initial_size))
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    while size > 14:
        font = get_font(size, bold=bold)
        bbox = draw.textbbox((0, 0), text, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            return font
        size = int(size * 0.92)
    return get_font(size, bold=bold)

def get_exif_data(image):
    meta = {}
    
    # 1. EXIF 및 Sub-IFD 파싱
    try:
        info = image.getexif()
        if info:
            for tag, val in info.items():
                decoded = ExifTags.TAGS.get(tag, tag)
                meta[decoded] = val
                
            for ifd_id in (ExifTags.IFD.Exif, ExifTags.IFD.GPSInfo, ExifTags.IFD.Interop):
                try:
                    sub_ifd = info.get_ifd(ifd_id)
                    if sub_ifd:
                        for tag, val in sub_ifd.items():
                            decoded = ExifTags.TAGS.get(tag, tag)
                            meta[decoded] = val
                except Exception:
                    pass
    except Exception:
        pass

    # 2. XMP 파싱 (Adobe 라이트룸/포토샵 보정본 대응)
    xmp_raw = image.info.get("xmp", b"")
    if isinstance(xmp_raw, bytes):
        xmp_str = xmp_raw.decode("utf-8", errors="ignore")
    elif isinstance(xmp_raw, str):
        xmp_str = xmp_raw
    else:
        xmp_str = ""

    if xmp_str:
        if not meta.get("LensModel"):
            for pattern in [
                r'aux:Lens=\"([^\"]+)\"',
                r'<aux:Lens>([^<]+)</aux:Lens>',
                r'LensModel=\"([^\"]+)\"',
                r'<[a-zA-Z0-9_:]*LensModel>([^<]+)</',
                r'aux:LensInfo=\"([^\"]+)\"'
            ]:
                match = re.search(pattern, xmp_str)
                if match:
                    meta["LensModel"] = match.group(1).strip()
                    break

        if not meta.get("Model"):
            match = re.search(r'tiff:Model=\"([^\"]+)\"', xmp_str) or re.search(r'<tiff:Model>([^<]+)</tiff:Model>', xmp_str)
            if match:
                meta["Model"] = match.group(1).strip()

        if not meta.get("Make"):
            match = re.search(r'tiff:Make=\"([^\"]+)\"', xmp_str) or re.search(r'<tiff:Make>([^<]+)</tiff:Make>', xmp_str)
            if match:
                meta["Make"] = match.group(1).strip()

        if not meta.get("FocalLength"):
            match = re.search(r'exif:FocalLength=\"([^\"]+)\"', xmp_str) or re.search(r'<exif:FocalLength>([^<]+)</exif:FocalLength>', xmp_str)
            if match:
                meta["FocalLength"] = match.group(1).strip()

        if not meta.get("FNumber"):
            match = re.search(r'exif:FNumber=\"([^\"]+)\"', xmp_str) or re.search(r'<exif:FNumber>([^<]+)</exif:FNumber>', xmp_str)
            if match:
                meta["FNumber"] = match.group(1).strip()

        if not meta.get("ExposureTime"):
            match = re.search(r'exif:ExposureTime=\"([^\"]+)\"', xmp_str) or re.search(r'<exif:ExposureTime>([^<]+)</exif:ExposureTime>', xmp_str)
            if match:
                meta["ExposureTime"] = match.group(1).strip()

        if not meta.get("ISOSpeedRatings") and not meta.get("PhotographicSensitivity"):
            match = re.search(r'<exif:ISOSpeedRatings>\s*<rdf:Seq>\s*<rdf:li>([^<]+)</rdf:li>', xmp_str)
            if match:
                meta["ISOSpeedRatings"] = match.group(1).strip()

        if not meta.get("DateTimeOriginal"):
            match = re.search(r'exif:DateTimeOriginal=\"([^\"]+)\"', xmp_str) or re.search(r'<exif:DateTimeOriginal>([^<]+)</exif:DateTimeOriginal>', xmp_str) or re.search(r'xmp:CreateDate=\"([^\"]+)\"', xmp_str)
            if match:
                meta["DateTimeOriginal"] = match.group(1).strip()

        if not meta.get("Artist"):
            match = re.search(r'<dc:creator>\s*<rdf:Seq>\s*<rdf:li>([^<]+)</rdf:li>', xmp_str)
            if match:
                meta["Artist"] = match.group(1).strip()

    return meta

def add_exif_frame(image, options):
    w, h = image.size
    
    # 해상도 비례 기준 스케일
    base_scale = w / 1200.0
    font_multiplier = options.get("font_scale", 1.2)
    
    # 여백 계산
    side_pct = options.get("side_margin_pct", 3.0) / 100.0
    bottom_pct = options.get("bottom_margin_pct", 9.0) / 100.0
    
    border_sides = max(20, int(w * side_pct))
    border_bottom = max(80, int(w * bottom_pct))
    
    new_width = w + (border_sides * 2)
    new_height = h + border_sides + border_bottom
    
    # 테마 색상 설정
    theme = options.get("theme", "화이트")
    if theme == "블랙":
        bg_color = (18, 18, 18)
        text_primary = (245, 245, 245)
        text_secondary = (165, 165, 165)
    elif theme == "다크 그레이":
        bg_color = (38, 40, 43)
        text_primary = (240, 240, 240)
        text_secondary = (175, 175, 175)
    elif theme == "크림":
        bg_color = (248, 246, 240)
        text_primary = (28, 28, 28)
        text_secondary = (120, 115, 110)
    else: # 화이트
        bg_color = (255, 255, 255)
        text_primary = (25, 25, 25)
        text_secondary = (110, 110, 110)
        
    framed_img = Image.new("RGB", (new_width, new_height), bg_color)
    if image.mode != "RGB":
        image = image.convert("RGB")
    framed_img.paste(image, (border_sides, border_sides))
    
    draw = ImageDraw.Draw(framed_img)
    
    # 텍스트 내용 준비
    camera_text = options.get("camera", "").strip()
    lens_text = options.get("lens", "").strip()
    settings_text = options.get("settings", "").strip()
    
    main_title_parts = [p for p in [camera_text, lens_text] if p]
    main_title = "   |   ".join(main_title_parts)
    
    # 추가 항목들 (날짜, 작가 등)
    extra_items = options.get("extra_items", [])
    extra_text = "  ·  ".join([item for item in extra_items if item.strip()])
    
    # 로고 리사이징
    logo_orig = options.get("logo")
    logo = None
    logo_w = 0
    logo_scale = options.get("logo_scale", 1.0)
    if logo_orig:
        logo = logo_orig.copy()
        if logo.mode != "RGBA":
            logo = logo.convert("RGBA")
        max_logo_h = min(int(border_bottom * 0.75), max(10, int(border_bottom * 0.45 * logo_scale)))
        logo.thumbnail((int(max_logo_h * 4.5), max_logo_h))
        logo_w = logo.width + int(30 * base_scale)
        
    layout = options.get("layout", "좌우 분할 (Modern)")
    usable_width = new_width - (border_sides * 2)
    
    init_title_size = int(24 * base_scale * font_multiplier)
    init_sub_size = int(18 * base_scale * font_multiplier)
    
    # 커스텀 텍스트 준비
    custom_opts = options.get("custom_text")
    has_custom = custom_opts and custom_opts.get("text")
    c_pos = custom_opts.get("position", "하단 프레임 - 우측 (브랜드 로고 자리)") if has_custom else None
    
    custom_right_w = 0
    c_font = None
    c_text = ""
    cw, ch = 0, 0
    if has_custom:
        c_text = custom_opts["text"].strip()
        c_scale = custom_opts.get("size", 1.5)
        c_bold = custom_opts.get("bold", True)
        c_font_size = int(24 * base_scale * font_multiplier * c_scale)
        c_font = get_font(c_font_size, bold=c_bold)
        c_bbox = draw.textbbox((0, 0), c_text, font=c_font)
        cw = c_bbox[2] - c_bbox[0]
        ch = c_bbox[3] - c_bbox[1]
        
        if c_pos == "하단 프레임 - 우측 (브랜드 로고 자리)":
            custom_right_w = cw + int(35 * base_scale)

    if layout == "좌우 분할 (Modern)":
        # 우측 설정 영역 폭 및 좌측 영역 폭 계산
        right_w = max(int(usable_width * 0.35), int(320 * base_scale))
        left_w = usable_width - right_w - logo_w - custom_right_w - int(20 * base_scale)
        
        t_font = fit_font(main_title, left_w, init_title_size, bold=True)
        s_font = fit_font(extra_text if extra_text else " ", left_w, init_sub_size, bold=False)
        sett_font = fit_font(settings_text, right_w, init_title_size, bold=False)
        
        t_bbox = draw.textbbox((0, 0), main_title if main_title else "A", font=t_font)
        s_bbox = draw.textbbox((0, 0), extra_text if extra_text else "A", font=s_font)
        
        content_h = (t_bbox[3] - t_bbox[1]) + ((s_bbox[3] - s_bbox[1]) if extra_text else 0) + (int(12 * base_scale) if extra_text else 0)
        start_y = h + border_sides + max(10, int((border_bottom - content_h) / 2))
        
        # 좌측 텍스트 출력
        draw.text((border_sides, start_y), main_title, fill=text_primary, font=t_font)
        if extra_text:
            next_y = start_y + (t_bbox[3] - t_bbox[1]) + int(12 * base_scale)
            draw.text((border_sides, next_y), extra_text, fill=text_secondary, font=s_font)
            
        # 우측 설정값 출력
        if settings_text:
            sett_bbox = draw.textbbox((0, 0), settings_text, font=sett_font)
            sett_w = sett_bbox[2] - sett_bbox[0]
            sett_x = new_width - border_sides - logo_w - custom_right_w - sett_w
            sett_y = h + border_sides + max(10, int((border_bottom - (sett_bbox[3] - sett_bbox[1])) / 2))
            draw.text((sett_x, sett_y), settings_text, fill=text_primary, font=sett_font)
            
        # 로고 출력 (최우측)
        if logo:
            logo_x = new_width - border_sides - logo.width
            logo_y = h + border_sides + max(10, int((border_bottom - logo.height) / 2))
            framed_img.paste(logo, (logo_x, logo_y), mask=logo)
                
    elif layout == "중앙 정렬 (Minimal)":
        t_font = fit_font(main_title, usable_width - custom_right_w - logo_w, init_title_size, bold=True)
        sub_line = "  ·  ".join([p for p in [settings_text, extra_text] if p])
        s_font = fit_font(sub_line, usable_width - custom_right_w - logo_w, init_sub_size, bold=False)
        
        t_bbox = draw.textbbox((0, 0), main_title if main_title else "A", font=t_font)
        s_bbox = draw.textbbox((0, 0), sub_line if sub_line else "A", font=s_font)
        
        content_h = (t_bbox[3] - t_bbox[1]) + ((s_bbox[3] - s_bbox[1]) if sub_line else 0) + (int(14 * base_scale) if sub_line else 0)
        start_y = h + border_sides + max(10, int((border_bottom - content_h) / 2))
        
        if main_title:
            t_w = t_bbox[2] - t_bbox[0]
            draw.text((int((new_width - t_w) / 2), start_y), main_title, fill=text_primary, font=t_font)
            
        if sub_line:
            s_w = s_bbox[2] - s_bbox[0]
            next_y = start_y + (t_bbox[3] - t_bbox[1]) + int(14 * base_scale)
            draw.text((int((new_width - s_w) / 2), next_y), sub_line, fill=text_secondary, font=s_font)
            
        if logo:
            logo_x = new_width - border_sides - logo.width
            logo_y = h + border_sides + max(10, int((border_bottom - logo.height) / 2))
            framed_img.paste(logo, (logo_x, logo_y), mask=logo)
                
    else: # 2단/3단 표준 정렬
        t_font = fit_font(main_title, usable_width - logo_w - custom_right_w, init_title_size, bold=True)
        s_font = fit_font(settings_text, usable_width - logo_w - custom_right_w, init_sub_size, bold=False)
        e_font = fit_font(extra_text if extra_text else " ", usable_width - logo_w - custom_right_w, max(12, int(init_sub_size * 0.9)), bold=False)
        
        t_bbox = draw.textbbox((0, 0), main_title if main_title else "A", font=t_font)
        s_bbox = draw.textbbox((0, 0), settings_text if settings_text else "A", font=s_font)
        e_bbox = draw.textbbox((0, 0), extra_text if extra_text else "A", font=e_font)
        
        line_gap = int(12 * base_scale)
        lines = [t_bbox[3] - t_bbox[1]]
        if settings_text:
            lines.append(s_bbox[3] - s_bbox[1])
        if extra_text:
            lines.append(e_bbox[3] - e_bbox[1])
        total_h = sum(lines) + line_gap * (len(lines) - 1)
        
        cur_y = h + border_sides + max(10, int((border_bottom - total_h) / 2))
        
        if main_title:
            draw.text((border_sides, cur_y), main_title, fill=text_primary, font=t_font)
            cur_y += (t_bbox[3] - t_bbox[1]) + line_gap
            
        if settings_text:
            draw.text((border_sides, cur_y), settings_text, fill=text_secondary, font=s_font)
            cur_y += (s_bbox[3] - s_bbox[1]) + line_gap
            
        if extra_text:
            draw.text((border_sides, cur_y), extra_text, fill=text_secondary, font=e_font)
            
        if logo:
            logo_x = new_width - border_sides - logo.width
            logo_y = h + border_sides + max(10, int((border_bottom - logo.height) / 2))
            framed_img.paste(logo, (logo_x, logo_y), mask=logo)

    # 커스텀 텍스트 렌더링
    if has_custom and c_text:
        raw_color = custom_opts.get("color")
        if raw_color:
            try:
                c_rgb = tuple(int(raw_color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
            except Exception:
                c_rgb = text_primary
        else:
            c_rgb = (255, 255, 255) if "사진 내부" in c_pos else text_primary
            
        pad_inside = int(w * 0.025)
        
        if c_pos == "하단 프레임 - 우측 (브랜드 로고 자리)":
            cx = new_width - border_sides - logo_w - cw
            cy = h + border_sides + max(10, int((border_bottom - ch) / 2))
        elif c_pos == "하단 프레임 - 중앙":
            cx = int((new_width - cw) / 2)
            cy = h + border_sides + max(10, int((border_bottom - ch) / 2))
        elif c_pos == "하단 프레임 - 좌측 (메타데이터 하단)":
            cx = border_sides
            cy = h + border_sides + border_bottom - ch - int(12 * base_scale)
        elif c_pos == "사진 내부 - 우측 하단 (워터마크)":
            cx = border_sides + w - pad_inside - cw
            cy = border_sides + h - pad_inside - ch
        elif c_pos == "사진 내부 - 좌측 하단 (워터마크)":
            cx = border_sides + pad_inside
            cy = border_sides + h - pad_inside - ch
        elif c_pos == "사진 내부 - 우측 상단":
            cx = border_sides + w - pad_inside - cw
            cy = border_sides + pad_inside
        elif c_pos == "사진 내부 - 좌측 상단":
            cx = border_sides + pad_inside
            cy = border_sides + pad_inside
        else:
            cx = new_width - border_sides - logo_w - cw
            cy = h + border_sides + max(10, int((border_bottom - ch) / 2))

        c_opacity = custom_opts.get("opacity", 1.0)
        if "사진 내부" in c_pos:
            overlay = Image.new("RGBA", framed_img.size, (0, 0, 0, 0))
            odraw = ImageDraw.Draw(overlay)
            alpha = int(255 * max(0.1, min(1.0, c_opacity)))
            shadow_alpha = int(alpha * 0.6)
            
            s_offset = max(2, int(2.5 * base_scale))
            odraw.text((cx + s_offset, cy + s_offset), c_text, fill=(0, 0, 0, shadow_alpha), font=c_font)
            odraw.text((cx, cy), c_text, fill=(c_rgb[0], c_rgb[1], c_rgb[2], alpha), font=c_font)
            framed_img = Image.alpha_composite(framed_img.convert("RGBA"), overlay).convert("RGB")
        else:
            draw.text((cx, cy), c_text, fill=c_rgb, font=c_font)
                
    return framed_img

st.set_page_config(layout="wide", page_title="EXIF Frame Generator")
st.title("📸 EXIF Frame Generator")

uploaded_file = st.file_uploader("사진을 업로드하세요 (JPG, PNG)", type=["jpg", "jpeg", "png"])

if uploaded_file:
    raw_img = Image.open(uploaded_file)
    exif = get_exif_data(raw_img)
    img = ImageOps.exif_transpose(raw_img)
    
    file_key = f"{uploaded_file.name}_{uploaded_file.size}"
    
    # 1. 원본 메타데이터 기본값 파싱
    default_camera = str(exif.get("Model") or "Unknown Camera").strip()
    default_lens = str(exif.get("LensModel") or exif.get("LensSpecification") or "Unknown Lens").strip()
    
    # 초점거리
    focal_raw = exif.get("FocalLength", "")
    default_focal = ""
    if focal_raw:
        try:
            default_focal = f"{float(focal_raw):g}mm"
        except Exception:
            default_focal = f"{focal_raw}mm"
            
    # 조리개
    f_raw = exif.get("FNumber", "")
    default_aperture = ""
    if f_raw:
        try:
            default_aperture = f"f/{float(f_raw):g}"
        except Exception:
            default_aperture = f"f/{f_raw}"
            
    # 셔터스피드
    exp_raw = exif.get("ExposureTime", "")
    default_shutter = ""
    if exp_raw:
        try:
            exp_f = float(exp_raw)
            if exp_f > 0:
                default_shutter = f"1/{round(1/exp_f)}s" if exp_f < 1 else f"{exp_f:g}s"
        except Exception:
            default_shutter = f"{exp_raw}s"
            
    # ISO
    iso_val = exif.get("ISOSpeedRatings") or exif.get("PhotographicSensitivity") or ""
    default_iso = f"ISO {iso_val}" if iso_val else ""
    
    # 촬영 일시 파싱
    date_raw = exif.get("DateTimeOriginal") or exif.get("DateTime") or ""
    default_date = ""
    if date_raw:
        match = re.match(r"(\d{4})[:\-](\d{2})[:\-](\d{2})(?:\s+(\d{2}:\d{2}))?", str(date_raw))
        if match:
            default_date = f"{match.group(1)}.{match.group(2)}.{match.group(3)}"
            if match.group(4):
                default_date += f" {match.group(4)}"
        else:
            default_date = str(date_raw).split("T")[0]
            
    # 작가 / 저작권 정보
    default_artist = str(exif.get("Artist") or "").strip()
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.image(img, caption=f"원본 이미지 ({img.width}x{img.height}px)", use_container_width=True)
        
        st.subheader("⚙️ 메타 데이터 항목 편집 및 추가")
        
        with st.expander("📷 카메라 및 렌즈 설정", expanded=True):
            camera_val = st.text_input("카메라 모델", value=default_camera, key=f"cam_{file_key}")
            lens_val = st.text_input("렌즈 모델", value=default_lens, key=f"lens_{file_key}")
            
        with st.expander("⏱️ 촬영 설정 개별 편집", expanded=True):
            sc1, sc2 = st.columns(2)
            with sc1:
                focal_val = st.text_input("초점거리", value=default_focal, key=f"foc_{file_key}")
                shutter_val = st.text_input("셔터 스피드", value=default_shutter, key=f"exp_{file_key}")
            with sc2:
                aperture_val = st.text_input("조리개 값", value=default_aperture, key=f"ap_{file_key}")
                iso_val_input = st.text_input("ISO 감도", value=default_iso, key=f"iso_{file_key}")
                
            auto_settings = "  ·  ".join([p for p in [focal_val, aperture_val, shutter_val, iso_val_input] if p])
            settings_final = st.text_input("촬영 설정 최종 텍스트", value=auto_settings, key=f"sett_final_{file_key}",
                                           help="위 4개 항목을 바탕으로 자동 구성되며, 원하는 형태로 직접 수정할 수 있습니다.")

        with st.expander("✨ 브랜드 로고 프리셋 (카메라 및 렌즈 제조사)", expanded=True):
            logo_presets = {
                "선택 안 함": None,
                # 소니
                "SONY α (소니 알파 오렌지 - 시그니처)": "logos/sony_alpha_orange.png",
                "SONY α (소니 알파 블랙)": "logos/sony_alpha_black.png",
                "SONY α (소니 알파 화이트 - 다크테마용)": "logos/sony_alpha_white.png",
                "SONY (소니 워드마크 블랙)": "logos/sony_black.png",
                "SONY (소니 워드마크 화이트 - 다크테마용)": "logos/sony_white.png",
                # 라이카
                "LEICA (라이카 레드 닷 - 시그니처)": "logos/leica_red.png",
                "LEICA (라이카 모노 블랙)": "logos/leica_black.png",
                "LEICA (라이카 화이트)": "logos/leica_white.png",
                # 핫셀블라드
                "HASSELBLAD (핫셀블라드 블랙)": "logos/hasselblad_black.png",
                "HASSELBLAD (핫셀블라드 화이트 - 다크테마용)": "logos/hasselblad_white.png",
                # 니콘
                "NIKON (니콘 워드마크 블랙)": "logos/nikon_black.png",
                "NIKON (니콘 워드마크 화이트 - 다크테마용)": "logos/nikon_white.png",
                "NIKON (니콘 옐로우 컬러 엠블럼)": "logos/nikon_color.png",
                # 캐논
                "CANON (캐논 시그니처 레드)": "logos/canon_red.png",
                "CANON (캐논 블랙)": "logos/canon_black.png",
                "CANON (캐논 화이트 - 다크테마용)": "logos/canon_white.png",
                # 후지필름
                "FUJIFILM (후지필름 오리지널 컬러)": "logos/fujifilm_color.png",
                "FUJIFILM (후지필름 화이트 - 레드 포인트)": "logos/fujifilm_white_accent.png",
                "FUJIFILM (후지필름 블랙)": "logos/fujifilm_black.png",
                "FUJIFILM (후지필름 모노 화이트)": "logos/fujifilm_white.png",
                # 시그마
                "SIGMA (시그마 공식 블랙)": "logos/sigma_black.png",
                "SIGMA (시그마 공식 화이트 - 다크테마용)": "logos/sigma_white.png",
                "SIGMA (시그마 시그니처 레드)": "logos/sigma_red.png",
                # 탐론
                "TAMRON (탐론 공식 블랙)": "logos/tamron_black.png",
                "TAMRON (탐론 화이트 - 다크테마용)": "logos/tamron_white.png",
                "TAMRON (탐론 오리지널 컬러)": "logos/tamron_color.png",
                # 빌트록스
                "VILTROX (빌트록스 공식 블랙)": "logos/viltrox_black.png",
                "VILTROX (빌트록스 화이트 - 다크테마용)": "logos/viltrox_white.png",
                # 직접 업로드
                "직접 이미지 업로드 (PNG)": "custom",
            }
            preset_names = list(logo_presets.keys())
            
            # 기본 프리셋 스마트 감지
            lens_lower = default_lens.lower()
            cam_lower = default_camera.lower()
            
            if any(k in lens_lower for k in ["tamron", "di iii"]):
                default_idx = preset_names.index("TAMRON (탐론 공식 블랙)")
            elif any(k in lens_lower for k in ["viltrox"]):
                default_idx = preset_names.index("VILTROX (빌트록스 공식 블랙)")
            elif any(k in lens_lower for k in ["sigma", "dg dn", "contemporary", "art", "sports"]):
                default_idx = preset_names.index("SIGMA (시그마 공식 블랙)")
            elif any(k in cam_lower or k in lens_lower for k in ["hasselblad", "x1d", "x2d", "907x"]):
                default_idx = preset_names.index("HASSELBLAD (핫셀블라드 블랙)")
            elif any(k in cam_lower or k in lens_lower for k in ["leica", "summicron", "summilux", "elmarit", "noctilux", "m10", "m11", "sl2", "q2", "q3"]):
                default_idx = preset_names.index("LEICA (라이카 레드 닷 - 시그니처)")
            elif any(k in cam_lower or k in lens_lower for k in ["nikon", "nikkor", "z5", "z6", "z7", "z8", "z9", "zfc", "d850"]):
                default_idx = preset_names.index("NIKON (니콘 워드마크 블랙)")
            elif any(k in cam_lower or k in lens_lower for k in ["canon", "eos", "rf ", "ef ", "r5", "r6", "r3"]):
                default_idx = preset_names.index("CANON (캐논 시그니처 레드)")
            elif any(k in cam_lower or k in lens_lower for k in ["fuji", "fujifilm", "fujinon", "x-t", "x-pro", "x-h", "x-s", "gfx"]):
                default_idx = preset_names.index("FUJIFILM (후지필름 오리지널 컬러)")
            elif any(k in cam_lower for k in ["sony", "ilce", "alpha", "a7", "a9", "a1"]):
                default_idx = preset_names.index("SONY α (소니 알파 오렌지 - 시그니처)")
            else:
                default_idx = 0
                
            logo_choice = st.selectbox("브랜드 로고 선택", preset_names, index=default_idx, key=f"logo_sel_{file_key}")
            
            chosen_logo_img = None
            if logo_choice == "직접 이미지 업로드 (PNG)":
                custom_logo_file = st.file_uploader("로고 이미지 파일 (PNG 투명 배경 권장)", type=["png"], key=f"custom_logo_{file_key}")
                if custom_logo_file:
                    chosen_logo_img = Image.open(custom_logo_file)
            elif logo_presets[logo_choice]:
                logo_file_path = os.path.join(os.path.dirname(__file__), logo_presets[logo_choice])
                if os.path.exists(logo_file_path):
                    chosen_logo_img = Image.open(logo_file_path)
                    
            if chosen_logo_img:
                logo_scale = st.slider("로고 크기 배율", min_value=0.4, max_value=2.2, value=1.0, step=0.1, key=f"logo_scale_{file_key}")
            else:
                logo_scale = 1.0

        with st.expander("✍️ 커스텀 문구 (서명 / 장소 / 추가 텍스트)", expanded=False):
            show_custom = st.checkbox("커스텀 문구 활성화", value=False, key=f"chk_custom_{file_key}")
            
            if show_custom:
                custom_val = st.text_input("문구 내용 (예: Photo by SIGONG, 영암 서킷)", value="", key=f"custom_{file_key}")
                
                c_col1, c_col2 = st.columns(2)
                with c_col1:
                    custom_pos = st.selectbox(
                        "문구 배치 위치",
                        [
                            "하단 프레임 - 우측 (브랜드 로고 자리)",
                            "하단 프레임 - 중앙",
                            "하단 프레임 - 좌측 (메타데이터 하단)",
                            "사진 내부 - 우측 하단 (워터마크)",
                            "사진 내부 - 좌측 하단 (워터마크)",
                            "사진 내부 - 우측 상단",
                            "사진 내부 - 좌측 상단"
                        ],
                        index=0,
                        key=f"cust_pos_{file_key}"
                    )
                    custom_size = st.slider(
                        "문구 크기 배율",
                        min_value=0.5,
                        max_value=3.5,
                        value=1.5,
                        step=0.1,
                        key=f"cust_size_{file_key}"
                    )
                    custom_bold = st.checkbox("굵게 (Bold)", value=True, key=f"cust_bold_{file_key}")

                with c_col2:
                    color_mode = st.radio("글씨 색상 선택", ["프리셋/사용자 지정 색상", "테마 기본색"], index=0, horizontal=True, key=f"cust_cmode_{file_key}")
                    
                    if color_mode == "프리셋/사용자 지정 색상":
                        preset_choice = st.selectbox(
                            "색상 프리셋",
                            [
                                "시그마/라이카 레드 (#E50012)",
                                "클래식 블랙 (#111111)",
                                "퓨어 화이트 (#FFFFFF)",
                                "골드 (#D4AF37)",
                                "쿨 그레이 (#888888)",
                                "직접 선택 (컬러 피커)"
                            ],
                            index=0,
                            key=f"cust_preset_{file_key}"
                        )
                        preset_map = {
                            "시그마/라이카 레드 (#E50012)": "#E50012",
                            "클래식 블랙 (#111111)": "#111111",
                            "퓨어 화이트 (#FFFFFF)": "#FFFFFF",
                            "골드 (#D4AF37)": "#D4AF37",
                            "쿨 그레이 (#888888)": "#888888",
                        }
                        default_picker_hex = preset_map.get(preset_choice, "#E50012")
                        custom_color = st.color_picker("색상 팔레트", value=default_picker_hex, key=f"cust_picker_{file_key}")
                    else:
                        custom_color = None
                        
                    if "사진 내부" in custom_pos:
                        custom_opacity = st.slider("워터마크 투명도", min_value=0.1, max_value=1.0, value=0.85, step=0.05, key=f"cust_op_{file_key}")
                    else:
                        custom_opacity = 1.0
            else:
                custom_val = ""
                custom_pos = "하단 프레임 - 우측 (브랜드 로고 자리)"
                custom_size = 1.5
                custom_bold = True
                custom_color = None
                custom_opacity = 1.0

        with st.expander("🏷️ 추가 일시 / 작가 정보 (선택 추가)", expanded=False):
            show_date = st.checkbox("촬영 일시 포함", value=bool(default_date), key=f"chk_date_{file_key}")
            date_val = st.text_input("촬영 일시", value=default_date, key=f"date_{file_key}", disabled=not show_date)
            
            show_artist = st.checkbox("촬영자 / 작가 포함", value=bool(default_artist), key=f"chk_art_{file_key}")
            artist_val = st.text_input("촬영자 이름", value=default_artist, key=f"art_{file_key}", disabled=not show_artist)

        with st.expander("🎨 프레임 디자인 및 전체 여백 설정", expanded=True):
            theme_choice = st.selectbox("프레임 테마", ["화이트", "블랙", "다크 그레이", "크림"], index=0, key=f"theme_{file_key}")
            layout_choice = st.selectbox("레이아웃 스타일", ["좌우 분할 (Modern)", "2단/3단 표준 정렬", "중앙 정렬 (Minimal)"], index=0, key=f"layout_{file_key}")
            
            font_scale = st.slider("기본 글자 크기 배율", min_value=0.6, max_value=2.5, value=1.3, step=0.1, key=f"font_scale_{file_key}")
            bottom_margin = st.slider("하단 여백 비율 (%)", min_value=5, max_value=20, value=9, step=1, key=f"bottom_m_{file_key}")
            side_margin = st.slider("테두리 여백 비율 (%)", min_value=0, max_value=10, value=3, step=1, key=f"side_m_{file_key}")

    with col2:
        # 추가 항목 리스트 구성
        extra_items = []
        if show_date and date_val.strip():
            extra_items.append(date_val.strip())
        if show_artist and artist_val.strip():
            extra_items.append(artist_val.strip())
            
        custom_text_dict = {
            "text": custom_val.strip() if show_custom else "",
            "position": custom_pos,
            "size": custom_size,
            "bold": custom_bold,
            "color": custom_color,
            "opacity": custom_opacity
        }
            
        options = {
            "camera": camera_val,
            "lens": lens_val,
            "settings": settings_final,
            "extra_items": extra_items,
            "custom_text": custom_text_dict,
            "theme": theme_choice,
            "layout": layout_choice,
            "font_scale": font_scale,
            "bottom_margin_pct": bottom_margin,
            "side_margin_pct": side_margin,
            "logo": chosen_logo_img,
            "logo_scale": logo_scale
        }
        
        st.subheader("🖼️ 완성 미리보기")
        if st.button("✨ 프레임 생성 / 새로고침", type="primary", use_container_width=True):
            st.session_state[f"generated_{file_key}"] = True
            
        if st.session_state.get(f"generated_{file_key}", True):
            result_img = add_exif_frame(img, options)
            st.image(result_img, caption=f"완성된 이미지 ({result_img.width}x{result_img.height}px)", use_container_width=True)
            
            # 고화질 JPEG 다운로드
            buf = io.BytesIO()
            result_img.save(buf, format="JPEG", quality=98)
            byte_im = buf.getvalue()
            
            st.download_button(
                label="📥 고화질 이미지 다운로드",
                data=byte_im,
                file_name=f"framed_{uploaded_file.name}",
                mime="image/jpeg",
                use_container_width=True
            )
