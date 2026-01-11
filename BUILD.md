# LawPro Fast Converter - 빌드 및 배포 가이드

## 1. 개발 환경 설정

### 필수 요구사항
- **Node.js**: 18.x 이상
- **Python**: 3.9 이상
- **npm** 또는 **yarn**

### 초기 설정

```bash
# 1. 저장소 클론
git clone <repository-url>
cd converter

# 2. Node.js 의존성 설치
npm install

# 3. Python 의존성 설치
cd engine
pip install -r requirements.txt
cd ..
```

## 2. 개발 모드 실행 (테스트)

### 방법 1: npm 스크립트 사용
```bash
# 개발 모드로 실행 (DevTools 자동 열림)
npm run dev

# 또는 일반 실행
npm start
```

### 방법 2: 직접 실행
```bash
# Electron 직접 실행
npx electron .
```

### 개발 모드 특징
- DevTools가 자동으로 열림
- 소스 파일 변경 시 수동 재시작 필요
- 콘솔에서 오류 확인 가능

## 3. 디버깅

### Electron DevTools
- 자동으로 열리거나, `Ctrl+Shift+I` (Windows/Linux) 또는 `Cmd+Option+I` (macOS)
- Console 탭에서 JavaScript 오류 확인
- Network 탭에서 API 호출 확인

### Python 엔진 디버깅
```bash
# 직접 Python 스크립트 실행
cd engine
python main.py /path/to/test/folder

# 크레딧 테스트
python credit_manager.py balance
python credit_manager.py set-email kjccjk@hanmail.net  # 관리자 테스트
python credit_manager.py add basic  # 크레딧 충전 테스트
```

### 로그 확인
- 앱 내 로그 영역에서 실시간 확인
- Python stdout이 앱으로 전달됨

## 4. 빌드 (배포용)

### Windows 빌드
```bash
npm run build:win
```
출력: `dist/` 폴더에 `.exe` 설치 파일 및 portable 버전 생성

### macOS 빌드
```bash
npm run build:mac
```
출력: `dist/` 폴더에 `.dmg` 및 `.zip` 파일 생성

### Linux 빌드
```bash
npm run build:linux
```
출력: `dist/` 폴더에 `.AppImage` 및 `.deb` 파일 생성

### 전체 플랫폼 빌드
```bash
npm run build
```

## 5. 빌드 설정 (package.json)

### electron-builder 설정
```json
{
  "build": {
    "appId": "com.lawpro.fastconverter",
    "productName": "LawPro Fast Converter",
    "directories": {
      "output": "dist",
      "buildResources": "resources"
    },
    "files": [
      "src/**/*",
      "node_modules/**/*",
      "package.json"
    ],
    "extraResources": [
      {
        "from": "engine",
        "to": "engine",
        "filter": ["**/*"]
      }
    ]
  }
}
```

### 중요: engine 폴더 포함
- `extraResources`에 engine 폴더가 포함되어야 함
- 빌드 후 `resources/engine/` 경로에 Python 스크립트 위치

## 6. 아이콘 준비

### 필요한 아이콘 파일
```
resources/
├── icon.png      (512x512 이상, Linux용)
├── icon.ico      (Windows용, 256x256)
└── icon.icns     (macOS용)
```

### 아이콘 생성 도구
- [electron-icon-builder](https://www.npmjs.com/package/electron-icon-builder)
- 온라인: [CloudConvert](https://cloudconvert.com/png-to-ico)

## 7. 코드 서명 (선택사항)

### Windows
```bash
# EV 코드 서명 인증서 필요
export CSC_LINK="path/to/certificate.pfx"
export CSC_KEY_PASSWORD="password"
npm run build:win
```

### macOS
```bash
# Apple Developer 계정 필요
export APPLE_ID="your@email.com"
export APPLE_APP_SPECIFIC_PASSWORD="xxxx-xxxx-xxxx-xxxx"
npm run build:mac
```

## 8. 배포

### 수동 배포
1. `dist/` 폴더에서 설치 파일 확인
2. 파일 공유 또는 웹서버 업로드
3. 사용자에게 다운로드 링크 제공

### 자동 업데이트 (선택사항)
```bash
# electron-updater 설치
npm install electron-updater

# GitHub Releases 또는 S3 연동
```

## 9. 테스트 체크리스트

### 기능 테스트
- [ ] 폴더 선택 (드래그앤드롭 / 클릭)
- [ ] XLSX 변환
- [ ] DOCX 변환
- [ ] PPTX 변환
- [ ] HWPX 변환
- [ ] 디지털 PDF 변환 (로컬)
- [ ] 이미지 PDF 변환 (Upstage API)
- [ ] Clean HTML 생성
- [ ] Markdown 생성
- [ ] 크레딧 시스템 (충전, 차감, 관리자 우회)
- [ ] Gemini 검수
- [ ] OpenAI 검수
- [ ] Claude MCP 연결

### 크레딧 테스트
```bash
# 1. 일반 사용자 테스트
python engine/credit_manager.py set-email test@example.com
python engine/credit_manager.py balance  # 0원 확인
python engine/credit_manager.py add basic  # 11만원 충전
python engine/credit_manager.py check 100  # 5,500원 필요

# 2. 관리자 테스트
python engine/credit_manager.py set-email kjccjk@hanmail.net
python engine/credit_manager.py balance  # 무제한 확인
```

### 빌드 테스트
- [ ] Windows 설치 파일 실행
- [ ] macOS dmg 마운트 및 설치
- [ ] Linux AppImage 실행 권한 및 실행

## 10. 문제 해결

### Python을 찾을 수 없음
```bash
# Windows: Python 설치 후 PATH에 추가
# macOS/Linux: python3 명령어 확인
which python3
```

### 패키지 누락
```bash
cd engine
pip install -r requirements.txt
```

### 빌드 실패
```bash
# 캐시 삭제 후 재시도
rm -rf node_modules dist
npm install
npm run build
```

### 앱 실행 안됨 (macOS)
```bash
# 보안 설정에서 허용 필요
# 시스템 환경설정 > 보안 및 개인정보 보호 > 일반
```

## 11. 버전 관리

### 버전 업데이트
```bash
# package.json의 version 수정
npm version patch  # 1.0.0 -> 1.0.1
npm version minor  # 1.0.0 -> 1.1.0
npm version major  # 1.0.0 -> 2.0.0
```

### 변경 로그
- CHANGELOG.md 파일에 변경사항 기록 권장

## 12. 디렉토리 구조

```
converter/
├── src/                    # Electron 프론트엔드
│   ├── main.js            # 메인 프로세스
│   ├── preload.js         # 프리로드 스크립트
│   ├── renderer.js        # 렌더러 스크립트
│   └── index.html         # UI
├── engine/                 # Python 백엔드
│   ├── main.py            # 변환 엔진
│   ├── processor.py       # 파일 처리기
│   ├── cleaner.py         # HTML 클리너
│   ├── credit_manager.py  # 크레딧 관리
│   ├── gemini_agent.py    # Gemini 검수
│   ├── openai_agent.py    # OpenAI 검수
│   ├── mcp_server.py      # Claude MCP 서버
│   └── requirements.txt   # Python 의존성
├── resources/             # 빌드 리소스 (아이콘 등)
├── dist/                  # 빌드 출력
├── package.json           # Node.js 설정
└── BUILD.md              # 이 문서
```
