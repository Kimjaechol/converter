# LawPro Fast Converter - 통합 마스터 개발 명세서

**Project:** LawPro Fast Converter (Standalone with MCP)
**Version:** 1.0.0
**Author:** LawPro Development Team

---

## 1. 핵심 철학 및 목표

### 1.1 비전
세상에서 가장 정교하게 문서를 HTML로 변환하는 고성능 데스크탑 앱

### 1.2 핵심 원칙
1. **Fast & Hybrid:** 로컬 처리(무료/초고속)와 Upstage API(유료/고정밀)를 파일 특성에 따라 자동 분기
2. **Parallelism:** Python의 ThreadPoolExecutor를 이용하여 수십 개의 파일을 동시에 변환
3. **Claude-Link (MCP):** 변호사가 사용하는 Claude Desktop 앱을 '검수관'으로 활용
4. **Zero-Barrier:** 사용자는 복잡한 설정 없이 버튼 하나로 Claude/Gemini와 연동

---

## 2. 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                     LawPro Fast Converter                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐      IPC        ┌──────────────────────────┐  │
│  │   Electron   │◄───────────────►│      Python Engine       │  │
│  │  (Frontend)  │                 │    (Backend + MCP)       │  │
│  │              │                 │                          │  │
│  │ - React UI   │                 │ - FileProcessor          │  │
│  │ - TailwindCSS│                 │ - ThreadPoolExecutor     │  │
│  │ - 설정 관리  │                 │ - MCP Server             │  │
│  └──────────────┘                 └──────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                        External Services                         │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐       │
│  │ Upstage API   │  │ Claude Desktop│  │  Gemini API   │       │
│  │ (OCR/Parse)   │  │    (MCP)      │  │   (Backup)    │       │
│  └───────────────┘  └───────────────┘  └───────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 기능 상세 명세

### 3.1 문서 변환 엔진 (Engine Core)

#### 3.1.1 라우팅 로직 (Routing)

| 파일 유형 | 처리 방식 | 라이브러리 | 비용 | 속도 |
|----------|----------|-----------|------|------|
| XLSX | Local | pandas, openpyxl | 무료 | 0.1초 |
| DOCX | Local | python-docx | 무료 | 0.1초 |
| PPTX | Local | python-pptx | 무료 | 0.1초 |
| HWPX | Local | lxml (XML) | 무료 | 0.1초 |
| PDF (디지털) | Local | pdfplumber | 무료 | 0.5초 |
| PDF (이미지) | API | Upstage | 유료 | 3-10초 |
| HWP (구형) | API | Upstage | 유료 | 3-10초 |

#### 3.1.2 디지털 PDF 판별 알고리즘

```python
def _analyze_pdf(file_path):
    """PDF가 디지털(텍스트)인지 이미지인지 판별"""
    with pdfplumber.open(file_path) as pdf:
        sample_pages = pdf.pages[:3]  # 처음 3페이지 샘플링
        total_text_len = sum(len(page.extract_text() or "") for page in sample_pages)

        # 텍스트가 100자 이상이고 비율이 30% 이상이면 디지털
        is_digital = total_text_len > 100
        return is_digital
```

#### 3.1.3 병렬 처리

```python
MAX_WORKERS = min(32, (os.cpu_count() or 4) * 2)

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    future_to_file = {executor.submit(process, f): f for f in files}
    for future in as_completed(future_to_file):
        result = future.result()
        emit_progress(result)
```

#### 3.1.4 대용량 PDF 분할 처리

10페이지 초과 PDF는 자동 분할:
1. 10페이지 단위로 Split
2. 각 부분을 병렬로 API 요청
3. 결과를 순서대로 Merge

---

### 3.2 서식 보존 상세

#### 3.2.1 표 테두리 처리

```python
def _detect_table_border(table):
    """테이블 테두리 유무 감지"""
    # Word: XML에서 tblBorders 확인
    # Excel: cell.border 속성 확인
    # PDF: page.lines, page.rects 확인

    has_border = ...
    return 'bordered' if has_border else 'borderless'
```

#### 3.2.2 생성되는 HTML 클래스

| 클래스 | 의미 |
|-------|------|
| `.bordered` | 테두리 있는 테이블 |
| `.borderless` | 테두리 없는 테이블 |
| `.excel-table` | Excel 원본 테이블 |
| `.word-table` | Word 원본 테이블 |
| `.pdf-table` | PDF 원본 테이블 |
| `.sheet` | Excel 시트 |
| `.slide` | PowerPoint 슬라이드 |

---

### 3.3 MCP 서버 명세

#### 3.3.1 사용 가능한 도구 (Tools)

| 도구명 | 설명 | 파라미터 |
|-------|------|---------|
| `list_documents` | 검수 대기 문서 목록 | status: pending/reviewed/all |
| `read_document` | 문서 내용 읽기 | filename: 파일명 |
| `analyze_ocr_errors` | 잠재적 OCR 오류 분석 | filename: 파일명 |
| `save_reviewed_document` | 검수 완료 저장 | filename, content |
| `get_review_stats` | 검수 통계 조회 | - |
| `set_working_directory` | 작업 폴더 변경 | path: 경로 |
| `batch_review_with_prompt` | 검수 프롬프트 반환 | - |

