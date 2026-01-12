#!/usr/bin/env python3
"""
Proxy Manager - 다중 사용자 프록시 관리
========================================

동시에 여러 사용자가 작업할 때 각각 다른 IP로 요청하도록
프록시 서버를 관리합니다.

기능:
- 프록시 풀 관리 (최대 50개)
- 세션별 프록시 할당
- 프록시 상태 모니터링 (실패 시 자동 제외)
- 라운드 로빈/랜덤 로드 밸런싱
- Decodo 등 포트 기반 프록시 서비스 지원

사용법:
1. admin_config.json에 프록시 설정
2. FileProcessor에서 자동으로 프록시 사용

설정 방법 1 - Decodo 스타일 (포트 범위):
{
    "proxy_host": "gate.decodo.com",
    "proxy_username": "sp3u3hafyc",
    "proxy_password": "PoOz6V4u4X0...",
    "proxy_port_start": 10001,
    "proxy_port_end": 10050,
    "proxy_mode": "round_robin"
}

설정 방법 2 - 개별 프록시 URL 목록:
{
    "proxy_servers": [
        "http://user:pass@proxy1.example.com:8080",
        "http://user:pass@proxy2.example.com:8080"
    ],
    "proxy_mode": "round_robin"
}

환경변수 설정:
- PROXY_HOST=gate.decodo.com
- PROXY_USERNAME=sp3u3hafyc
- PROXY_PASSWORD=PoOz6V4u4X0...
- PROXY_PORT_START=10001
- PROXY_PORT_END=10050
- PROXY_MODE=round_robin
"""

import os
import json
import time
import random
import threading
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import deque


@dataclass
class ProxyStatus:
    """프록시 상태 정보"""
    url: str
    success_count: int = 0
    failure_count: int = 0
    last_used: float = 0
    last_error: str = ""
    is_active: bool = True
    consecutive_failures: int = 0

    @property
    def failure_rate(self) -> float:
        total = self.success_count + self.failure_count
        if total == 0:
            return 0
        return self.failure_count / total


