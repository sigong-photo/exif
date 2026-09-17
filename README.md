# 📸 EXIF Frame Generator

사진의 EXIF 및 메타데이터를 기반으로 세련된 사진 프레임(보더)과 워터마크를 생성해 주는 Streamlit 웹 애플리케이션입니다.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.40%2B-FF4B4B)
![Pillow](https://img.shields.io/badge/Pillow-10.0%2B-green)

---

## ✨ 주요 기능

- **카메라 & 렌즈 메타데이터 자동 감지**:
  - 카메라 기본 EXIF(0th IFD) 및 Exif Sub-IFD 태그 파싱
  - 어도비 라이트룸/포토샵 등 보정 툴에서 내보낸 이미지의 **XMP 메타데이터(`aux:Lens`) 완벽 지원**
  - 초점거리(`FocalLength`), 조리개(`FNumber`), 셔터스피드(`ExposureTime`), `ISO` 자동 포맷팅
- **풍부한 공식 브랜드 로고 프리셋 탑재**:
  - **카메라 제조사**: SONY(알파 오렌지/블랙/화이트, 워드마크), LEICA(레드 닷), HASSELBLAD, NIKON, CANON, FUJIFILM
  - **렌즈 전문 제조사**: SIGMA(공식 로고/시그니처 레드), TAMRON, VILTROX
  - **스마트 자동 추천**: EXIF 정보를 기반으로 장착된 렌즈/카메라 브랜드 로고 자동 선택
  - 커스텀 PNG 로고 파일 직접 업로드 지원
- **커스텀 문구 & 워터마크 설정**:
  - 브랜드명, 작가 서명, 촬영 장소 등 원하는 문구 입력
  - 7가지 위치(하단 프레임 우/중/좌, 사진 내부 사각 모서리 워터마크) 지원
  - 글씨 크기, 굵기, 투명도 및 컬러 피커/프리셋 색상 조절
- **고해상도 비례 스케일링**:
  - 수천만 화소 원본 사진 해상도에 맞춰 폰트와 여백이 비례 계산되어 선명하고 안정적인 타이포그래피 제공
  - 폰트 크기, 하단 여백, 테두리 여백 실시간 슬라이더 조절
- **프레임 스타일 & 테마**:
  - 3가지 레이아웃: 좌우 분할(Modern), 2단/3단 표준(Standard), 중앙 정렬(Minimal)
  - 4가지 컬러 테마: 화이트, 블랙, 다크 그레이, 크림

---

## 🚀 시작하기

### 1. 환경 설정 및 설치

```bash
# 가상환경 생성 및 활성화
python3 -m venv .venv
source .venv/bin/activate

# 의존성 패키지 설치
pip install -r requirements.txt
```

### 2. 애플리케이션 실행

```bash
streamlit run app.py
```

브라우저에서 `http://localhost:8501`로 접속하여 사진을 업로드하고 프레임을 생성할 수 있습니다.

---

## 📁 프로젝트 구조

```
exif/
├── app.py              # Streamlit 프레임 생성기 메인 앱
├── requirements.txt    # 의존성 패키지 목록 (streamlit, pillow, cairosvg, svglib)
├── .gitignore          # Git 제외 목록
├── README.md           # 프로젝트 안내서
└── logos/              # 각 브랜드별 고해상도 투명 PNG 및 SVG 로고
    ├── sony_alpha_*.png
    ├── sony_*.png
    ├── sigma_*.png
    ├── leica_*.png
    ├── hasselblad_*.png
    ├── nikon_*.png
    ├── canon_*.png
    ├── fujifilm_*.png
    ├── tamron_*.png
    └── viltrox_*.png
```