#### 3.3.2 리소스 (Resources)

| 리소스 URI | 설명 |
|-----------|------|
| `prompts://review-system` | 검수 시스템 프롬프트 |
| `prompts://error-patterns` | OCR 오류 패턴 JSON |

---

### 3.4 OCR 오류 패턴 DB

```python
OCR_ERROR_PATTERNS = {
    # 한글 조사 오인식
    "을": ["Z", "z", "2", "ㅡ"],
    "를": ["Z", "z", "2"],
    "은": ["E", "e", "ㅡ"],
    "의": ["9", "Q", "q"],
    "이": ["0", "O", "o", "l", "1"],
    "가": ["7", "71", "7l"],

    # 법률 용어
    "조": ["초", "소"],
    "항": ["향", "왕"],
    "호": ["효", "후"],
    "법": ["벌", "범"],
    "제": ["게", "재"],

    # 숫자-문자 혼동
    "0": ["O", "o", "Q"],
    "1": ["l", "I", "|", "!"],
    "2": ["Z", "z"],
}
```

---

### 3.5 원클릭 MCP 설정

#### 3.5.1 Claude Desktop 설정 파일 위치

| OS | 경로 |
|----|------|
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Linux | `~/.config/claude/claude_desktop_config.json` |

#### 3.5.2 자동 주입되는 설정

```json
{
  "mcpServers": {
    "lawpro-converter": {
      "command": "python",
      "args": ["/path/to/mcp_server.py"],
      "env": {
        "LAWPRO_OUTPUT_DIR": "~/Documents/LawPro_Output"
      }
    }
  }
}
```

---

### 3.6 Gemini 백업 에이전트

#### 3.6.1 지원 모델

| 모델 ID | 이름 | 특징 |
|--------|------|------|
| `gemini-2.0-flash-exp` | Flash 2.0 | 최신, 가장 빠름 |
| `gemini-1.5-flash` | Flash 1.5 | 안정적 |
| `gemini-1.5-pro` | Pro 1.5 | 고품질 |

#### 3.6.2 Rate Limit 관리

- 요청 간 1초 대기
- 대용량 문서는 30,000자 청크로 분할
- 재시도 로직 (지수 백오프)

---

## 4. 데이터 흐름

```
[사용자]
    │
    ▼
[폴더 드래그] ──────────────────────────────────────────┐
    │                                                    │
    ▼                                                    ▼
[Electron Main] ────IPC────► [Python Engine]     [Upstage API]
    │                              │                     │
    │                              ▼                     │
    │                    ┌─────────────────────┐         │
    │                    │   FileProcessor     │◄────────┘
    │                    │                     │
    │                    │  ┌───────────────┐  │
    │                    │  │ ThreadPool    │  │
    │                    │  │ (병렬 처리)    │  │
    │                    │  └───────────────┘  │
    │                    └─────────────────────┘
    │                              │
    │◄────────JSON 로그────────────┘
    │
    ▼
[UI 업데이트] ───► [진행바, 로그, 결과 요약]
    │
    ▼
[Converted_HTML 폴더] ───► [MCP 서버] ───► [Claude Desktop]
                                                   │
                                                   ▼
                                          [Final_Reviewed 폴더]
```

---

## 5. 보안 고려사항

### 5.1 API 키 관리
- `electron-store`로 암호화 저장
- 메모리에 평문 보관 최소화
- .gitignore에 config 파일 제외

### 5.2 파일 접근
- 사용자가 명시적으로 선택한 폴더만 접근
- 시스템 파일 접근 차단
- 출력은 선택된 폴더 하위에만 생성

### 5.3 MCP 통신
- 로컬 소켓/파이프 사용 (네트워크 노출 없음)
- Claude Desktop의 보안 모델 준수

---

## 6. 성능 목표

| 지표 | 목표 | 비고 |
|-----|------|------|
| 디지털 PDF 변환 | < 0.5초/페이지 | 로컬 처리 |
| 이미지 PDF 변환 | < 5초/페이지 | Upstage API |
| Excel 변환 | < 0.1초/시트 | 로컬 처리 |
| 병렬 처리 효율 | > 80% | CPU 활용률 |
| 메모리 사용 | < 500MB | 일반 작업 시 |

---

## 7. 향후 개선 계획

### Phase 2
- [ ] 실시간 미리보기
- [ ] 배치 검수 자동화
- [ ] 커스텀 템플릿

### Phase 3
- [ ] 클라우드 동기화
- [ ] 팀 협업 기능
- [ ] AI 학습 데이터 수집

---

## 8. 문의

- 기술 지원: tech@lawpro.ai
- 버그 리포트: https://github.com/lawpro/fast-converter/issues