class ProxyManager:
    """다중 사용자 프록시 관리자"""

    # 프록시 실패 임계값
    MAX_CONSECUTIVE_FAILURES = 3  # 연속 실패 시 비활성화
    REACTIVATION_DELAY = 300  # 5분 후 재활성화 시도

    def __init__(self, proxies: List[str] = None, mode: str = "round_robin"):
        """
        Args:
            proxies: 프록시 URL 목록
            mode: 로드 밸런싱 모드 (round_robin, random, session_sticky)
        """
        self.mode = mode
        self.lock = threading.Lock()

        # 프록시 상태 관리
        self.proxies: Dict[str, ProxyStatus] = {}
        self._proxy_order: deque = deque()  # round_robin용 순서 관리

        # 세션별 프록시 할당 (session_sticky 모드용)
        self.session_proxies: Dict[str, str] = {}

        # 프록시 설정
        if proxies:
            for proxy_url in proxies:
                self._add_proxy(proxy_url)

    def _add_proxy(self, proxy_url: str):
        """프록시 추가"""
        if proxy_url and proxy_url not in self.proxies:
            self.proxies[proxy_url] = ProxyStatus(url=proxy_url)
            self._proxy_order.append(proxy_url)

    def get_proxy(self, session_id: str = None) -> Optional[str]:
        """
        프록시 URL 반환

        Args:
            session_id: 세션 ID (session_sticky 모드에서 사용)

        Returns:
            프록시 URL 또는 None (프록시 없거나 모두 비활성화)
        """
        with self.lock:
            if not self.proxies:
                return None

            # 비활성화된 프록시 재활성화 시도
            self._try_reactivate_proxies()

            active_proxies = [
                url for url, status in self.proxies.items()
                if status.is_active
            ]

            if not active_proxies:
                return None

            # 모드별 선택
            if self.mode == "session_sticky" and session_id:
                return self._get_sticky_proxy(session_id, active_proxies)
            elif self.mode == "random":
                return self._get_random_proxy(active_proxies)
            else:  # round_robin (기본)
                return self._get_round_robin_proxy(active_proxies)

    def _get_round_robin_proxy(self, active_proxies: List[str]) -> str:
        """라운드 로빈 방식으로 프록시 선택"""
        # 활성 프록시 순서대로 순환
        for _ in range(len(self._proxy_order)):
            proxy_url = self._proxy_order[0]
            self._proxy_order.rotate(-1)

            if proxy_url in active_proxies:
                self.proxies[proxy_url].last_used = time.time()
                return proxy_url

        # 모든 프록시가 비활성 상태면 첫 번째 활성 프록시 반환
        return active_proxies[0]

    def _get_random_proxy(self, active_proxies: List[str]) -> str:
        """랜덤 방식으로 프록시 선택"""
        proxy_url = random.choice(active_proxies)
        self.proxies[proxy_url].last_used = time.time()
        return proxy_url

    def _get_sticky_proxy(self, session_id: str, active_proxies: List[str]) -> str:
        """세션별 고정 프록시 할당"""
        # 이미 할당된 프록시가 있고 활성 상태면 재사용
        if session_id in self.session_proxies:
            assigned = self.session_proxies[session_id]
            if assigned in active_proxies:
                self.proxies[assigned].last_used = time.time()
                return assigned

        # 새 프록시 할당 (가장 덜 사용된 프록시 선택)
        least_used = min(
            active_proxies,
            key=lambda url: len([
                sid for sid, purl in self.session_proxies.items()
                if purl == url
            ])
        )

        self.session_proxies[session_id] = least_used
        self.proxies[least_used].last_used = time.time()
        return least_used

    def report_success(self, proxy_url: str):
        """프록시 성공 보고"""
        with self.lock:
            if proxy_url in self.proxies:
                status = self.proxies[proxy_url]
                status.success_count += 1
                status.consecutive_failures = 0
                status.is_active = True

    def report_failure(self, proxy_url: str, error: str = ""):
        """
        프록시 실패 보고

        연속 실패가 임계값을 넘으면 프록시 비활성화
        """
        with self.lock:
            if proxy_url in self.proxies:
                status = self.proxies[proxy_url]
                status.failure_count += 1
                status.consecutive_failures += 1
                status.last_error = error

                # 연속 실패 시 비활성화
                if status.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                    status.is_active = False

    def _try_reactivate_proxies(self):
        """비활성화된 프록시 재활성화 시도"""
        current_time = time.time()

        for status in self.proxies.values():
            if not status.is_active:
                # 일정 시간 경과 후 재활성화
                if current_time - status.last_used >= self.REACTIVATION_DELAY:
                    status.is_active = True
                    status.consecutive_failures = 0

    def get_status(self) -> Dict:
        """프록시 상태 정보 반환"""
        with self.lock:
            return {
                "total": len(self.proxies),
                "active": sum(1 for s in self.proxies.values() if s.is_active),
                "mode": self.mode,
                "proxies": [
                    {
                        "url": self._mask_proxy_url(url),
                        "active": status.is_active,
                        "success": status.success_count,
                        "failure": status.failure_count,
                        "failure_rate": round(status.failure_rate * 100, 1)
                    }
                    for url, status in self.proxies.items()
                ]
            }

    def _mask_proxy_url(self, url: str) -> str:
        """프록시 URL 마스킹 (로깅용)"""
        # 비밀번호 숨기기: http://user:pass@host:port -> http://user:***@host:port
        import re
        return re.sub(r':([^@:]+)@', r':***@', url)

    def get_requests_proxies_dict(self, proxy_url: str) -> Dict:
        """
        requests 라이브러리용 프록시 딕셔너리 반환

        Args:
            proxy_url: 프록시 URL

        Returns:
            {"http": proxy_url, "https": proxy_url}
        """
        if not proxy_url:
            return {}

        return {
            "http": proxy_url,
            "https": proxy_url
        }

    def release_session(self, session_id: str):
        """세션 프록시 할당 해제"""
        with self.lock:
            if session_id in self.session_proxies:
                del self.session_proxies[session_id]


