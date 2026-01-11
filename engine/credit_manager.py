#!/usr/bin/env python3
"""
LawPro Fast Converter - Credit Manager
=======================================
이미지 PDF 변환 크레딧 관리 시스템

Pricing:
- 이미지 PDF 1페이지당 55원 (부가세 포함)
- 크레딧 패키지: 110,000원, 220,000원, 550,000원 (부가세 포함)

Admin:
- kjccjk@hanmail.net: 무제한 크레딧 (관리자)
"""

import os
import json
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from pathlib import Path


# 크레딧 설정
CREDIT_PER_PAGE = 55  # 1페이지당 55원 (부가세 포함)

CREDIT_PACKAGES = {
    "basic": {"price": 110000, "credits": 110000, "label": "11만원"},
    "standard": {"price": 220000, "credits": 220000, "label": "22만원"},
    "premium": {"price": 550000, "credits": 550000, "label": "55만원"}
}

# 관리자 이메일 (무제한 크레딧)
ADMIN_EMAILS = [
    "kjccjk@hanmail.net"
]


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

        self._load_data()

    def _load_data(self):
        """저장된 데이터 로드"""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.data = self._default_data()
        else:
            self.data = self._default_data()

    def _default_data(self) -> Dict[str, Any]:
        """기본 데이터 구조"""
        return {
            "user_email": "",
            "credits": 0,
            "is_admin": False,
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

    def set_user_email(self, email: str) -> Dict[str, Any]:
        """
        사용자 이메일 설정 및 관리자 확인

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
            self.data["credits"] = 999999999  # 실질적 무제한

        self._save_data()

        return {
            "email": email,
            "is_admin": self.data["is_admin"],
            "credits": self.data["credits"]
        }

    def get_balance(self) -> Dict[str, Any]:
        """
        현재 크레딧 잔액 조회

        Returns:
            잔액 정보
        """
        return {
            "credits": self.data["credits"],
            "is_admin": self.data["is_admin"],
            "user_email": self.data["user_email"],
            "pages_available": self.data["credits"] // CREDIT_PER_PAGE if not self.data["is_admin"] else 999999,
            "total_pages_converted": self.data.get("total_pages_converted", 0)
        }

    def check_credits(self, page_count: int) -> Tuple[bool, int, str]:
        """
        변환에 필요한 크레딧 확인

        Args:
            page_count: 변환할 페이지 수

        Returns:
            (충분 여부, 필요 크레딧, 메시지)
        """
        # 관리자는 무조건 통과
        if self.data["is_admin"]:
            return True, 0, "관리자 계정 - 무제한 사용"

        required_credits = page_count * CREDIT_PER_PAGE
        current_credits = self.data["credits"]

        if current_credits >= required_credits:
            return True, required_credits, f"{page_count}페이지 변환 가능 ({required_credits:,}원)"
        else:
            shortage = required_credits - current_credits
            return False, required_credits, f"크레딧 부족: {shortage:,}원 필요"

    def deduct_credits(self, page_count: int, filename: str = "") -> Dict[str, Any]:
        """
        크레딧 차감

        Args:
            page_count: 변환한 페이지 수
            filename: 변환한 파일명

        Returns:
            차감 결과
        """
        # 관리자는 차감 없음
        if self.data["is_admin"]:
            self.data["total_pages_converted"] = self.data.get("total_pages_converted", 0) + page_count
            self._save_data()
            return {
                "success": True,
                "deducted": 0,
                "remaining": 999999999,
                "message": "관리자 계정 - 무제한"
            }

        required_credits = page_count * CREDIT_PER_PAGE

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
            "filename": filename
        }
        self.data["usage_history"].append(usage_record)

        # 최근 1000개만 유지
        self.data["usage_history"] = self.data["usage_history"][-1000:]

        self._save_data()

        return {
            "success": True,
            "deducted": required_credits,
            "remaining": self.data["credits"],
            "message": f"{page_count}페이지 변환 완료 ({required_credits:,}원 차감)"
        }

    def add_credits(self, package_id: str, transaction_id: str = "") -> Dict[str, Any]:
        """
        크레딧 충전 (결제 완료 후 호출)

        Args:
            package_id: 패키지 ID (basic, standard, premium)
            transaction_id: 결제 트랜잭션 ID

        Returns:
            충전 결과
        """
        if package_id not in CREDIT_PACKAGES:
            return {
                "success": False,
                "message": f"잘못된 패키지 ID: {package_id}"
            }

        package = CREDIT_PACKAGES[package_id]
        credits_to_add = package["credits"]

        # 크레딧 추가
        self.data["credits"] += credits_to_add

        # 구매 내역 기록
        purchase_record = {
            "timestamp": datetime.now().isoformat(),
            "package_id": package_id,
            "price": package["price"],
            "credits_added": credits_to_add,
            "transaction_id": transaction_id or f"manual_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        }
        self.data["purchase_history"].append(purchase_record)

        # 최근 100개만 유지
        self.data["purchase_history"] = self.data["purchase_history"][-100:]

        self._save_data()

        return {
            "success": True,
            "credits_added": credits_to_add,
            "total_credits": self.data["credits"],
            "message": f"{package['label']} 크레딧 충전 완료"
        }

    def get_packages(self) -> Dict[str, Any]:
        """
        사용 가능한 크레딧 패키지 목록

        Returns:
            패키지 목록
        """
        packages = []
        for pkg_id, pkg_info in CREDIT_PACKAGES.items():
            packages.append({
                "id": pkg_id,
                "price": pkg_info["price"],
                "credits": pkg_info["credits"],
                "label": pkg_info["label"],
                "pages": pkg_info["credits"] // CREDIT_PER_PAGE,
                "price_per_page": CREDIT_PER_PAGE
            })
        return {
            "packages": packages,
            "credit_per_page": CREDIT_PER_PAGE
        }

    def get_usage_history(self, limit: int = 50) -> list:
        """
        사용 내역 조회

        Args:
            limit: 반환할 최대 개수

        Returns:
            사용 내역 목록
        """
        return self.data.get("usage_history", [])[-limit:]

    def get_purchase_history(self, limit: int = 20) -> list:
        """
        구매 내역 조회

        Args:
            limit: 반환할 최대 개수

        Returns:
            구매 내역 목록
        """
        return self.data.get("purchase_history", [])[-limit:]


# 전역 인스턴스
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
        print("  python credit_manager.py balance              - 잔액 조회")
        print("  python credit_manager.py set-email <email>    - 이메일 설정")
        print("  python credit_manager.py add <package_id>     - 크레딧 충전")
        print("  python credit_manager.py check <pages>        - 크레딧 확인")
        print("  python credit_manager.py packages             - 패키지 목록")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "balance":
        result = manager.get_balance()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "set-email" and len(sys.argv) > 2:
        email = sys.argv[2]
        result = manager.set_user_email(email)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "add" and len(sys.argv) > 2:
        package_id = sys.argv[2]
        result = manager.add_credits(package_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "check" and len(sys.argv) > 2:
        pages = int(sys.argv[2])
        has_credits, required, msg = manager.check_credits(pages)
        print(json.dumps({
            "has_credits": has_credits,
            "required": required,
            "message": msg
        }, ensure_ascii=False, indent=2))

    elif cmd == "packages":
        result = manager.get_packages()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        print("잘못된 명령어입니다")
        sys.exit(1)
