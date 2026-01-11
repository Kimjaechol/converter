# 🎯 LawPro Fast Converter - 초보자용 설치 및 실행 가이드

> 이 문서는 개발 경험이 없는 분도 따라할 수 있도록 작성되었습니다.

---

## 📋 목차
1. [필수 프로그램 설치하기](#1-필수-프로그램-설치하기)
2. [앱 실행하기 (개발자 모드)](#2-앱-실행하기-개발자-모드)
3. [설치 파일 만들기 (빌드)](#3-설치-파일-만들기-빌드)
4. [다른 컴퓨터에 배포하기](#4-다른-컴퓨터에-배포하기)
5. [문제 해결](#5-문제-해결)

---

## 1. 필수 프로그램 설치하기

앱을 실행하려면 먼저 2가지 프로그램을 설치해야 합니다.

### 1-1. Node.js 설치 (필수)

Node.js는 앱의 화면(UI)을 실행하는데 필요합니다.

**Windows:**
1. https://nodejs.org 접속
2. **"LTS"** 버전 다운로드 (안정적인 버전)
3. 다운로드된 `.msi` 파일 실행
4. "Next" 계속 클릭하며 설치 완료

**macOS:**
1. https://nodejs.org 접속
2. **"LTS"** 버전 다운로드
3. 다운로드된 `.pkg` 파일 실행하여 설치

**설치 확인:**
```bash
# 터미널(명령 프롬프트)을 열고 입력:
node --version
# v18.x.x 또는 v20.x.x 등이 나오면 성공!

npm --version
# 9.x.x 또는 10.x.x 등이 나오면 성공!
```

### 1-2. Python 설치 (필수)

Python은 문서 변환 엔진을 실행하는데 필요합니다.

**Windows:**
1. https://python.org 접속
2. "Downloads" > "Download Python 3.12.x" 클릭
3. 다운로드된 파일 실행
4. **중요!** 설치 시작 화면에서 **"Add Python to PATH"** 체크박스를 반드시 체크!
5. "Install Now" 클릭하여 설치

**macOS:**
1. https://python.org 접속
2. "Downloads" > "Download Python 3.12.x" 클릭
3. 다운로드된 `.pkg` 파일 실행하여 설치

**설치 확인:**
```bash
# 터미널(명령 프롬프트)을 열고 입력:
python --version
# 또는
python3 --version
# Python 3.9.x 이상이 나오면 성공!
```

---

## 2. 앱 실행하기 (개발자 모드)

이제 앱을 테스트해볼 수 있습니다.

### 2-1. 터미널(명령 프롬프트) 열기

**Windows:**
- 시작 메뉴에서 "cmd" 검색 후 "명령 프롬프트" 실행
- 또는 시작 메뉴에서 "PowerShell" 검색 후 실행

**macOS:**
- Spotlight(Cmd+Space)에서 "Terminal" 검색 후 실행
- 또는 응용 프로그램 > 유틸리티 > 터미널

### 2-2. 프로젝트 폴더로 이동

```bash
# converter 폴더가 있는 경로로 이동
# 예시 (실제 경로에 맞게 수정하세요):

# Windows 예시:
cd C:\Users\사용자이름\converter

# macOS 예시:
cd /Users/사용자이름/converter

# 현재 폴더 확인:
# Windows: dir
# macOS/Linux: ls
```

### 2-3. 필요한 패키지 설치 (최초 1회만)

```bash
# Step 1: Node.js 패키지 설치 (1-2분 소요)
npm install

# Step 2: Python 패키지 설치
# Windows:
pip install -r engine/requirements.txt

# macOS/Linux:
pip3 install -r engine/requirements.txt
```

**설치 중 에러가 나면?**
- "npm ERR!" → Node.js 설치가 제대로 안된 것. 1-1 단계 다시 확인
- "pip: command not found" → Python 설치가 제대로 안된 것. 1-2 단계 다시 확인

### 2-4. 앱 실행하기

```bash
# 개발자 모드로 실행 (오류를 확인할 수 있음)
npm run dev
```

**실행 성공하면:**
- 새 창이 열리며 앱이 나타납니다
- DevTools(개발자 도구)가 함께 열립니다 - 오류 확인용이니 무시해도 됩니다
- 앱을 사용해보고 테스트하세요!

**앱 종료:**
- 창의 X 버튼을 클릭하거나
- 터미널에서 `Ctrl+C` 입력

---

## 3. 설치 파일 만들기 (빌드)

다른 컴퓨터에 배포하려면 설치 파일을 만들어야 합니다.

### 3-1. 아이콘 준비 (선택사항)

앱 아이콘을 사용하려면 `resources` 폴더에 아이콘 파일을 넣으세요:

```bash
# resources 폴더 만들기
mkdir resources
```

필요한 아이콘:
- `resources/icon.ico` - Windows용 (256x256 픽셀)
- `resources/icon.icns` - macOS용
- `resources/icon.png` - Linux용 (512x512 픽셀)

아이콘이 없어도 빌드는 됩니다 (기본 아이콘 사용).

### 3-2. 빌드 실행

```bash
# Windows용 설치파일 만들기:
npm run build:win

# macOS용 설치파일 만들기:
npm run build:mac

# Linux용 설치파일 만들기:
npm run build:linux
```

**빌드에 5-10분 정도 소요됩니다. 기다려주세요.**

### 3-3. 빌드 결과물 확인

빌드가 완료되면 `dist` 폴더에 설치 파일이 생성됩니다:

```
dist/
├── LawPro Fast Converter Setup 1.0.0.exe    (Windows 설치 파일)
├── LawPro Fast Converter-1.0.0-portable.exe (Windows 포터블 버전)
├── LawPro Fast Converter-1.0.0.dmg          (macOS 설치 파일)
├── LawPro Fast Converter-1.0.0.AppImage     (Linux 실행 파일)
└── LawPro Fast Converter-1.0.0.deb          (Linux Debian 패키지)
```

**참고:** 현재 운영체제에서는 해당 운영체제용 파일만 만들어집니다.
- Windows에서는 .exe 파일만
- macOS에서는 .dmg 파일만
- Linux에서는 .AppImage, .deb 파일만

---

## 4. 다른 컴퓨터에 배포하기

### 4-1. 배포 방법

1. `dist` 폴더의 설치 파일을 USB, 클라우드(구글 드라이브, 네이버 클라우드 등)에 복사
2. 사용할 컴퓨터에서 다운로드
3. 설치 파일 실행하여 설치

### 4-2. 사용자 컴퓨터 요구사항

**필수:**
- Python 3.9 이상 설치 (변환 엔진에 필요)
- pip로 필요한 패키지 설치:
  ```bash
  pip install python-pptx python-docx openpyxl beautifulsoup4 lxml pdf2image PyMuPDF google-generativeai openai httpx mcp markdown
  ```

**이미지 PDF 변환을 사용하려면:**
- Upstage API 키 필요 (유료)
- `~/.lawpro/config.json` 파일에 API 키 설정

### 4-3. API 키 설정하기

변환 기능을 사용하려면 API 키가 필요합니다:

```json
// ~/.lawpro/config.json 파일 생성 (경로: 사용자 홈 폴더 아래 .lawpro 폴더)
// Windows: C:\Users\사용자이름\.lawpro\config.json
// macOS: /Users/사용자이름/.lawpro/config.json

{
  "UPSTAGE_API_KEY": "여기에 Upstage API 키 입력",
  "GEMINI_API_KEY": "여기에 Gemini API 키 입력",
  "OPENAI_API_KEY": "여기에 OpenAI API 키 입력"
}
```

---

## 5. 문제 해결

### 문제: "npm: command not found"
**원인:** Node.js가 설치되지 않았거나 PATH에 추가되지 않음
**해결:** Node.js를 다시 설치하세요. 설치 후 터미널을 다시 열어주세요.

### 문제: "python: command not found" 또는 "pip: command not found"
**원인:** Python이 설치되지 않았거나 PATH에 추가되지 않음
**해결:**
- Windows: Python 설치 시 "Add Python to PATH" 체크 후 재설치
- macOS: `python3` 또는 `pip3` 명령어 사용

### 문제: 앱 실행 시 "Cannot find module" 에러
**원인:** Node.js 패키지가 설치되지 않음
**해결:** `npm install` 명령 실행

### 문제: 변환 시 "ModuleNotFoundError" 에러
**원인:** Python 패키지가 설치되지 않음
**해결:** `pip install -r engine/requirements.txt` 명령 실행

### 문제: Windows에서 빌드 실패
**해결:**
```bash
# node_modules 삭제 후 재설치
rmdir /s node_modules
del package-lock.json
npm install
npm run build:win
```

### 문제: macOS에서 앱 실행 시 "확인되지 않은 개발자" 경고
**해결:**
1. 시스템 환경설정 > 보안 및 개인정보 보호 > 일반
2. "확인 없이 열기" 버튼 클릭
3. 또는 앱을 우클릭 > "열기" 선택

### 문제: 크레딧이 부족하다고 나옴
**해결:**
- 관리자 이메일(kjccjk@hanmail.net)로 로그인하면 무제한 사용 가능
- 또는 크레딧 충전 기능 사용

---

## 📞 도움이 필요하면?

1. 오류 메시지를 복사해두세요
2. 어떤 단계에서 문제가 발생했는지 기록하세요
3. 개발자에게 문의하세요

---

## 🚀 빠른 시작 요약

```bash
# 1. 프로젝트 폴더로 이동
cd converter

# 2. 패키지 설치 (최초 1회)
npm install
pip install -r engine/requirements.txt

# 3. 앱 실행 (테스트)
npm run dev

# 4. 설치 파일 만들기 (배포용)
npm run build:win    # Windows
npm run build:mac    # macOS
npm run build:linux  # Linux
```

이게 전부입니다! 🎉
