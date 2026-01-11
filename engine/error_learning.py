#!/usr/bin/env python3
"""
LawPro Error Learning System
=============================
사용자의 오류 수정 내역을 수집하고 학습하여 AI 검수 품질을 지속적으로 개선합니다.

두 가지 오류 출처:
1. image_pdf: Upstage Document Parser의 OCR 오류
2. digital_doc: 라이브러리(lxml, python-docx 등)의 변환 버그

수집된 패턴은 review_rules.json에 자동 반영됩니다.
"""

import os
import sys
import json
import hashlib
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

# ============================================================
# 설정
# ============================================================
# 로컬 학습 데이터 저장 경로
ENGINE_DIR = Path(__file__).parent
LEARNED_PATTERNS_FILE = ENGINE_DIR / "learned_patterns.json"
PENDING_SYNC_FILE = ENGINE_DIR / "pending_corrections.json"
CONFIG_FILE = ENGINE_DIR / "learning_config.json"

# 서버 엔드포인트 (Railway 배포 후 실제 URL로 교체)
ERROR_COLLECTION_SERVER = os.environ.get(
    'LAWPRO_ERROR_SERVER',
    'https://lawpro-admin.up.railway.app'  # Railway 배포 URL (예시)
)

# LLM 컨텍스트 제한 (토큰 기준)
# - GPT-4o: 128K tokens
# - Gemini 2.0 Flash: 1M tokens
# - Claude 3.5 Sonnet: 200K tokens
#
# 패턴당 평균 토큰: 약 50 tokens (한글 포함)
# 프롬프트 기타 요소: 약 5K tokens 필요
#
# GPT-4o 기준 권장값:
#   (128,000 - 5,000) / 50 = 2,460 패턴 (안전 마진 적용 → 2,000개)
#
# Gemini 2.0 기준 권장값:
#   (1,000,000 - 5,000) / 50 = 19,900 패턴 (안전 마진 → 10,000개)

LLM_CONTEXT_LIMITS = {
    'gpt-4o': {'tokens': 128000, 'recommended_patterns': 2000},
    'gpt-4o-mini': {'tokens': 128000, 'recommended_patterns': 2000},
    'gemini-2.0-flash': {'tokens': 1000000, 'recommended_patterns': 10000},
    'gemini-1.5-pro': {'tokens': 1000000, 'recommended_patterns': 10000},
    'claude-3.5-sonnet': {'tokens': 200000, 'recommended_patterns': 3500},
    'claude-3-opus': {'tokens': 200000, 'recommended_patterns': 3500},
}

# 기본 설정값 (GPT-4o 기준 보수적 설정)
DEFAULT_CONFIG = {
    'max_patterns': 5000,            # 최대 패턴 수 (저장용)
    'max_patterns_per_source': 2500, # 출처당 최대 패턴 수
    'min_usage_to_keep': 0,          # 유지할 최소 사용 횟수 (0=제한없음)
    'cleanup_threshold': 6000,       # 이 수를 넘으면 자동 정리
    'prompt_pattern_limit': 100,     # 프롬프트에 포함할 최대 패턴 수
    'target_llm': 'gpt-4o',          # 타겟 LLM 모델
}

def load_config() -> dict:
    """설정 로드"""
    config = DEFAULT_CONFIG.copy()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                config.update(user_config)
        except:
            pass
    return config

