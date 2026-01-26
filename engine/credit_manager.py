#!/usr/bin/env python3
"""
LawPro Fast Converter - Credit Manager
=======================================
문서 변환 크레딧 관리 시스템

Pricing (부가세 별도):
■ 본인 API 키 사용 시:
  - 이미지 PDF/이미지 파일 (OCR): 장당 50원
  - 일반 문서 (DOCX, HWPX, XLSX, PPTX, 디지털 PDF): 무료

■ API 키 없이 사용 시 (회사 제공):
  - 이미지 PDF/이미지 파일 (OCR): 장당 70원
  - 일반 문서: 장당 20원

Admin:
- ID: admin / PW: 3436 → 무제한 크레딧
- 관리자가 특정 회원에게 크레딧 부여 가능

Signup:
- 신규 가입 시 1,000 크레딧 무료 지급 (가입환영 크레딧)
"""

import os
import json
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path


# ============================================================
# 크레딧 요금 설정
# ============================================================
# 본인 API 키 사용 시
CREDIT_PER_PAGE_OCR = 50           # 이미지 PDF/이미지 파일 (OCR 포함): 장당 50원 (부가세 별도)
CREDIT_PER_PAGE_GENERAL = 0        # 일반 문서: 무료 (본인 API 키 사용 시)

# API 키 없이 사용 시 (회사 제공 키 사용)
CREDIT_PER_PAGE_OCR_NOKEY = 70     # 이미지 PDF/이미지 파일 (OCR): 장당 70원 (부가세 별도)
CREDIT_PER_PAGE_GENERAL_NOKEY = 20 # 일반 문서: 장당 20원 (부가세 별도)

WELCOME_CREDITS = 1000          # 가입환영 크레딧

CREDIT_PACKAGES = {
    "basic": {"price": 50000, "credits": 50000, "label": "5만원"},
    "standard": {"price": 100000, "credits": 100000, "label": "10만원"},
    "premium": {"price": 300000, "credits": 300000, "label": "30만원"}
}

# ============================================================
# 관리자 인증
# ============================================================
ADMIN_ID = "admin"
ADMIN_PASSWORD_HASH = hashlib.sha256("3436".encode()).hexdigest()

# 하위호환: 관리자 이메일 (기존)
ADMIN_EMAILS = [
    "kjccjk@hanmail.net"
]

# OCR 대상 확장자 (장당 50원)
OCR_EXTENSIONS = (
    '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif', '.webp'
)


def _hash_password(password: str) -> str:
    """비밀번호 SHA-256 해시"""
    return hashlib.sha256(password.encode()).hexdigest()


def is_ocr_file(file_path: str) -> bool:
    """OCR 대상 파일 여부 (이미지 파일)"""
    ext = os.path.splitext(file_path)[1].lower()
    return ext in OCR_EXTENSIONS


def is_image_pdf(file_path: str, is_digital: bool = None) -> bool:
    """이미지 PDF 여부"""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.pdf' and is_digital is False:
        return True
    return False


def get_credit_per_page(file_path: str, is_digital_pdf: bool = None, has_own_key: bool = True) -> int:
    """
    파일 유형별 장당 크레딧 반환

    Args:
        file_path: 파일 경로
        is_digital_pdf: PDF인 경우 디지털 여부 (True=디지털, False=이미지)
        has_own_key: 사용자가 본인 API 키를 사용하는지 여부

    Returns:
        장당 크레딧
        - 본인 키 사용: OCR=50, 일반=0(무료)
        - 키 없음: OCR=70, 일반=20
    """
    ext = os.path.splitext(file_path)[1].lower()

    # 이미지 파일 → OCR 요금
    if ext in OCR_EXTENSIONS:
        return CREDIT_PER_PAGE_OCR if has_own_key else CREDIT_PER_PAGE_OCR_NOKEY

    # 이미지 PDF → OCR 요금
    if ext == '.pdf' and is_digital_pdf is False:
        return CREDIT_PER_PAGE_OCR if has_own_key else CREDIT_PER_PAGE_OCR_NOKEY

    # 그 외 (디지털 PDF, docx, hwpx, xlsx, pptx 등) → 일반 요금
    return CREDIT_PER_PAGE_GENERAL if has_own_key else CREDIT_PER_PAGE_GENERAL_NOKEY


