# LawPro Admin Server 배포 가이드

이 가이드는 LawPro 관리자 서버를 Supabase(데이터베이스)와 Railway(서버)에 배포하는 방법을 설명합니다.

## 목차
1. [Supabase 설정](#1-supabase-설정)
2. [Railway 배포](#2-railway-배포)
3. [Electron 앱 연동](#3-electron-앱-연동)
4. [관리자 페이지 접속](#4-관리자-페이지-접속)

---

## 1. Supabase 설정

### 1.1. Supabase 계정 생성
1. https://supabase.com 접속
2. GitHub 계정으로 가입 (무료)
3. "New Project" 클릭

### 1.2. 프로젝트 생성
- **Organization**: 개인 또는 조직 선택
- **Project name**: `lawpro-converter` (원하는 이름)
- **Database Password**: 안전한 비밀번호 설정 (저장해두세요!)
- **Region**: `Northeast Asia (Seoul)` 선택 (한국 사용자 기준)
- **Pricing Plan**: Free tier로 시작

> 생성까지 2-3분 소요됩니다.

### 1.3. 데이터베이스 스키마 생성
1. 프로젝트 대시보드에서 왼쪽 메뉴 **"SQL Editor"** 클릭
2. **"New Query"** 클릭
3. `server/supabase_schema.sql` 파일 내용 전체 복사하여 붙여넣기
4. **"Run"** 버튼 클릭 (Ctrl+Enter)
5. "Success" 메시지 확인

### 1.4. API 키 확인
1. 왼쪽 메뉴 **"Project Settings"** (톱니바퀴 아이콘)
2. **"API"** 탭 클릭
3. 다음 정보 복사하여 저장:
   - **Project URL**: `https://xxxxx.supabase.co`
   - **service_role key**: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` (비밀 키)

> ⚠️ **주의**: `service_role key`는 절대 공개하지 마세요! 이 키는 RLS를 우회합니다.

---

## 2. Railway 배포

### 2.1. Railway 계정 생성
1. https://railway.app 접속
2. GitHub 계정으로 가입 (무료 티어: $5/월 크레딧)

### 2.2. 새 프로젝트 생성

#### 방법 A: GitHub 연동 (권장)
1. **"New Project"** 클릭
2. **"Deploy from GitHub repo"** 선택
3. GitHub 저장소 연결 (권한 부여 필요)
4. 저장소 선택 후 `server` 폴더 지정

#### 방법 B: CLI 사용
```bash
# Railway CLI 설치
npm install -g @railway/cli

# 로그인
railway login

# 프로젝트 생성 및 연결
cd server
railway init
railway up
```

### 2.3. 환경 변수 설정
1. Railway 대시보드에서 프로젝트 선택
2. **"Variables"** 탭 클릭
3. 다음 환경 변수 추가:

| 변수명 | 값 | 설명 |
|--------|-----|------|
| `SUPABASE_URL` | `https://xxxxx.supabase.co` | Supabase 프로젝트 URL |
| `SUPABASE_KEY` | `eyJhbGci...` | Supabase service_role 키 |
| `ADMIN_USERNAME` | `admin` | 관리자 로그인 ID |
| `ADMIN_PASSWORD` | `your-secure-password` | 관리자 비밀번호 (변경 필수!) |
| `JWT_SECRET` | `random-32-char-string` | JWT 암호화 키 (랜덤 생성) |

> JWT_SECRET 생성 예: `openssl rand -hex 32`

### 2.4. 배포 확인
1. **"Deployments"** 탭에서 배포 상태 확인
2. 성공 시 **"Generate Domain"** 클릭
3. 생성된 URL 확인 (예: `lawpro-admin-production.up.railway.app`)

### 2.5. 헬스 체크
```bash
curl https://your-railway-url.up.railway.app/health
# 응답: {"status":"healthy","timestamp":"..."}
```

---

## 3. Electron 앱 연동

### 3.1. 서버 URL 설정
`engine/error_learning.py`에서 서버 URL 업데이트:

```python
ERROR_COLLECTION_SERVER = os.environ.get(
    'LAWPRO_ERROR_SERVER',
    'https://your-railway-url.up.railway.app'  # ← 실제 Railway URL로 변경
)
```

또는 환경 변수로 설정:
```bash
# .env 파일
LAWPRO_ERROR_SERVER=https://your-railway-url.up.railway.app
```

### 3.2. 오류 수정 데이터 동기화
앱에서 사용자가 오류를 수정하면 자동으로 서버에 전송됩니다:

```javascript
// src/renderer.js에서 자동 호출
await window.lawpro.collectCorrections(corrections);
```

---

## 4. 관리자 페이지 접속

### 4.1. 관리자 로그인
1. 브라우저에서 접속: `https://your-railway-url.up.railway.app/admin`
2. 설정한 관리자 ID/비밀번호로 로그인

### 4.2. 주요 기능

#### 대시보드
- 총 회원수, 오늘 가입, 변환 통계
- 오류 패턴 수, 수정 내역 통계

#### 회원 관리
- 회원 목록 조회/검색
- 회원 활성화/비활성화
- 크레딧 관리

#### 오류 패턴 관리
- 효과성 점수순 정렬 (사용횟수 × 2 + 제출횟수)
- 패턴 추가/수정/삭제
- 저사용 패턴 일괄 정리

#### 설정 관리
- 타겟 LLM 설정 (GPT-4o, Gemini, Claude)
- 최대 패턴 수 설정
- 자동 정리 임계값 설정

---

## 5. LLM별 권장 설정

| LLM 모델 | 컨텍스트 | 권장 max_patterns | 설명 |
|----------|----------|-------------------|------|
| GPT-4o | 128K | 2,000 | 기본 설정 |
| GPT-4o-mini | 128K | 2,000 | 경제적 옵션 |
| Gemini 2.0 Flash | 1M | 10,000 | 대용량 처리 |
| Gemini 1.5 Pro | 1M | 10,000 | 고품질 |
| Claude 3.5 Sonnet | 200K | 3,500 | 균형 잡힌 옵션 |

> 패턴당 약 50토큰 사용. 프롬프트 기타 요소에 5K 토큰 필요.

---

## 6. 비용 정보

### Supabase (무료 티어)
- 500MB 데이터베이스
- 1GB 파일 스토리지
- 2GB 대역폭/월
- 50,000 MAU

### Railway (Starter)
- $5/월 크레딧 무료 제공
- 500시간 실행 시간
- 100GB 대역폭

> 초기에는 무료 티어로 충분합니다. 사용량 증가 시 유료 플랜 전환.

---

## 7. 문제 해결

### 배포 실패 시
```bash
# Railway 로그 확인
railway logs

# 로컬 테스트
cd server
pip install -r requirements.txt
uvicorn main:app --reload
```

### 데이터베이스 연결 실패 시
1. Supabase 대시보드에서 프로젝트 상태 확인
2. API 키가 service_role 키인지 확인 (anon 키 아님)
3. Railway 환경 변수가 올바른지 확인

### 관리자 로그인 실패 시
1. Railway 환경 변수 `ADMIN_USERNAME`, `ADMIN_PASSWORD` 확인
2. JWT_SECRET이 설정되어 있는지 확인

---

## 8. API 엔드포인트 요약

### 공개 API (인증 불필요)
- `GET /health` - 헬스 체크
- `GET /admin` - 관리자 페이지
- `POST /api/corrections/report` - 수정 내역 보고
- `GET /api/patterns/active` - 활성 패턴 조회
- `POST /api/patterns/mark-used` - 패턴 사용 기록

### 관리자 API (JWT 인증 필요)
- `POST /api/admin/login` - 관리자 로그인
- `GET /api/admin/stats/overview` - 통계 개요
- `GET /api/admin/users` - 회원 목록
- `GET /api/admin/patterns` - 패턴 목록
- `POST /api/admin/patterns/cleanup` - 패턴 정리
- `GET /api/admin/config` - 설정 조회
- `PATCH /api/admin/config` - 설정 수정

---

## 9. 보안 체크리스트

- [ ] `ADMIN_PASSWORD`를 강력한 비밀번호로 변경
- [ ] `JWT_SECRET`을 랜덤 문자열로 설정
- [ ] Supabase `service_role` 키를 절대 공개하지 않음
- [ ] HTTPS만 사용 (Railway 기본 제공)
- [ ] 정기적으로 관리자 비밀번호 변경

---

문의사항이 있으시면 GitHub Issues를 통해 연락해주세요.
