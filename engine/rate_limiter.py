#!/usr/bin/env python3
"""
Upstage API Rate Limiter - 적응형 Rate Limit 학습 시스템
=========================================================

429 에러 발생 시 요청 빈도를 분석하고, 성공 시와 비교하여
최적의 내부 Rate Limit을 자동으로 학습합니다.

핵심 로직:
1. 모든 API 요청 시간을 기록
2. 429 발생 시: 직전 1분/5분/10분 요청 빈도 기록 (실패 케이스)
3. 성공 지속 시: 주기적으로 요청 빈도 기록 (성공 케이스)
4. 두 케이스의 중간값을 내부 Rate Limit으로 설정
5. 요청 전 Rate Limit 초과 예상 시 자동 대기
"""

import os
import json
import time
import threading
from collections import deque
from typing import Dict, Optional, Tuple
from datetime import datetime


class RateLimitTracker:
    """적응형 Rate Limit 추적기"""

    # 데이터 저장 파일
    DATA_FILE = "rate_limit_history.json"

    # 분석 윈도우 (초)
    WINDOW_1MIN = 60
    WINDOW_5MIN = 300
    WINDOW_10MIN = 600

    # 성공 케이스 기록 간격 (성공 요청 10회마다)
    SUCCESS_SNAPSHOT_INTERVAL = 10

    # 기본 Rate Limit (학습 전 초기값) - 분당 요청 수
    DEFAULT_RATE_LIMIT = 30  # 보수적으로 시작

    def __init__(self, data_dir: str = None):
        """
        Args:
            data_dir: 데이터 저장 디렉토리 (없으면 engine 폴더)
        """
        self.data_dir = data_dir or os.path.dirname(os.path.abspath(__file__))
        self.data_file = os.path.join(self.data_dir, self.DATA_FILE)

        # 요청 타임스탬프 기록 (최근 10분만 유지)
        self.request_times = deque(maxlen=1000)

        # 성공 요청 카운터 (스냅샷 주기 결정용)
        self.success_count = 0

        # 학습된 Rate Limit 데이터
        self.rate_data = {
            "success_snapshots": [],  # 성공 시 요청 빈도 기록
            "failure_snapshots": [],  # 429 발생 시 요청 빈도 기록
            "learned_rate_limit": self.DEFAULT_RATE_LIMIT,  # 학습된 분당 제한
            "last_updated": None
        }

        # 스레드 안전성
        self.lock = threading.Lock()

        # 저장된 데이터 로드
        self._load_data()

    def _load_data(self):
        """저장된 Rate Limit 데이터 로드"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    saved_data = json.load(f)
                    self.rate_data.update(saved_data)

                    # 24시간 이상 된 스냅샷 제거
                    cutoff = time.time() - 86400  # 24시간
                    self.rate_data["success_snapshots"] = [
                        s for s in self.rate_data.get("success_snapshots", [])
                        if s.get("timestamp", 0) > cutoff
                    ]
                    self.rate_data["failure_snapshots"] = [
                        s for s in self.rate_data.get("failure_snapshots", [])
                        if s.get("timestamp", 0) > cutoff
                    ]
        except Exception as e:
            print(f"Rate limit 데이터 로드 실패: {e}")

    def _save_data(self):
        """Rate Limit 데이터 저장"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.rate_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Rate limit 데이터 저장 실패: {e}")

    def _calculate_rates(self) -> Dict[str, float]:
        """현재 요청 빈도 계산 (1분/5분/10분 윈도우)"""
        now = time.time()
        rates = {}

        with self.lock:
            # 각 윈도우별 요청 수 계산
            count_1min = sum(1 for t in self.request_times if now - t <= self.WINDOW_1MIN)
            count_5min = sum(1 for t in self.request_times if now - t <= self.WINDOW_5MIN)
            count_10min = sum(1 for t in self.request_times if now - t <= self.WINDOW_10MIN)

        # 분당 평균 요청 수로 변환
        rates["rate_1min"] = count_1min  # 1분간 총 요청 = 분당 요청
        rates["rate_5min_avg"] = count_5min / 5 if count_5min > 0 else 0  # 5분간 평균
        rates["rate_10min_avg"] = count_10min / 10 if count_10min > 0 else 0  # 10분간 평균
        rates["timestamp"] = now

        return rates

    def record_request(self):
        """API 요청 기록"""
        with self.lock:
            self.request_times.append(time.time())

    def record_success(self):
        """성공 요청 기록 및 주기적 스냅샷"""
        self.success_count += 1

        # 일정 간격마다 성공 케이스 스냅샷 저장
        if self.success_count % self.SUCCESS_SNAPSHOT_INTERVAL == 0:
            rates = self._calculate_rates()
            rates["type"] = "success"

            with self.lock:
                self.rate_data["success_snapshots"].append(rates)
                # 최근 100개만 유지
                if len(self.rate_data["success_snapshots"]) > 100:
                    self.rate_data["success_snapshots"] = self.rate_data["success_snapshots"][-100:]

            self._save_data()

    def record_429_error(self) -> Dict:
        """
        429 에러 기록 및 분석

        Returns:
            분석 결과 (현재 요청 빈도, 성공 케이스와 비교, 새로운 Rate Limit)
        """
        current_rates = self._calculate_rates()
        current_rates["type"] = "failure_429"

        # 실패 케이스 저장
        with self.lock:
            self.rate_data["failure_snapshots"].append(current_rates)
            # 최근 50개만 유지
            if len(self.rate_data["failure_snapshots"]) > 50:
                self.rate_data["failure_snapshots"] = self.rate_data["failure_snapshots"][-50:]

        # 성공 케이스와 비교
        comparison = self._compare_with_success()

        # 새로운 Rate Limit 계산
        new_limit = self._calculate_new_rate_limit(current_rates, comparison)

        # 저장
        self.rate_data["learned_rate_limit"] = new_limit
        self.rate_data["last_updated"] = datetime.now().isoformat()
        self._save_data()

        return {
            "current_rates": current_rates,
            "comparison": comparison,
            "new_rate_limit": new_limit,
            "old_rate_limit": self.rate_data.get("learned_rate_limit", self.DEFAULT_RATE_LIMIT)
        }

    def _compare_with_success(self) -> Optional[Dict]:
        """24시간 이내 성공 케이스와 비교"""
        success_snapshots = self.rate_data.get("success_snapshots", [])

        if not success_snapshots:
            return None

        # 성공 케이스들의 평균 계산
        avg_1min = sum(s["rate_1min"] for s in success_snapshots) / len(success_snapshots)
        avg_5min = sum(s["rate_5min_avg"] for s in success_snapshots) / len(success_snapshots)
        avg_10min = sum(s["rate_10min_avg"] for s in success_snapshots) / len(success_snapshots)

        return {
            "success_avg_1min": avg_1min,
            "success_avg_5min": avg_5min,
            "success_avg_10min": avg_10min,
            "sample_count": len(success_snapshots)
        }

    def _calculate_new_rate_limit(self, current_rates: Dict, comparison: Optional[Dict]) -> float:
        """
        새로운 Rate Limit 계산

        로직: 429 발생 시 요청 빈도와 성공 시 요청 빈도의 중간값
        """
        failure_rate = current_rates["rate_1min"]

        if comparison and comparison["sample_count"] >= 3:
            # 성공 케이스가 충분히 있으면 중간값 사용
            success_rate = comparison["success_avg_1min"]

            # 중간값 계산 (성공 쪽으로 약간 치우침 - 안전 마진)
            # 성공율의 80% 지점을 선택
            new_limit = success_rate * 0.8

            # 너무 낮으면 최소값 보장
            new_limit = max(new_limit, 5)

            # 현재 학습값과 가중 평균 (급격한 변화 방지)
            current_limit = self.rate_data.get("learned_rate_limit", self.DEFAULT_RATE_LIMIT)
            new_limit = (current_limit * 0.3) + (new_limit * 0.7)

        else:
            # 성공 케이스가 부족하면 현재 실패율의 70% 사용
            new_limit = failure_rate * 0.7
            new_limit = max(new_limit, 5)

        return round(new_limit, 1)

    def get_rate_limit(self) -> float:
        """현재 학습된 Rate Limit 반환 (분당 요청 수)"""
        return self.rate_data.get("learned_rate_limit", self.DEFAULT_RATE_LIMIT)

    def should_wait(self) -> Tuple[bool, float]:
        """
        Rate Limit 초과 예상 시 대기 필요 여부 확인

        Returns:
            (should_wait, wait_seconds)
        """
        current_rates = self._calculate_rates()
        rate_limit = self.get_rate_limit()

        # 현재 1분간 요청 수가 Rate Limit에 근접하면 대기
        current_rate = current_rates["rate_1min"]

        if current_rate >= rate_limit * 0.9:  # 90% 도달 시 대기 시작
            # 다음 요청까지 대기 시간 계산
            # 1분에 rate_limit개 요청 = 60/rate_limit 초 간격
            wait_time = 60 / rate_limit
            return True, wait_time

        return False, 0

    def get_status_log(self) -> str:
        """현재 상태 로그 문자열 반환"""
        rates = self._calculate_rates()
        rate_limit = self.get_rate_limit()

        return json.dumps({
            "type": "rate_status",
            "current_1min": rates["rate_1min"],
            "current_5min_avg": round(rates["rate_5min_avg"], 1),
            "current_10min_avg": round(rates["rate_10min_avg"], 1),
            "learned_limit": rate_limit,
            "success_samples": len(self.rate_data.get("success_snapshots", [])),
            "failure_samples": len(self.rate_data.get("failure_snapshots", []))
        }, ensure_ascii=False)

    def get_429_analysis_log(self, analysis: Dict) -> str:
        """429 발생 시 분석 로그 문자열 반환"""
        current = analysis["current_rates"]
        comparison = analysis.get("comparison")

        log_data = {
            "type": "rate_limit_429",
            "current": {
                "1min": current["rate_1min"],
                "5min_avg": round(current["rate_5min_avg"], 1),
                "10min_avg": round(current["rate_10min_avg"], 1)
            },
            "learned_limit": {
                "old": analysis.get("old_rate_limit"),
                "new": analysis["new_rate_limit"]
            }
        }

        if comparison:
            log_data["success_baseline"] = {
                "1min_avg": round(comparison["success_avg_1min"], 1),
                "5min_avg": round(comparison["success_avg_5min"], 1),
                "10min_avg": round(comparison["success_avg_10min"], 1),
                "samples": comparison["sample_count"]
            }

        return json.dumps(log_data, ensure_ascii=False)


# 싱글톤 인스턴스
_rate_limiter_instance = None


def get_rate_limiter(data_dir: str = None) -> RateLimitTracker:
    """Rate Limiter 싱글톤 인스턴스 반환"""
    global _rate_limiter_instance
    if _rate_limiter_instance is None:
        _rate_limiter_instance = RateLimitTracker(data_dir)
    return _rate_limiter_instance