class CreditManager:
    """크레딧 관리 클래스"""

    def __init__(self, storage_path: Optional[str] = None):
        """
        Args:
            storage_path: 크레딧 데이터 저장 경로 (기본: ~/.lawpro/credits.json)
        """
        if storage_path:
            self.storage_path = storage_path
        else:
            home_dir = os.path.expanduser("~")
            lawpro_dir = os.path.join(home_dir, ".lawpro")
            os.makedirs(lawpro_dir, exist_ok=True)
            self.storage_path = os.path.join(lawpro_dir, "credits.json")

        # 회원 DB 경로 (관리자 기능용)
        self.users_path = os.path.join(os.path.dirname(self.storage_path), "users.json")

        self._load_data()
        self._load_users()

    def _load_data(self):
        """저장된 데이터 로드"""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                # 기존 데이터 마이그레이션
                if "user_id" not in self.data:
                    self.data["user_id"] = ""
            except (json.JSONDecodeError, IOError):
                self.data = self._default_data()
        else:
            self.data = self._default_data()

    def _default_data(self) -> Dict[str, Any]:
        """기본 데이터 구조"""
        return {
            "user_id": "",
            "user_email": "",
            "credits": 0,
            "is_admin": False,
            "is_registered": False,
            "purchase_history": [],
            "usage_history": [],
            "total_pages_converted": 0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

    def _save_data(self):
        """데이터 저장"""
        self.data["updated_at"] = datetime.now().isoformat()
        with open(self.storage_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def _load_users(self):
        """회원 DB 로드 (관리자 기능)"""
        if os.path.exists(self.users_path):
            try:
                with open(self.users_path, 'r', encoding='utf-8') as f:
                    self.users = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.users = {"users": {}}
        else:
            self.users = {"users": {}}

    def _save_users(self):
        """회원 DB 저장"""
        with open(self.users_path, 'w', encoding='utf-8') as f:
            json.dump(self.users, f, ensure_ascii=False, indent=2)

    # ============================================================
    # 회원 가입 / 로그인
    # ============================================================

    def register(self, user_id: str, password: str, email: str = "") -> Dict[str, Any]:
        """
        회원 가입

        Args:
            user_id: 사용자 ID
            password: 비밀번호
            email: 이메일 (선택)

        Returns:
            가입 결과 (성공 시 1000 크레딧 지급)
        """
        user_id = user_id.strip().lower()

        # ID 유효성 검사
        if len(user_id) < 2:
            return {"success": False, "message": "아이디는 2자 이상이어야 합니다"}
        if len(password) < 2:
            return {"success": False, "message": "비밀번호는 2자 이상이어야 합니다"}

        # 중복 확인
        if user_id in self.users.get("users", {}):
            return {"success": False, "message": "이미 존재하는 아이디입니다"}

        # 관리자 계정 확인
        is_admin = (user_id == ADMIN_ID and _hash_password(password) == ADMIN_PASSWORD_HASH)

        # 회원 데이터 생성
        user_data = {
            "password_hash": _hash_password(password),
            "email": email.strip(),
            "credits": 999999999 if is_admin else WELCOME_CREDITS,
            "is_admin": is_admin,
            "total_pages_converted": 0,
            "registered_at": datetime.now().isoformat(),
            "usage_history": [],
            "purchase_history": []
        }

        # 저장
        self.users.setdefault("users", {})[user_id] = user_data
        self._save_users()

        # 현재 디바이스에도 로그인 처리
        self.data["user_id"] = user_id
        self.data["user_email"] = email
        self.data["credits"] = user_data["credits"]
        self.data["is_admin"] = is_admin
        self.data["is_registered"] = True
        self._save_data()

        welcome_msg = "관리자 계정으로 등록되었습니다. 무제한 사용 가능합니다." if is_admin else f"가입이 완료되었습니다! 가입환영 {WELCOME_CREDITS:,} 크레딧이 지급되었습니다."

        return {
            "success": True,
            "user_id": user_id,
            "credits": user_data["credits"],
            "is_admin": is_admin,
            "message": welcome_msg
        }

    def login(self, user_id: str, password: str) -> Dict[str, Any]:
        """
        로그인

        Args:
            user_id: 사용자 ID
            password: 비밀번호

        Returns:
            로그인 결과
        """
        user_id = user_id.strip().lower()
        users = self.users.get("users", {})

        if user_id not in users:
            return {"success": False, "message": "존재하지 않는 아이디입니다"}

        user_data = users[user_id]

        if user_data["password_hash"] != _hash_password(password):
            return {"success": False, "message": "비밀번호가 올바르지 않습니다"}

        # 로그인 성공 → 로컬 데이터 동기화
        self.data["user_id"] = user_id
        self.data["user_email"] = user_data.get("email", "")
        self.data["credits"] = user_data["credits"]
        self.data["is_admin"] = user_data.get("is_admin", False)
        self.data["is_registered"] = True
        self.data["total_pages_converted"] = user_data.get("total_pages_converted", 0)
        self._save_data()

        return {
            "success": True,
            "user_id": user_id,
            "credits": user_data["credits"],
            "is_admin": user_data.get("is_admin", False),
            "message": "로그인 성공"
        }

    # ============================================================
    # 이메일 기반 (하위호환)
    # ============================================================

    def set_user_email(self, email: str) -> Dict[str, Any]:
        """
        사용자 이메일 설정 및 관리자 확인 (하위호환)

        Args:
            email: 사용자 이메일

        Returns:
            사용자 정보
        """
        email = email.strip().lower()
        self.data["user_email"] = email
        self.data["is_admin"] = email in [e.lower() for e in ADMIN_EMAILS]

        # 관리자는 무제한 크레딧
        if self.data["is_admin"]:
            self.data["credits"] = 999999999

        # 미등록 사용자에게 환영 크레딧 지급
        if not self.data.get("is_registered") and not self.data["is_admin"]:
            if self.data["credits"] == 0:
                self.data["credits"] = WELCOME_CREDITS
                self.data["is_registered"] = True

        self._save_data()

        return {
            "email": email,
            "is_admin": self.data["is_admin"],
            "credits": self.data["credits"]
        }

    # ============================================================
    # 크레딧 조회 / 확인 / 차감
    # ============================================================

    def get_balance(self) -> Dict[str, Any]:
        """현재 크레딧 잔액 조회"""
        # 서버 데이터와 동기화 시도
        self._sync_from_users()

        credits = self.data["credits"]
        is_admin = self.data["is_admin"]

        return {
            "credits": credits,
            "is_admin": is_admin,
            "user_id": self.data.get("user_id", ""),
            "user_email": self.data.get("user_email", ""),
            "pages_available_ocr": credits // CREDIT_PER_PAGE_OCR if (not is_admin and CREDIT_PER_PAGE_OCR > 0) else 999999,
            "pages_available_general": 999999 if (is_admin or CREDIT_PER_PAGE_GENERAL == 0) else credits // CREDIT_PER_PAGE_GENERAL,
            "total_pages_converted": self.data.get("total_pages_converted", 0),
            # 본인 키 사용 시 요금
            "credit_per_page_ocr": CREDIT_PER_PAGE_OCR,
            "credit_per_page_general": CREDIT_PER_PAGE_GENERAL,
            # 키 없이 사용 시 요금
            "credit_per_page_ocr_nokey": CREDIT_PER_PAGE_OCR_NOKEY,
            "credit_per_page_general_nokey": CREDIT_PER_PAGE_GENERAL_NOKEY
        }

    def check_credits(self, page_count: int, credit_per_page: int = None) -> Tuple[bool, int, str]:
        """
        변환에 필요한 크레딧 확인

        Args:
            page_count: 변환할 페이지 수
            credit_per_page: 장당 크레딧 (None이면 OCR 기본값)

        Returns:
            (충분 여부, 필요 크레딧, 메시지)
        """
        if self.data["is_admin"]:
            return True, 0, "관리자 계정 - 무제한 사용"

        per_page = credit_per_page or CREDIT_PER_PAGE_OCR
        required_credits = page_count * per_page
        current_credits = self.data["credits"]

        if current_credits >= required_credits:
            return True, required_credits, f"{page_count}페이지 변환 가능 ({required_credits:,}원)"
        else:
            shortage = required_credits - current_credits
            return False, required_credits, f"크레딧 부족: {shortage:,}원 필요"

    def deduct_credits(self, page_count: int, filename: str = "",
                       credit_per_page: int = None) -> Dict[str, Any]:
        """
        크레딧 차감

        Args:
            page_count: 변환한 페이지 수
            filename: 변환한 파일명
            credit_per_page: 장당 크레딧 (None이면 OCR 기본값)

        Returns:
            차감 결과
        """
        if self.data["is_admin"]:
            self.data["total_pages_converted"] = self.data.get("total_pages_converted", 0) + page_count
            self._save_data()
            self._sync_to_users()
            return {
                "success": True,
                "deducted": 0,
                "remaining": 999999999,
                "message": "관리자 계정 - 무제한"
            }

        per_page = credit_per_page or CREDIT_PER_PAGE_OCR
        required_credits = page_count * per_page

        if self.data["credits"] < required_credits:
            return {
                "success": False,
                "deducted": 0,
                "remaining": self.data["credits"],
                "message": "크레딧이 부족합니다"
            }

        # 차감
        self.data["credits"] -= required_credits
        self.data["total_pages_converted"] = self.data.get("total_pages_converted", 0) + page_count

        # 사용 내역 기록
        usage_record = {
            "timestamp": datetime.now().isoformat(),
            "pages": page_count,
            "credits_used": required_credits,
            "credit_per_page": per_page,
            "filename": filename
        }
        self.data.setdefault("usage_history", []).append(usage_record)
        self.data["usage_history"] = self.data["usage_history"][-1000:]

        self._save_data()
        self._sync_to_users()

        return {
            "success": True,
            "deducted": required_credits,
            "remaining": self.data["credits"],
            "message": f"{page_count}페이지 변환 완료 ({required_credits:,}원 차감)"
        }

    # ============================================================
    # 크레딧 충전
    # ============================================================

    def add_credits(self, package_id: str, transaction_id: str = "") -> Dict[str, Any]:
        """
        크레딧 충전

        Args:
            package_id: 패키지 ID (basic, standard, premium)
            transaction_id: 결제 트랜잭션 ID

        Returns:
            충전 결과
        """
        if package_id not in CREDIT_PACKAGES:
            return {"success": False, "message": f"잘못된 패키지 ID: {package_id}"}

        package = CREDIT_PACKAGES[package_id]
        credits_to_add = package["credits"]

        self.data["credits"] += credits_to_add

        purchase_record = {
            "timestamp": datetime.now().isoformat(),
            "package_id": package_id,
            "price": package["price"],
            "credits_added": credits_to_add,
            "transaction_id": transaction_id or f"manual_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        }
        self.data.setdefault("purchase_history", []).append(purchase_record)
        self.data["purchase_history"] = self.data["purchase_history"][-100:]

        self._save_data()
        self._sync_to_users()

        return {
            "success": True,
            "credits_added": credits_to_add,
            "total_credits": self.data["credits"],
            "message": f"{package['label']} 크레딧 충전 완료"
        }

    def get_packages(self) -> Dict[str, Any]:
        """사용 가능한 크레딧 패키지 목록"""
        packages = []
        for pkg_id, pkg_info in CREDIT_PACKAGES.items():
            packages.append({
                "id": pkg_id,
                "price": pkg_info["price"],
                "credits": pkg_info["credits"],
                "label": pkg_info["label"],
                "pages_ocr": pkg_info["credits"] // CREDIT_PER_PAGE_OCR,
                "pages_general": pkg_info["credits"] // CREDIT_PER_PAGE_GENERAL,
                "price_per_page_ocr": CREDIT_PER_PAGE_OCR,
                "price_per_page_general": CREDIT_PER_PAGE_GENERAL
            })
        return {
            "packages": packages,
            "credit_per_page_ocr": CREDIT_PER_PAGE_OCR,
            "credit_per_page_general": CREDIT_PER_PAGE_GENERAL
        }

    # ============================================================
    # 관리자 기능: 회원 크레딧 부여
    # ============================================================

    def admin_add_credits(self, target_user_id: str, amount: int, reason: str = "") -> Dict[str, Any]:
        """
        관리자가 특정 회원에게 크레딧을 부여

        Args:
            target_user_id: 대상 회원 ID
            amount: 부여할 크레딧
            reason: 사유

        Returns:
            결과
        """
        if not self.data.get("is_admin"):
            return {"success": False, "message": "관리자 권한이 필요합니다"}

        target_user_id = target_user_id.strip().lower()
        users = self.users.get("users", {})

        if target_user_id not in users:
            return {"success": False, "message": f"존재하지 않는 회원: {target_user_id}"}

        # 크레딧 부여
        users[target_user_id]["credits"] = users[target_user_id].get("credits", 0) + amount

        # 기록
        admin_record = {
            "timestamp": datetime.now().isoformat(),
            "action": "admin_add_credits",
            "admin_id": self.data.get("user_id", "admin"),
            "target_user_id": target_user_id,
            "amount": amount,
            "reason": reason,
            "new_balance": users[target_user_id]["credits"]
        }
        users[target_user_id].setdefault("purchase_history", []).append(admin_record)

        self._save_users()

        return {
            "success": True,
            "target_user_id": target_user_id,
            "credits_added": amount,
            "new_balance": users[target_user_id]["credits"],
            "message": f"{target_user_id}에게 {amount:,} 크레딧 부여 완료"
        }

    def admin_list_users(self) -> Dict[str, Any]:
        """
        관리자: 전체 회원 목록 조회

        Returns:
            회원 목록
        """
        if not self.data.get("is_admin"):
            return {"success": False, "message": "관리자 권한이 필요합니다", "users": []}

        user_list = []
        for uid, udata in self.users.get("users", {}).items():
            user_list.append({
                "user_id": uid,
                "email": udata.get("email", ""),
                "credits": udata.get("credits", 0),
                "is_admin": udata.get("is_admin", False),
                "total_pages_converted": udata.get("total_pages_converted", 0),
                "registered_at": udata.get("registered_at", "")
            })

        return {
            "success": True,
            "users": user_list,
            "total": len(user_list)
        }

    def admin_set_credits(self, target_user_id: str, amount: int) -> Dict[str, Any]:
        """
        관리자가 특정 회원의 크레딧을 설정 (덮어쓰기)

        Args:
            target_user_id: 대상 회원 ID
            amount: 설정할 크레딧

        Returns:
            결과
        """
        if not self.data.get("is_admin"):
            return {"success": False, "message": "관리자 권한이 필요합니다"}

        target_user_id = target_user_id.strip().lower()
        users = self.users.get("users", {})

        if target_user_id not in users:
            return {"success": False, "message": f"존재하지 않는 회원: {target_user_id}"}

        old_balance = users[target_user_id].get("credits", 0)
        users[target_user_id]["credits"] = amount
        self._save_users()

        return {
            "success": True,
            "target_user_id": target_user_id,
            "old_balance": old_balance,
            "new_balance": amount,
            "message": f"{target_user_id} 크레딧: {old_balance:,} → {amount:,}"
        }

    # ============================================================
    # 데이터 동기화
    # ============================================================

    def _sync_to_users(self):
        """로컬 데이터를 회원 DB에 동기화"""
        user_id = self.data.get("user_id", "")
        if user_id and user_id in self.users.get("users", {}):
            self.users["users"][user_id]["credits"] = self.data["credits"]
            self.users["users"][user_id]["total_pages_converted"] = self.data.get("total_pages_converted", 0)
            self._save_users()

    def _sync_from_users(self):
        """회원 DB에서 로컬 데이터로 동기화"""
        user_id = self.data.get("user_id", "")
        if user_id and user_id in self.users.get("users", {}):
            user_data = self.users["users"][user_id]
            self.data["credits"] = user_data.get("credits", self.data["credits"])
            self.data["is_admin"] = user_data.get("is_admin", False)

    # ============================================================
    # 히스토리
    # ============================================================

    def get_usage_history(self, limit: int = 50) -> list:
        """사용 내역 조회"""
        return self.data.get("usage_history", [])[-limit:]

    def get_purchase_history(self, limit: int = 20) -> list:
        """구매 내역 조회"""
        return self.data.get("purchase_history", [])[-limit:]


# ============================================================
# 전역 인스턴스
# ============================================================
_credit_manager: Optional[CreditManager] = None


def get_credit_manager() -> CreditManager:
    """전역 CreditManager 인스턴스 반환"""
    global _credit_manager
    if _credit_manager is None:
        _credit_manager = CreditManager()
    return _credit_manager


# ============================================================
# CLI 지원
# ============================================================
if __name__ == "__main__":
    import sys

    manager = CreditManager()

    if len(sys.argv) < 2:
        print("사용법:")
        print("  python credit_manager.py balance                  - 잔액 조회")
        print("  python credit_manager.py register <id> <pw>       - 회원 가입")
        print("  python credit_manager.py login <id> <pw>          - 로그인")
        print("  python credit_manager.py set-email <email>        - 이메일 설정")
        print("  python credit_manager.py add <package_id>         - 크레딧 충전")
        print("  python credit_manager.py check <pages> [ocr]      - 크레딧 확인")
        print("  python credit_manager.py packages                 - 패키지 목록")
        print("  python credit_manager.py admin-list               - 회원 목록 (관리자)")
        print("  python credit_manager.py admin-add <user> <amount>- 크레딧 부여 (관리자)")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "balance":
        result = manager.get_balance()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "register" and len(sys.argv) > 3:
        result = manager.register(sys.argv[2], sys.argv[3])
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "login" and len(sys.argv) > 3:
        result = manager.login(sys.argv[2], sys.argv[3])
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "set-email" and len(sys.argv) > 2:
        result = manager.set_user_email(sys.argv[2])
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "add" and len(sys.argv) > 2:
        result = manager.add_credits(sys.argv[2])
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "check" and len(sys.argv) > 2:
        pages = int(sys.argv[2])
        is_ocr = len(sys.argv) > 3 and sys.argv[3] == "ocr"
        per_page = CREDIT_PER_PAGE_OCR if is_ocr else CREDIT_PER_PAGE_GENERAL
        has_credits, required, msg = manager.check_credits(pages, per_page)
        print(json.dumps({
            "has_credits": has_credits,
            "required": required,
            "message": msg
        }, ensure_ascii=False, indent=2))

    elif cmd == "packages":
        result = manager.get_packages()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "admin-list":
        result = manager.admin_list_users()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "admin-add" and len(sys.argv) > 3:
        target = sys.argv[2]
        amount = int(sys.argv[3])
        reason = sys.argv[4] if len(sys.argv) > 4 else ""
        result = manager.admin_add_credits(target, amount, reason)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        print("잘못된 명령어입니다")
        sys.exit(1)