# 싱글톤 인스턴스
_proxy_manager_instance = None


def generate_proxy_urls_from_port_range(
    host: str,
    username: str,
    password: str,
    port_start: int,
    port_end: int,
    protocol: str = "http"
) -> List[str]:
    """
    포트 범위로 프록시 URL 목록 생성 (Decodo 등)

    Args:
        host: 프록시 호스트 (예: gate.decodo.com)
        username: 인증 사용자명
        password: 인증 비밀번호
        port_start: 시작 포트 (예: 10001)
        port_end: 종료 포트 (예: 10050)
        protocol: 프로토콜 (http, https, socks5)

    Returns:
        프록시 URL 목록
        예: ["http://user:pass@gate.decodo.com:10001", ...]
    """
    proxies = []
    for port in range(port_start, port_end + 1):
        proxy_url = f"{protocol}://{username}:{password}@{host}:{port}"
        proxies.append(proxy_url)
    return proxies


def get_proxy_manager() -> Optional[ProxyManager]:
    """프록시 매니저 싱글톤 인스턴스 반환"""
    global _proxy_manager_instance

    if _proxy_manager_instance is None:
        # admin_config에서 프록시 설정 로드
        try:
            from admin_config import get_admin_config
            config = get_admin_config()

            proxies = []
            mode = config.get("proxy_mode", "round_robin")

            # 방법 1: Decodo 스타일 (포트 범위 설정)
            proxy_host = config.get("proxy_host")
            proxy_username = config.get("proxy_username")
            proxy_password = config.get("proxy_password")
            proxy_port_start = config.get("proxy_port_start")
            proxy_port_end = config.get("proxy_port_end")

            if all([proxy_host, proxy_username, proxy_password, proxy_port_start, proxy_port_end]):
                proxies = generate_proxy_urls_from_port_range(
                    host=proxy_host,
                    username=proxy_username,
                    password=proxy_password,
                    port_start=int(proxy_port_start),
                    port_end=int(proxy_port_end),
                    protocol=config.get("proxy_protocol", "http")
                )
                print(f"[ProxyManager] Decodo 프록시 {len(proxies)}개 생성됨 "
                      f"(포트 {proxy_port_start}-{proxy_port_end}, 모드: {mode})")

            # 방법 2: 개별 프록시 URL 목록
            if not proxies:
                proxies = config.get("proxy_servers", [])
                if proxies:
                    print(f"[ProxyManager] 프록시 {len(proxies)}개 로드됨 (모드: {mode})")

            if proxies:
                _proxy_manager_instance = ProxyManager(proxies=proxies, mode=mode)
            else:
                return None

        except ImportError:
            return None
        except Exception as e:
            print(f"[ProxyManager] 초기화 실패: {e}")
            return None

    return _proxy_manager_instance


def init_proxy_manager(proxies: List[str], mode: str = "round_robin") -> ProxyManager:
    """프록시 매니저 초기화 (외부에서 직접 설정)"""
    global _proxy_manager_instance
    _proxy_manager_instance = ProxyManager(proxies=proxies, mode=mode)
    return _proxy_manager_instance


def init_proxy_manager_decodo(
    host: str,
    username: str,
    password: str,
    port_start: int,
    port_end: int,
    mode: str = "round_robin"
) -> ProxyManager:
    """
    Decodo 스타일 프록시 매니저 초기화

    사용 예:
        init_proxy_manager_decodo(
            host="gate.decodo.com",
            username="sp3u3hafyc",
            password="PoOz6V4u4X0...",
            port_start=10001,
            port_end=10050
        )
    """
    global _proxy_manager_instance
    proxies = generate_proxy_urls_from_port_range(
        host=host,
        username=username,
        password=password,
        port_start=port_start,
        port_end=port_end
    )
    _proxy_manager_instance = ProxyManager(proxies=proxies, mode=mode)
    print(f"[ProxyManager] Decodo 프록시 {len(proxies)}개 초기화됨 (모드: {mode})")
    return _proxy_manager_instance
