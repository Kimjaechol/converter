#!/usr/bin/env python3
"""
LawPro Converter - Admin Backend Server
========================================
관리자용 API 서버 (FastAPI)
- 통계 조회
- 회원 관리
- 오류 패턴 관리
- 학습 데이터 동기화
"""

import os
import json
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import jwt

# Supabase
try:
    from supabase import create_client, Client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False
    print("Warning: supabase not installed. Run: pip install supabase")

# ============================================================
# 환경 변수 및 설정
# ============================================================
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")  # service_role key for admin
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "change-this-secret-key")
JWT_SECRET = os.getenv("JWT_SECRET", "jwt-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# LLM 컨텍스트 제한 설정 (토큰 기준)
LLM_CONTEXT_LIMITS = {
    "gemini-2.0-flash": 1000000,    # 1M tokens
    "gemini-1.5-pro": 1000000,      # 1M tokens
    "gpt-4o": 128000,               # 128K tokens
    "gpt-4o-mini": 128000,
    "claude-3.5-sonnet": 200000,    # 200K tokens
    "claude-3-opus": 200000,
}

# 패턴당 평균 토큰 수 (한글 기준 더 보수적으로)
TOKENS_PER_PATTERN = 50

# 기본 설정
DEFAULT_CONFIG = {
    'max_patterns': 5000,            # 보수적 기본값 (GPT-4o 기준)
    'max_patterns_per_source': 2500,
    'min_usage_to_keep': 0,
    'cleanup_threshold': 6000,
    'prompt_pattern_limit': 100,
    'target_llm': 'gpt-4o',          # 기본 타겟 LLM
}


# ============================================================
# Supabase 클라이언트
# ============================================================
supabase: Optional[Client] = None

def get_supabase() -> Client:
    global supabase
    if supabase is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise HTTPException(500, "Supabase credentials not configured")
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return supabase


# ============================================================
# Pydantic 모델
# ============================================================
class AdminLogin(BaseModel):
    username: str
    password: str

class AdminToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class PatternCreate(BaseModel):
    original: str
    corrected: str
    source: str  # 'image_pdf' or 'digital_doc'
    context: str = ""
    category: str = "unknown"
    reason: str = ""

class PatternUpdate(BaseModel):
    original: Optional[str] = None
    corrected: Optional[str] = None
    source: Optional[str] = None
    category: Optional[str] = None
    reason: Optional[str] = None
    is_active: Optional[bool] = None

class PatternBatch(BaseModel):
    patterns: List[PatternCreate]

class ConfigUpdate(BaseModel):
    max_patterns: Optional[int] = None
    max_patterns_per_source: Optional[int] = None
    min_usage_to_keep: Optional[int] = None
    cleanup_threshold: Optional[int] = None
    prompt_pattern_limit: Optional[int] = None
    target_llm: Optional[str] = None

class UserUpdate(BaseModel):
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    credits: Optional[int] = None
    memo: Optional[str] = None

class CorrectionReport(BaseModel):
    file_name: str
    file_type: str  # 'image_pdf', 'hwpx', 'docx', etc.
    original: str
    corrected: str
    context: str = ""
    category: str = "unknown"
    reason: str = ""
    decision: str = "confirmed"  # 'confirmed', 'rejected', 'modified'
    user_id: Optional[str] = None


# ============================================================
# 인증
# ============================================================
security = HTTPBearer()

def create_jwt_token(data: dict) -> str:
    """JWT 토큰 생성"""
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    to_encode = data.copy()
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_jwt_token(token: str) -> dict:
    """JWT 토큰 검증"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")

async def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """현재 관리자 정보 반환"""
    payload = verify_jwt_token(credentials.credentials)
    if not payload.get("is_admin"):
        raise HTTPException(403, "Admin access required")
    return payload


# ============================================================
# 앱 초기화
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting LawPro Admin Server...")
    if HAS_SUPABASE and SUPABASE_URL and SUPABASE_KEY:
        try:
            get_supabase()
            print("Supabase connected")
        except Exception as e:
            print(f"Supabase connection failed: {e}")
    yield
    # Shutdown
    print("Shutting down...")

app = FastAPI(
    title="LawPro Converter Admin API",
    description="관리자용 API - 통계, 회원관리, 오류패턴 관리",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인만
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static 파일 서빙
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ============================================================
# 헬스체크 및 관리자 페이지
# ============================================================
@app.get("/")
async def root():
    return {"status": "ok", "service": "LawPro Admin API", "version": "1.0.0"}

@app.get("/admin")
async def admin_page():
    """관리자 대시보드 페이지"""
    admin_html = os.path.join(STATIC_DIR, "admin.html")
    if os.path.exists(admin_html):
        return FileResponse(admin_html)
    return {"error": "Admin page not found"}

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# ============================================================
# 인증 엔드포인트
# ============================================================
@app.post("/api/admin/login", response_model=AdminToken)
async def admin_login(login: AdminLogin):
    """관리자 로그인"""
    # 간단한 관리자 인증 (프로덕션에서는 DB 연동)
    # 환경변수로 설정: ADMIN_USERNAME, ADMIN_PASSWORD
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")

    if login.username != admin_username or login.password != admin_password:
        raise HTTPException(401, "Invalid credentials")

    token = create_jwt_token({
        "sub": login.username,
        "is_admin": True,
        "iat": datetime.utcnow().isoformat()
    })

    return AdminToken(
        access_token=token,
        expires_in=JWT_EXPIRATION_HOURS * 3600
    )


# ============================================================
# 대시보드 통계
# ============================================================
@app.get("/api/admin/stats/overview")
async def get_overview_stats(admin: dict = Depends(get_current_admin)):
    """전체 통계 개요"""
    db = get_supabase()

    stats = {
        "users": {"total": 0, "active": 0, "new_today": 0, "new_this_week": 0},
        "conversions": {"total": 0, "today": 0, "this_week": 0, "this_month": 0},
        "pages": {"total": 0, "today": 0},
        "patterns": {"total": 0, "image_pdf": 0, "digital_doc": 0, "active": 0},
        "corrections": {"total": 0, "confirmed": 0, "rejected": 0}
    }

    try:
        # 사용자 통계
        users = db.table("users").select("*", count="exact").execute()
        stats["users"]["total"] = users.count or 0

        active_users = db.table("users").select("*", count="exact").eq("is_active", True).execute()
        stats["users"]["active"] = active_users.count or 0

        today = datetime.utcnow().date().isoformat()
        new_today = db.table("users").select("*", count="exact").gte("created_at", today).execute()
        stats["users"]["new_today"] = new_today.count or 0

        week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
        new_week = db.table("users").select("*", count="exact").gte("created_at", week_ago).execute()
        stats["users"]["new_this_week"] = new_week.count or 0

        # 변환 통계
        conversions = db.table("conversions").select("*", count="exact").execute()
        stats["conversions"]["total"] = conversions.count or 0

        conv_today = db.table("conversions").select("*", count="exact").gte("created_at", today).execute()
        stats["conversions"]["today"] = conv_today.count or 0

        # 페이지 통계
        pages_result = db.table("conversions").select("page_count").execute()
        if pages_result.data:
            stats["pages"]["total"] = sum(r.get("page_count", 0) for r in pages_result.data)

        # 패턴 통계
        patterns = db.table("error_patterns").select("*", count="exact").execute()
        stats["patterns"]["total"] = patterns.count or 0

        image_patterns = db.table("error_patterns").select("*", count="exact").eq("source", "image_pdf").execute()
        stats["patterns"]["image_pdf"] = image_patterns.count or 0

        digital_patterns = db.table("error_patterns").select("*", count="exact").eq("source", "digital_doc").execute()
        stats["patterns"]["digital_doc"] = digital_patterns.count or 0

        active_patterns = db.table("error_patterns").select("*", count="exact").eq("is_active", True).execute()
        stats["patterns"]["active"] = active_patterns.count or 0

        # 수정 통계
        corrections = db.table("correction_logs").select("*", count="exact").execute()
        stats["corrections"]["total"] = corrections.count or 0

        confirmed = db.table("correction_logs").select("*", count="exact").eq("decision", "confirmed").execute()
        stats["corrections"]["confirmed"] = confirmed.count or 0

        rejected = db.table("correction_logs").select("*", count="exact").eq("decision", "rejected").execute()
        stats["corrections"]["rejected"] = rejected.count or 0

    except Exception as e:
        print(f"Stats error: {e}")

    return stats


@app.get("/api/admin/stats/conversions")
async def get_conversion_stats(
    period: str = Query("week", enum=["day", "week", "month", "year"]),
    admin: dict = Depends(get_current_admin)
):
    """기간별 변환 통계"""
    db = get_supabase()

    # 기간 설정
    if period == "day":
        start = datetime.utcnow() - timedelta(days=1)
    elif period == "week":
        start = datetime.utcnow() - timedelta(days=7)
    elif period == "month":
        start = datetime.utcnow() - timedelta(days=30)
    else:
        start = datetime.utcnow() - timedelta(days=365)

    try:
        result = db.table("conversions")\
            .select("file_type, page_count, created_at")\
            .gte("created_at", start.isoformat())\
            .execute()

        # 파일 타입별 집계
        by_type = {}
        total_pages = 0

        for r in result.data or []:
            ft = r.get("file_type", "unknown")
            by_type[ft] = by_type.get(ft, 0) + 1
            total_pages += r.get("page_count", 0)

        return {
            "period": period,
            "total_conversions": len(result.data or []),
            "total_pages": total_pages,
            "by_file_type": by_type
        }

    except Exception as e:
        raise HTTPException(500, f"Database error: {str(e)}")


# ============================================================
# 회원 관리
# ============================================================
@app.get("/api/admin/users")
async def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    admin: dict = Depends(get_current_admin)
):
    """회원 목록 조회"""
    db = get_supabase()

    try:
        query = db.table("users").select("*", count="exact")

        if search:
            query = query.or_(f"email.ilike.%{search}%,name.ilike.%{search}%")

        if is_active is not None:
            query = query.eq("is_active", is_active)

        # 페이지네이션
        offset = (page - 1) * limit
        result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()

        return {
            "users": result.data or [],
            "total": result.count or 0,
            "page": page,
            "limit": limit,
            "total_pages": ((result.count or 0) + limit - 1) // limit
        }

    except Exception as e:
        raise HTTPException(500, f"Database error: {str(e)}")


@app.get("/api/admin/users/{user_id}")
async def get_user(user_id: str, admin: dict = Depends(get_current_admin)):
    """회원 상세 조회"""
    db = get_supabase()

    try:
        result = db.table("users").select("*").eq("id", user_id).single().execute()

        if not result.data:
            raise HTTPException(404, "User not found")

        # 사용자의 변환 이력
        conversions = db.table("conversions")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .limit(20)\
            .execute()

        return {
            "user": result.data,
            "recent_conversions": conversions.data or []
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Database error: {str(e)}")


@app.patch("/api/admin/users/{user_id}")
async def update_user(
    user_id: str,
    update: UserUpdate,
    admin: dict = Depends(get_current_admin)
):
    """회원 정보 수정"""
    db = get_supabase()

    try:
        update_data = {k: v for k, v in update.dict().items() if v is not None}
        update_data["updated_at"] = datetime.utcnow().isoformat()

        result = db.table("users").update(update_data).eq("id", user_id).execute()

        if not result.data:
            raise HTTPException(404, "User not found")

        return {"success": True, "user": result.data[0]}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Database error: {str(e)}")


# ============================================================
# 오류 패턴 관리
# ============================================================
@app.get("/api/admin/patterns")
async def list_patterns(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    source: Optional[str] = Query(None, enum=["image_pdf", "digital_doc"]),
    sort_by: str = Query("effectiveness", enum=["effectiveness", "usage_count", "frequency", "created_at"]),
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    admin: dict = Depends(get_current_admin)
):
    """오류 패턴 목록 조회 (사용빈도순 정렬)"""
    db = get_supabase()

    try:
        query = db.table("error_patterns").select("*", count="exact")

        if source:
            query = query.eq("source", source)

        if is_active is not None:
            query = query.eq("is_active", is_active)

        if search:
            query = query.or_(f"original.ilike.%{search}%,corrected.ilike.%{search}%")

        # 정렬
        if sort_by == "effectiveness":
            # effectiveness = usage_count * 2 + frequency
            query = query.order("usage_count", desc=True).order("frequency", desc=True)
        elif sort_by == "usage_count":
            query = query.order("usage_count", desc=True)
        elif sort_by == "frequency":
            query = query.order("frequency", desc=True)
        else:
            query = query.order("created_at", desc=True)

        # 페이지네이션
        offset = (page - 1) * limit
        result = query.range(offset, offset + limit - 1).execute()

        # 효과성 점수 계산 추가
        patterns = []
        for p in result.data or []:
            p["effectiveness_score"] = (p.get("usage_count", 0) * 2) + p.get("frequency", 0)
            patterns.append(p)

        return {
            "patterns": patterns,
            "total": result.count or 0,
            "page": page,
            "limit": limit,
            "total_pages": ((result.count or 0) + limit - 1) // limit
        }

    except Exception as e:
        raise HTTPException(500, f"Database error: {str(e)}")


@app.post("/api/admin/patterns")
async def create_pattern(
    pattern: PatternCreate,
    admin: dict = Depends(get_current_admin)
):
    """오류 패턴 추가"""
    db = get_supabase()

    try:
        # 중복 체크
        existing = db.table("error_patterns")\
            .select("id")\
            .eq("original", pattern.original)\
            .eq("corrected", pattern.corrected)\
            .eq("source", pattern.source)\
            .execute()

        if existing.data:
            # 기존 패턴 frequency 증가
            db.table("error_patterns")\
                .update({"frequency": existing.data[0].get("frequency", 0) + 1})\
                .eq("id", existing.data[0]["id"])\
                .execute()
            return {"success": True, "action": "updated", "id": existing.data[0]["id"]}

        # 새 패턴 생성
        data = {
            "original": pattern.original,
            "corrected": pattern.corrected,
            "source": pattern.source,
            "context": pattern.context,
            "category": pattern.category,
            "reason": pattern.reason,
            "frequency": 1,
            "usage_count": 0,
            "is_active": True,
            "created_at": datetime.utcnow().isoformat()
        }

        result = db.table("error_patterns").insert(data).execute()

        return {"success": True, "action": "created", "pattern": result.data[0]}

    except Exception as e:
        raise HTTPException(500, f"Database error: {str(e)}")


@app.post("/api/admin/patterns/batch")
async def create_patterns_batch(
    batch: PatternBatch,
    admin: dict = Depends(get_current_admin)
):
    """오류 패턴 일괄 추가"""
    db = get_supabase()

    created = 0
    updated = 0
    errors = []

    for pattern in batch.patterns:
        try:
            # 중복 체크
            existing = db.table("error_patterns")\
                .select("id, frequency")\
                .eq("original", pattern.original)\
                .eq("corrected", pattern.corrected)\
                .eq("source", pattern.source)\
                .execute()

            if existing.data:
                db.table("error_patterns")\
                    .update({"frequency": existing.data[0].get("frequency", 0) + 1})\
                    .eq("id", existing.data[0]["id"])\
                    .execute()
                updated += 1
            else:
                data = {
                    "original": pattern.original,
                    "corrected": pattern.corrected,
                    "source": pattern.source,
                    "context": pattern.context,
                    "category": pattern.category,
                    "reason": pattern.reason,
                    "frequency": 1,
                    "usage_count": 0,
                    "is_active": True,
                    "created_at": datetime.utcnow().isoformat()
                }
                db.table("error_patterns").insert(data).execute()
                created += 1

        except Exception as e:
            errors.append({"pattern": pattern.original, "error": str(e)})

    return {
        "success": True,
        "created": created,
        "updated": updated,
        "errors": errors
    }


@app.patch("/api/admin/patterns/{pattern_id}")
async def update_pattern(
    pattern_id: str,
    update: PatternUpdate,
    admin: dict = Depends(get_current_admin)
):
    """오류 패턴 수정"""
    db = get_supabase()

    try:
        update_data = {k: v for k, v in update.dict().items() if v is not None}
        update_data["updated_at"] = datetime.utcnow().isoformat()

        result = db.table("error_patterns").update(update_data).eq("id", pattern_id).execute()

        if not result.data:
            raise HTTPException(404, "Pattern not found")

        return {"success": True, "pattern": result.data[0]}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Database error: {str(e)}")


@app.delete("/api/admin/patterns/{pattern_id}")
async def delete_pattern(
    pattern_id: str,
    admin: dict = Depends(get_current_admin)
):
    """오류 패턴 삭제"""
    db = get_supabase()

    try:
        result = db.table("error_patterns").delete().eq("id", pattern_id).execute()

        if not result.data:
            raise HTTPException(404, "Pattern not found")

        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Database error: {str(e)}")


@app.post("/api/admin/patterns/cleanup")
async def cleanup_patterns(
    max_patterns: Optional[int] = None,
    admin: dict = Depends(get_current_admin)
):
    """저사용 패턴 정리"""
    db = get_supabase()

    try:
        # 현재 설정 로드
        config_result = db.table("config").select("*").eq("key", "pattern_limits").single().execute()
        config = config_result.data.get("value", DEFAULT_CONFIG) if config_result.data else DEFAULT_CONFIG

        target_max = max_patterns or config.get("max_patterns", 5000)

        # 현재 패턴 수
        total = db.table("error_patterns").select("*", count="exact").execute()
        current_count = total.count or 0

        if current_count <= target_max:
            return {
                "success": True,
                "action": "none",
                "current_count": current_count,
                "target_max": target_max
            }

        # 효과성 점수 기준 하위 패턴 삭제
        # (usage_count * 2 + frequency) 가 낮은 순으로 삭제
        to_delete = current_count - target_max

        # 하위 패턴 조회
        low_patterns = db.table("error_patterns")\
            .select("id")\
            .order("usage_count", desc=False)\
            .order("frequency", desc=False)\
            .limit(to_delete)\
            .execute()

        deleted = 0
        for p in low_patterns.data or []:
            db.table("error_patterns").delete().eq("id", p["id"]).execute()
            deleted += 1

        return {
            "success": True,
            "action": "cleaned",
            "deleted": deleted,
            "remaining": current_count - deleted,
            "target_max": target_max
        }

    except Exception as e:
        raise HTTPException(500, f"Database error: {str(e)}")


# ============================================================
# 수정 내역 로그
# ============================================================
@app.get("/api/admin/corrections")
async def list_corrections(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    decision: Optional[str] = Query(None, enum=["confirmed", "rejected", "modified"]),
    file_type: Optional[str] = None,
    admin: dict = Depends(get_current_admin)
):
    """수정 내역 로그 조회"""
    db = get_supabase()

    try:
        query = db.table("correction_logs").select("*", count="exact")

        if decision:
            query = query.eq("decision", decision)

        if file_type:
            query = query.eq("file_type", file_type)

        offset = (page - 1) * limit
        result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()

        return {
            "corrections": result.data or [],
            "total": result.count or 0,
            "page": page,
            "limit": limit
        }

    except Exception as e:
        raise HTTPException(500, f"Database error: {str(e)}")


# ============================================================
# 설정 관리
# ============================================================
@app.get("/api/admin/config")
async def get_config(admin: dict = Depends(get_current_admin)):
    """설정 조회"""
    db = get_supabase()

    try:
        result = db.table("config").select("*").eq("key", "pattern_limits").single().execute()

        config = result.data.get("value", DEFAULT_CONFIG) if result.data else DEFAULT_CONFIG

        # LLM 컨텍스트 정보 추가
        target_llm = config.get("target_llm", "gpt-4o")
        llm_context = LLM_CONTEXT_LIMITS.get(target_llm, 128000)
        recommended_max = llm_context // TOKENS_PER_PATTERN // 2  # 50% 여유

        return {
            "config": config,
            "llm_info": {
                "target_llm": target_llm,
                "context_limit": llm_context,
                "tokens_per_pattern": TOKENS_PER_PATTERN,
                "recommended_max_patterns": recommended_max
            },
            "available_llms": list(LLM_CONTEXT_LIMITS.keys())
        }

    except Exception as e:
        # 설정이 없으면 기본값 반환
        return {
            "config": DEFAULT_CONFIG,
            "llm_info": {
                "target_llm": "gpt-4o",
                "context_limit": 128000,
                "tokens_per_pattern": TOKENS_PER_PATTERN,
                "recommended_max_patterns": 1280
            },
            "available_llms": list(LLM_CONTEXT_LIMITS.keys())
        }


@app.patch("/api/admin/config")
async def update_config(
    update: ConfigUpdate,
    admin: dict = Depends(get_current_admin)
):
    """설정 수정"""
    db = get_supabase()

    try:
        # 현재 설정 로드
        result = db.table("config").select("*").eq("key", "pattern_limits").single().execute()

        if result.data:
            current = result.data.get("value", DEFAULT_CONFIG)
        else:
            current = DEFAULT_CONFIG.copy()

        # 업데이트 적용
        for k, v in update.dict().items():
            if v is not None:
                current[k] = v

        # 저장
        if result.data:
            db.table("config")\
                .update({"value": current, "updated_at": datetime.utcnow().isoformat()})\
                .eq("key", "pattern_limits")\
                .execute()
        else:
            db.table("config").insert({
                "key": "pattern_limits",
                "value": current,
                "created_at": datetime.utcnow().isoformat()
            }).execute()

        return {"success": True, "config": current}

    except Exception as e:
        raise HTTPException(500, f"Database error: {str(e)}")


# ============================================================
# 클라이언트용 API (인증 불필요)
# ============================================================
@app.post("/api/corrections/report")
async def report_correction(report: CorrectionReport):
    """클라이언트에서 수정 내역 보고"""
    db = get_supabase()

    try:
        # 수정 로그 저장
        log_data = {
            "file_name": report.file_name,
            "file_type": report.file_type,
            "original": report.original,
            "corrected": report.corrected,
            "context": report.context,
            "category": report.category,
            "reason": report.reason,
            "decision": report.decision,
            "user_id": report.user_id,
            "created_at": datetime.utcnow().isoformat()
        }

        db.table("correction_logs").insert(log_data).execute()

        # confirmed인 경우 패턴으로 추가
        if report.decision == "confirmed":
            source = "image_pdf" if report.file_type in ["pdf", "image_pdf"] else "digital_doc"

            # 중복 체크
            existing = db.table("error_patterns")\
                .select("id, frequency")\
                .eq("original", report.original)\
                .eq("corrected", report.corrected)\
                .eq("source", source)\
                .execute()

            if existing.data:
                # frequency 증가
                db.table("error_patterns")\
                    .update({"frequency": existing.data[0].get("frequency", 0) + 1})\
                    .eq("id", existing.data[0]["id"])\
                    .execute()
            else:
                # 새 패턴 생성
                pattern_data = {
                    "original": report.original,
                    "corrected": report.corrected,
                    "source": source,
                    "context": report.context,
                    "category": report.category,
                    "reason": report.reason,
                    "frequency": 1,
                    "usage_count": 0,
                    "is_active": True,
                    "created_at": datetime.utcnow().isoformat()
                }
                db.table("error_patterns").insert(pattern_data).execute()

        return {"success": True}

    except Exception as e:
        raise HTTPException(500, f"Database error: {str(e)}")


@app.get("/api/patterns/active")
async def get_active_patterns(
    source: Optional[str] = Query(None, enum=["image_pdf", "digital_doc"]),
    limit: int = Query(100, ge=1, le=500)
):
    """활성 패턴 조회 (클라이언트용)"""
    db = get_supabase()

    try:
        query = db.table("error_patterns")\
            .select("original, corrected, source, category, frequency, usage_count")\
            .eq("is_active", True)

        if source:
            query = query.eq("source", source)

        # 효과성 점수순 정렬
        result = query\
            .order("usage_count", desc=True)\
            .order("frequency", desc=True)\
            .limit(limit)\
            .execute()

        patterns = []
        for p in result.data or []:
            p["effectiveness_score"] = (p.get("usage_count", 0) * 2) + p.get("frequency", 0)
            patterns.append(p)

        return {"patterns": patterns, "count": len(patterns)}

    except Exception as e:
        raise HTTPException(500, f"Database error: {str(e)}")


@app.post("/api/patterns/mark-used")
async def mark_pattern_used(original: str, corrected: str, source: Optional[str] = None):
    """패턴 사용 기록 (AI 검수 후 호출)"""
    db = get_supabase()

    try:
        query = db.table("error_patterns")\
            .select("id, usage_count")\
            .eq("original", original)\
            .eq("corrected", corrected)

        if source:
            query = query.eq("source", source)

        result = query.execute()

        for p in result.data or []:
            db.table("error_patterns")\
                .update({
                    "usage_count": p.get("usage_count", 0) + 1,
                    "last_used": datetime.utcnow().isoformat()
                })\
                .eq("id", p["id"])\
                .execute()

        return {"success": True, "matched": len(result.data or [])}

    except Exception as e:
        raise HTTPException(500, f"Database error: {str(e)}")


# ============================================================
# 메인 실행
# ============================================================
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
