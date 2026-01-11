# LawPro Fast Converter

고성능 문서-HTML 변환 데스크탑 앱 (Electron + Python)

## 주요 기능

### 문서 변환
- **지원 형식**: HWPX, DOCX, XLSX, PPTX, PDF (디지털/이미지)
- **하이브리드 처리**:
  - 디지털 문서 → 로컬 라이브러리 (무료, 초고속)
  - 이미지 PDF → Upstage Document Parse API (고정밀 OCR)
- **병렬 처리**: CPU 코어 기반 최적화 (수십 개 파일 동시 변환)
- **서식 완벽 보존**: 표 테두리, 셀 병합, 서식 등 원본 유지

### AI 검수 (MCP 연동)
- **Claude Desktop 연결**: 원클릭 MCP 설정으로 Claude와 연동
- **Gemini 백업**: Claude 사용량 소진 시 Gemini Flash로 전환
- **OCR 오류 자동 감지**: Z/을, 0/O 등 한글-영문 혼동 패턴 학습

## 빠른 시작

### 1. 설치

```bash
# 저장소 클론
git clone https://github.com/lawpro/fast-converter.git
cd fast-converter

# Node.js 의존성 설치
npm install

# Python 의존성 설치
cd engine
pip install -r requirements.txt
cd ..
```

### 2. 실행

```bash
# 개발 모드
npm start

# 또는
npm run dev
```

### 3. 빌드

```bash
# Windows
npm run build:win

# macOS
npm run build:mac

# Linux
npm run build:linux
```

## 아키텍처

```
LawPro-FastConverter/
├── engine/                     # Python 백엔드
│   ├── main.py                 # 병렬 변환 엔진
│   ├── processor.py            # 파일 처리 라우터
│   ├── mcp_server.py           # Claude MCP 서버
│   ├── gemini_agent.py         # Gemini 백업 에이전트
│   └── prompts/                # 검수 프롬프트
├── src/                        # Electron 프론트엔드
│   ├── main.js                 # 메인 프로세스
│   ├── preload.js              # IPC 브릿지
│   ├── renderer.js             # UI 로직
│   └── index.html              # 메인 화면
├── resources/                  # 앱 아이콘
└── package.json
```

## 사용법

### 문서 변환

1. 앱 실행
2. 변환할 문서가 있는 폴더를 드래그 앤 드롭 (또는 클릭하여 선택)
3. Upstage API 키 입력 (이미지 PDF 변환 시 필요)
4. "변환 시작" 클릭
5. 결과는 `Converted_HTML` 폴더에 저장

### Claude 연동 (MCP)

1. "AI 검수" 탭으로 이동
2. "원클릭 연결하기" 버튼 클릭
3. Claude Desktop 재시작
4. Claude에서 검수 작업 수행:

```
# Claude Desktop에서 사용 가능한 도구:
- list_documents(): 검수 대기 문서 목록
- read_document(filename): 문서 읽기
- analyze_ocr_errors(filename): 오류 분석
- save_reviewed_document(filename, content): 저장
```

### Gemini 백업

1. [Google AI Studio](https://aistudio.google.com/)에서 API 키 발급
2. "AI 검수" 탭에서 Gemini API 키 입력
3. 모델 선택 (Flash 2.0 권장)
4. "Gemini 검수 시작" 클릭

## 지원 파일 형식

| 형식 | 처리 방식 | 비용 |
|------|----------|------|
| XLSX | pandas + openpyxl | 무료 |
| DOCX | python-docx | 무료 |
| PPTX | python-pptx | 무료 |
| HWPX | lxml (XML 파싱) | 무료 |
| PDF (디지털) | pdfplumber | 무료 |
| PDF (이미지) | Upstage API | 유료 |
| HWP (구형) | Upstage API | 유료 |

## OCR 오류 패턴

MCP 검수 시 다음 패턴을 자동 감지합니다:

| 정확한 글자 | 오인식 | 예시 |
|------------|--------|------|
| 을 | Z, z, 2 | 계약Z → 계약을 |
| 를 | Z, z | 권리Z → 권리를 |
| 은 | E, e | 것E → 것은 |
| 이 | 0, O, l, 1 | 권l → 권이 |
| 제1조 | 게1초 | 법률 조항 |

## API 키 설정

### Upstage Document Parse API
- [Upstage Console](https://console.upstage.ai/)에서 발급
- 이미지 PDF 변환에 필요
- 무료 크레딧 제공

### Gemini API
- [Google AI Studio](https://aistudio.google.com/)에서 발급
- Claude 백업용 검수에 사용
- 무료 티어 (분당 15회 요청)

## 개발

### 환경 요구사항
- Node.js 18+
- Python 3.9+
- npm 또는 yarn

### 개발 서버

```bash
npm run dev
```

### Python 엔진 테스트

```bash
cd engine
python main.py /path/to/documents your-upstage-api-key
```

### MCP 서버 테스트

```bash
cd engine
python mcp_server.py
```

## 라이선스

MIT License

## 지원

문의: support@lawpro.ai