def save_config(config: dict):
    """설정 저장"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

# 오류 출처 분류
ERROR_SOURCES = {
    'image_pdf': {
        'name': '이미지 PDF (Upstage OCR)',
        'description': 'Upstage Document Parser의 OCR 오류 패턴',
        'extensions': ['.pdf'],
        'requires_ocr': True
    },
    'digital_doc': {
        'name': '디지털 문서',
        'description': '라이브러리 변환 버그 패턴',
        'extensions': ['.hwpx', '.docx', '.xlsx', '.pptx', '.pdf'],
        'requires_ocr': False
    }
}


# ============================================================
# 오류 패턴 데이터 구조
# ============================================================
class ErrorPattern:
    """학습된 오류 패턴"""

    def __init__(self, original: str, corrected: str, source: str,
                 context: str = "", category: str = "unknown",
                 reason: str = "", frequency: int = 1, usage_count: int = 0):
        self.original = original
        self.corrected = corrected
        self.source = source  # 'image_pdf' or 'digital_doc'
        self.context = context  # 주변 문맥 (앞뒤 10자)
        self.category = category  # 오류 카테고리
        self.reason = reason  # 수정 이유
        self.frequency = frequency  # 사용자 제출 빈도
        self.usage_count = usage_count  # AI 검수에서 실제 사용된 횟수
        self.pattern_id = self._generate_id()
        self.created_at = datetime.now().isoformat()
        self.last_seen = datetime.now().isoformat()
        self.last_used = None  # 마지막 사용 시간

    def _generate_id(self) -> str:
        """패턴 고유 ID 생성"""
        content = f"{self.original}|{self.corrected}|{self.source}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def mark_used(self):
        """AI 검수에서 패턴이 사용되었을 때 호출"""
        self.usage_count += 1
        self.last_used = datetime.now().isoformat()

    def get_effectiveness_score(self) -> float:
        """
        패턴의 효과성 점수 계산
        - usage_count(실제 사용)에 가중치를 더 많이 부여
        - 최근 사용일수록 점수 높음
        """
        # 기본 점수: 사용 횟수 * 2 + 제출 빈도
        score = (self.usage_count * 2) + self.frequency

        # 최근 사용 가산점
        if self.last_used:
            try:
                last_used_dt = datetime.fromisoformat(self.last_used)
                days_ago = (datetime.now() - last_used_dt).days
                if days_ago < 7:
                    score *= 1.5  # 최근 1주 사용
                elif days_ago < 30:
                    score *= 1.2  # 최근 1달 사용
            except:
                pass

        return score

    def to_dict(self) -> dict:
        return {
            'pattern_id': self.pattern_id,
            'original': self.original,
            'corrected': self.corrected,
            'source': self.source,
            'context': self.context,
            'category': self.category,
            'reason': self.reason,
            'frequency': self.frequency,
            'usage_count': self.usage_count,
            'created_at': self.created_at,
            'last_seen': self.last_seen,
            'last_used': self.last_used
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ErrorPattern':
        pattern = cls(
            original=data['original'],
            corrected=data['corrected'],
            source=data['source'],
            context=data.get('context', ''),
            category=data.get('category', 'unknown'),
            reason=data.get('reason', ''),
            frequency=data.get('frequency', 1),
            usage_count=data.get('usage_count', 0)
        )
        pattern.pattern_id = data.get('pattern_id', pattern._generate_id())
        pattern.created_at = data.get('created_at', datetime.now().isoformat())
        pattern.last_seen = data.get('last_seen', datetime.now().isoformat())
        pattern.last_used = data.get('last_used')
        return pattern


# ============================================================
# 학습 패턴 저장소
# ============================================================
class PatternStore:
    """학습된 패턴 저장 및 관리"""

    def __init__(self, file_path: Path = LEARNED_PATTERNS_FILE):
        self.file_path = file_path
        self.patterns: Dict[str, ErrorPattern] = {}
        self._load()

    def _load(self):
        """파일에서 패턴 로드"""
        if self.file_path.exists():
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for pattern_data in data.get('patterns', []):
                        pattern = ErrorPattern.from_dict(pattern_data)
                        self.patterns[pattern.pattern_id] = pattern
            except json.JSONDecodeError as e:
                print(f"[PatternStore] JSON 파싱 오류: {e}")
                print(f"[PatternStore] 파일 경로: {self.file_path}")
                print(f"[PatternStore] 파일을 초기화합니다...")
                # 손상된 파일 백업 후 초기화
                backup_path = str(self.file_path) + '.corrupted'
                try:
                    import shutil
                    shutil.copy(self.file_path, backup_path)
                    print(f"[PatternStore] 손상된 파일 백업: {backup_path}")
                except:
                    pass
                self.patterns = {}
                self._save()  # 빈 파일로 초기화
            except Exception as e:
                print(f"[PatternStore] 로드 실패: {e}")

    def _save(self):
        """파일에 패턴 저장"""
        try:
            data = {
                'version': '1.0.0',
                'updated_at': datetime.now().isoformat(),
                'total_patterns': len(self.patterns),
                'patterns': [p.to_dict() for p in self.patterns.values()]
            }
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[PatternStore] 저장 실패: {e}")

    def add_pattern(self, pattern: ErrorPattern) -> bool:
        """패턴 추가 또는 빈도 증가"""
        if pattern.pattern_id in self.patterns:
            # 기존 패턴 빈도 증가
            existing = self.patterns[pattern.pattern_id]
            existing.frequency += 1
            existing.last_seen = datetime.now().isoformat()
        else:
            # 새 패턴 추가
            self.patterns[pattern.pattern_id] = pattern

        self._save()
        return True

    def get_patterns_by_source(self, source: str) -> List[ErrorPattern]:
        """출처별 패턴 조회"""
        return [p for p in self.patterns.values() if p.source == source]

    def get_top_patterns(self, source: str = None, limit: int = None) -> List[ErrorPattern]:
        """
        효과성 점수 기준 상위 패턴 조회

        Args:
            source: 출처 필터 (None이면 전체)
            limit: 최대 개수 (None이면 설정값 사용)
        """
        config = load_config()
        if limit is None:
            limit = config.get('prompt_pattern_limit', 100)

        patterns = list(self.patterns.values())
        if source:
            patterns = [p for p in patterns if p.source == source]

        # 효과성 점수순 정렬 (높은 것이 먼저)
        patterns.sort(key=lambda p: p.get_effectiveness_score(), reverse=True)
        return patterns[:limit]

    def mark_pattern_used(self, pattern_id: str) -> bool:
        """패턴이 실제 AI 검수에서 사용되었음을 기록"""
        if pattern_id in self.patterns:
            self.patterns[pattern_id].mark_used()
            self._save()
            return True
        return False

    def mark_patterns_used_by_content(self, original: str, corrected: str, source: str = None):
        """
        AI가 수정한 내용과 일치하는 패턴의 사용 횟수 증가
        (AI 검수 결과와 패턴을 매칭하여 호출)
        """
        for pattern in self.patterns.values():
            if pattern.original == original and pattern.corrected == corrected:
                if source is None or pattern.source == source:
                    pattern.mark_used()
        self._save()

    def cleanup(self, max_patterns: int = None, max_per_source: int = None) -> dict:
        """
        저사용 패턴 정리

        Args:
            max_patterns: 유지할 최대 패턴 수
            max_per_source: 출처당 최대 패턴 수

        Returns:
            정리 결과 통계
        """
        config = load_config()
        max_patterns = max_patterns or config.get('max_patterns', 10000)
        max_per_source = max_per_source or config.get('max_patterns_per_source', 5000)

        before_count = len(self.patterns)
        removed = {'total': 0, 'by_source': defaultdict(int)}

        # 1. 출처별 정리
        for source in ['image_pdf', 'digital_doc']:
            source_patterns = self.get_patterns_by_source(source)

            if len(source_patterns) > max_per_source:
                # 효과성 점수순 정렬
                source_patterns.sort(key=lambda p: p.get_effectiveness_score(), reverse=True)

                # 하위 패턴 삭제
                to_remove = source_patterns[max_per_source:]
                for p in to_remove:
                    if p.pattern_id in self.patterns:
                        del self.patterns[p.pattern_id]
                        removed['by_source'][source] += 1
                        removed['total'] += 1

        # 2. 전체 개수 제한
        if len(self.patterns) > max_patterns:
            all_patterns = list(self.patterns.values())
            all_patterns.sort(key=lambda p: p.get_effectiveness_score(), reverse=True)

            to_remove = all_patterns[max_patterns:]
            for p in to_remove:
                if p.pattern_id in self.patterns:
                    del self.patterns[p.pattern_id]
                    removed['total'] += 1

        self._save()

        return {
            'before': before_count,
            'after': len(self.patterns),
            'removed': removed['total'],
            'removed_by_source': dict(removed['by_source'])
        }

    def auto_cleanup_if_needed(self) -> Optional[dict]:
        """임계값 초과 시 자동 정리"""
        config = load_config()
        threshold = config.get('cleanup_threshold', 12000)

        if len(self.patterns) >= threshold:
            return self.cleanup()
        return None

    def get_stats(self) -> dict:
        """통계 조회"""
        config = load_config()
        stats = {
            'total': len(self.patterns),
            'max_patterns': config.get('max_patterns', 10000),
            'by_source': defaultdict(int),
            'by_category': defaultdict(int),
            'top_frequency': 0,
            'top_usage': 0,
            'total_usage': 0,
            'patterns_with_usage': 0,  # 한 번이라도 사용된 패턴 수
            'avg_effectiveness': 0
        }

        total_score = 0
        for p in self.patterns.values():
            stats['by_source'][p.source] += 1
            stats['by_category'][p.category] += 1
            if p.frequency > stats['top_frequency']:
                stats['top_frequency'] = p.frequency
            if p.usage_count > stats['top_usage']:
                stats['top_usage'] = p.usage_count
            stats['total_usage'] += p.usage_count
            if p.usage_count > 0:
                stats['patterns_with_usage'] += 1
            total_score += p.get_effectiveness_score()

        if stats['total'] > 0:
            stats['avg_effectiveness'] = round(total_score / stats['total'], 2)

        return dict(stats)


# ============================================================
# 오류 수집기
# ============================================================
class ErrorCollector:
    """사용자 수정 내역 수집"""

    def __init__(self):
        self.store = PatternStore()
        self.pending_sync: List[dict] = []
        self._load_pending()

    def _load_pending(self):
        """동기화 대기 중인 수정 내역 로드"""
        if PENDING_SYNC_FILE.exists():
            try:
                with open(PENDING_SYNC_FILE, 'r', encoding='utf-8') as f:
                    self.pending_sync = json.load(f)
            except:
                self.pending_sync = []

    def _save_pending(self):
        """동기화 대기 내역 저장"""
        try:
            with open(PENDING_SYNC_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.pending_sync, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ErrorCollector] 대기 내역 저장 실패: {e}")

    def determine_source(self, file_path: str, was_ocr_processed: bool = False) -> str:
        """파일 경로와 처리 방식으로 오류 출처 결정"""
        ext = Path(file_path).suffix.lower()

        # 이미지 PDF는 OCR 처리된 경우에만
        if ext == '.pdf' and was_ocr_processed:
            return 'image_pdf'

        # 나머지는 디지털 문서
        return 'digital_doc'

    def collect_correction(self,
                          original: str,
                          corrected: str,
                          file_path: str,
                          was_ocr_processed: bool = False,
                          context: str = "",
                          category: str = "unknown",
                          reason: str = "",
                          decision: str = "confirmed") -> bool:
        """
        사용자 수정 내역 수집

        Args:
            original: 원본 텍스트
            corrected: 수정된 텍스트
            file_path: 원본 파일 경로
            was_ocr_processed: OCR 처리 여부
            context: 주변 문맥
            category: 오류 카테고리
            reason: 수정 이유
            decision: 사용자 결정 (confirmed, rejected, edited)
        """
        # 거부된 수정은 수집하지 않음 (AI가 틀렸으므로)
        if decision == 'rejected':
            return False

        # 오류 출처 결정
        source = self.determine_source(file_path, was_ocr_processed)

        # 패턴 생성
        pattern = ErrorPattern(
            original=original,
            corrected=corrected,
            source=source,
            context=context,
            category=category,
            reason=reason
        )

        # 로컬 저장
        self.store.add_pattern(pattern)

        # 자동 정리 (임계값 초과 시)
        cleanup_result = self.store.auto_cleanup_if_needed()
        if cleanup_result:
            print(f"[AutoCleanup] {cleanup_result['removed']}개 패턴 정리됨")

        # 서버 동기화 대기열에 추가
        self.pending_sync.append({
            **pattern.to_dict(),
            'user_decision': decision,
            'collected_at': datetime.now().isoformat()
        })
        self._save_pending()

        return True

    def sync_to_server(self) -> Tuple[bool, str]:
        """
        수집된 패턴을 서버로 동기화

        Returns:
            (성공여부, 메시지)
        """
        if not self.pending_sync:
            return True, "동기화할 내역 없음"

        try:
            # 서버로 전송
            response = requests.post(
                f"{ERROR_COLLECTION_SERVER}/submit",
                json={
                    'patterns': self.pending_sync,
                    'client_version': '1.0.0',
                    'submitted_at': datetime.now().isoformat()
                },
                timeout=10
            )

            if response.status_code == 200:
                # 성공 시 대기열 비우기
                synced_count = len(self.pending_sync)
                self.pending_sync = []
                self._save_pending()
                return True, f"{synced_count}개 패턴 동기화 완료"
            else:
                return False, f"서버 오류: {response.status_code}"

        except requests.exceptions.RequestException as e:
            # 네트워크 오류 - 나중에 재시도
            return False, f"네트워크 오류: {str(e)}"

    def fetch_from_server(self) -> Tuple[bool, str]:
        """
        서버에서 최신 패턴 가져오기

        Returns:
            (성공여부, 메시지)
        """
        try:
            response = requests.get(
                f"{ERROR_COLLECTION_SERVER}/patterns",
                params={
                    'min_frequency': 3,  # 최소 3회 이상 발생한 패턴만
                    'limit': 500
                },
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                new_count = 0

                for pattern_data in data.get('patterns', []):
                    pattern = ErrorPattern.from_dict(pattern_data)
                    if pattern.pattern_id not in self.store.patterns:
                        self.store.patterns[pattern.pattern_id] = pattern
                        new_count += 1
                    else:
                        # 빈도 업데이트 (서버 값이 더 크면)
                        existing = self.store.patterns[pattern.pattern_id]
                        if pattern.frequency > existing.frequency:
                            existing.frequency = pattern.frequency

                self.store._save()
                return True, f"{new_count}개 새 패턴 추가됨"
            else:
                return False, f"서버 오류: {response.status_code}"

        except requests.exceptions.RequestException as e:
            return False, f"네트워크 오류: {str(e)}"


# ============================================================
# 프롬프트 생성기
# ============================================================
class PromptEnhancer:
    """학습된 패턴을 프롬프트에 통합"""

    def __init__(self, store: PatternStore = None):
        self.store = store or PatternStore()

    def generate_learned_rules_section(self, source: str = None, max_patterns: int = 50) -> str:
        """
        학습된 패턴을 프롬프트 섹션으로 변환 (효과성 점수순 정렬)

        Args:
            source: 'image_pdf' 또는 'digital_doc' (None이면 전체)
            max_patterns: 포함할 최대 패턴 수

        Returns:
            프롬프트에 추가할 마크다운 텍스트
        """
        patterns = self.store.get_top_patterns(source=source, limit=max_patterns)

        if not patterns:
            return ""

        sections = []

        # 출처별 그룹화
        by_source = defaultdict(list)
        for p in patterns:
            by_source[p.source].append(p)

        for source_key, source_patterns in by_source.items():
            source_info = ERROR_SOURCES.get(source_key, {})
            source_name = source_info.get('name', source_key)

            section = f"\n### 학습된 오류 패턴 ({source_name})\n"
            section += "| 오류 | 정답 | 제출 | 사용 |\n"
            section += "|------|------|------|------|\n"

            for p in source_patterns[:25]:  # 각 출처당 최대 25개
                section += f"| {p.original} | {p.corrected} | {p.frequency} | {p.usage_count} |\n"

            sections.append(section)

        return "\n".join(sections)

    def enhance_review_rules(self, rules: dict) -> dict:
        """
        기존 review_rules에 학습된 패턴 추가

        Args:
            rules: 기존 review_rules.json 내용

        Returns:
            학습된 패턴이 추가된 rules
        """
        enhanced = rules.copy()

        # 학습된 오류 섹션 추가
        if '학습된_오류' not in enhanced:
            enhanced['학습된_오류'] = {}

        # 이미지 PDF 오류 패턴 (효과성 점수순)
        image_patterns = self.store.get_top_patterns(source='image_pdf', limit=100)
        if image_patterns:
            enhanced['학습된_오류']['이미지_PDF_OCR'] = {
                '설명': 'Upstage Document Parser에서 자주 발생하는 OCR 오류 (사용빈도순 정렬)',
                '패턴_수': len(image_patterns),
                '패턴': [
                    {
                        '오류': p.original,
                        '정답': p.corrected,
                        '제출': p.frequency,
                        '사용': p.usage_count,
                        '효과점수': round(p.get_effectiveness_score(), 1)
                    }
                    for p in image_patterns
                ]
            }

        # 디지털 문서 오류 패턴 (효과성 점수순)
        digital_patterns = self.store.get_top_patterns(source='digital_doc', limit=100)
        if digital_patterns:
            enhanced['학습된_오류']['디지털_문서'] = {
                '설명': '라이브러리 변환 시 자주 발생하는 버그 (사용빈도순 정렬)',
                '패턴_수': len(digital_patterns),
                '패턴': [
                    {
                        '오류': p.original,
                        '정답': p.corrected,
                        '제출': p.frequency,
                        '사용': p.usage_count,
                        '효과점수': round(p.get_effectiveness_score(), 1)
                    }
                    for p in digital_patterns
                ]
            }

        return enhanced


# ============================================================
# CLI 인터페이스
# ============================================================
def main():
    """CLI 실행"""
    if len(sys.argv) < 2:
        print(json.dumps({
            "error": "사용법: python error_learning.py <command> [args]",
            "commands": ["stats", "sync", "fetch", "export"]
        }))
        return

    command = sys.argv[1]
    collector = ErrorCollector()

    if command == 'stats':
        # 통계 조회
        stats = collector.store.get_stats()
        print(json.dumps({
            "type": "stats",
            "data": stats,
            "pending_sync": len(collector.pending_sync)
        }, ensure_ascii=False))

    elif command == 'sync':
        # 서버로 동기화
        success, message = collector.sync_to_server()
        print(json.dumps({
            "type": "sync_result",
            "success": success,
            "message": message
        }, ensure_ascii=False))

    elif command == 'fetch':
        # 서버에서 가져오기
        success, message = collector.fetch_from_server()
        print(json.dumps({
            "type": "fetch_result",
            "success": success,
            "message": message
        }, ensure_ascii=False))

    elif command == 'export':
        # 프롬프트 섹션 내보내기
        enhancer = PromptEnhancer(collector.store)
        section = enhancer.generate_learned_rules_section()
        print(json.dumps({
            "type": "prompt_section",
            "content": section
        }, ensure_ascii=False))

    elif command == 'collect':
        # 수정 내역 수집 (테스트용)
        if len(sys.argv) < 5:
            print(json.dumps({"error": "사용법: collect <original> <corrected> <file_path>"}))
            return

        original = sys.argv[2]
        corrected = sys.argv[3]
        file_path = sys.argv[4]

        success = collector.collect_correction(
            original=original,
            corrected=corrected,
            file_path=file_path
        )
        print(json.dumps({
            "type": "collect_result",
            "success": success
        }))

    elif command == 'collect-batch':
        # stdin에서 JSON 배열로 수정 내역 일괄 수집
        input_data = sys.stdin.read()

        try:
            corrections = json.loads(input_data)
            success_count = 0

            for corr in corrections:
                success = collector.collect_correction(
                    original=corr.get('original', ''),
                    corrected=corr.get('corrected', ''),
                    file_path=corr.get('file_path', ''),
                    context=corr.get('context', ''),
                    category=corr.get('category', 'unknown'),
                    reason=corr.get('reason', ''),
                    decision=corr.get('decision', 'confirmed')
                )
                if success:
                    success_count += 1

            print(json.dumps({
                "type": "collect_batch_result",
                "success": True,
                "total": len(corrections),
                "collected": success_count
            }))

        except json.JSONDecodeError as e:
            print(json.dumps({
                "type": "collect_batch_result",
                "success": False,
                "error": f"JSON 파싱 오류: {str(e)}"
            }))

    elif command == 'cleanup':
        # 저사용 패턴 정리 (수동 실행)
        max_patterns = int(sys.argv[2]) if len(sys.argv) > 2 else None
        result = collector.store.cleanup(max_patterns=max_patterns)
        print(json.dumps({
            "type": "cleanup_result",
            "success": True,
            **result
        }, ensure_ascii=False))

    elif command == 'config':
        # 설정 조회/변경
        if len(sys.argv) < 3:
            # 현재 설정 조회
            config = load_config()
            print(json.dumps({
                "type": "config",
                "data": config
            }, ensure_ascii=False))
        else:
            # 설정 변경
            key = sys.argv[2]
            value = sys.argv[3] if len(sys.argv) > 3 else None

            config = load_config()
            if value is not None:
                # 숫자 설정값 변환
                if key in ['max_patterns', 'max_patterns_per_source', 'min_usage_to_keep',
                           'cleanup_threshold', 'prompt_pattern_limit']:
                    value = int(value)
                config[key] = value
                save_config(config)
                print(json.dumps({
                    "type": "config_update",
                    "success": True,
                    "key": key,
                    "value": value
                }, ensure_ascii=False))
            else:
                # 단일 키 조회
                print(json.dumps({
                    "type": "config_value",
                    "key": key,
                    "value": config.get(key)
                }, ensure_ascii=False))

    elif command == 'mark-used':
        # 패턴 사용 기록 (AI 검수 결과와 매칭 시 호출)
        if len(sys.argv) < 4:
            print(json.dumps({"error": "사용법: mark-used <original> <corrected> [source]"}))
            return

        original = sys.argv[2]
        corrected = sys.argv[3]
        source = sys.argv[4] if len(sys.argv) > 4 else None

        collector.store.mark_patterns_used_by_content(original, corrected, source)
        print(json.dumps({
            "type": "mark_used_result",
            "success": True,
            "original": original,
            "corrected": corrected
        }, ensure_ascii=False))

    elif command == 'top-patterns':
        # 효과성 점수 기준 상위 패턴 조회
        source = sys.argv[2] if len(sys.argv) > 2 else None
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 50

        patterns = collector.store.get_top_patterns(source=source, limit=limit)
        print(json.dumps({
            "type": "top_patterns",
            "count": len(patterns),
            "patterns": [
                {
                    'original': p.original,
                    'corrected': p.corrected,
                    'source': p.source,
                    'frequency': p.frequency,
                    'usage_count': p.usage_count,
                    'effectiveness_score': p.get_effectiveness_score()
                }
                for p in patterns
            ]
        }, ensure_ascii=False))

    else:
        print(json.dumps({
            "error": f"알 수 없는 명령: {command}",
            "commands": ["stats", "sync", "fetch", "export", "collect", "collect-batch",
                        "cleanup", "config", "mark-used", "top-patterns"]
        }))


if __name__ == "__main__":
    main()
