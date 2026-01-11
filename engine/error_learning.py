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

# 서버 엔드포인트 (추후 실제 서버로 교체)
ERROR_COLLECTION_SERVER = os.environ.get(
    'LAWPRO_ERROR_SERVER',
    'https://api.lawpro.kr/v1/error-patterns'  # 예시 URL
)

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
                 reason: str = "", frequency: int = 1):
        self.original = original
        self.corrected = corrected
        self.source = source  # 'image_pdf' or 'digital_doc'
        self.context = context  # 주변 문맥 (앞뒤 10자)
        self.category = category  # 오류 카테고리
        self.reason = reason  # 수정 이유
        self.frequency = frequency  # 발생 빈도
        self.pattern_id = self._generate_id()
        self.created_at = datetime.now().isoformat()
        self.last_seen = datetime.now().isoformat()

    def _generate_id(self) -> str:
        """패턴 고유 ID 생성"""
        content = f"{self.original}|{self.corrected}|{self.source}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

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
            'created_at': self.created_at,
            'last_seen': self.last_seen
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
            frequency=data.get('frequency', 1)
        )
        pattern.pattern_id = data.get('pattern_id', pattern._generate_id())
        pattern.created_at = data.get('created_at', datetime.now().isoformat())
        pattern.last_seen = data.get('last_seen', datetime.now().isoformat())
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

    def get_top_patterns(self, source: str = None, limit: int = 100) -> List[ErrorPattern]:
        """빈도순 상위 패턴 조회"""
        patterns = list(self.patterns.values())
        if source:
            patterns = [p for p in patterns if p.source == source]

        # 빈도순 정렬
        patterns.sort(key=lambda p: p.frequency, reverse=True)
        return patterns[:limit]

    def get_stats(self) -> dict:
        """통계 조회"""
        stats = {
            'total': len(self.patterns),
            'by_source': defaultdict(int),
            'by_category': defaultdict(int),
            'top_frequency': 0
        }

        for p in self.patterns.values():
            stats['by_source'][p.source] += 1
            stats['by_category'][p.category] += 1
            if p.frequency > stats['top_frequency']:
                stats['top_frequency'] = p.frequency

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
        학습된 패턴을 프롬프트 섹션으로 변환

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
            section += "| 오류 | 정답 | 발생빈도 |\n"
            section += "|------|------|----------|\n"

            for p in source_patterns[:25]:  # 각 출처당 최대 25개
                section += f"| {p.original} | {p.corrected} | {p.frequency}회 |\n"

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

        # 이미지 PDF 오류 패턴
        image_patterns = self.store.get_top_patterns(source='image_pdf', limit=100)
        if image_patterns:
            enhanced['학습된_오류']['이미지_PDF_OCR'] = {
                '설명': 'Upstage Document Parser에서 자주 발생하는 OCR 오류',
                '패턴_수': len(image_patterns),
                '패턴': [
                    {
                        '오류': p.original,
                        '정답': p.corrected,
                        '빈도': p.frequency
                    }
                    for p in image_patterns
                ]
            }

        # 디지털 문서 오류 패턴
        digital_patterns = self.store.get_top_patterns(source='digital_doc', limit=100)
        if digital_patterns:
            enhanced['학습된_오류']['디지털_문서'] = {
                '설명': '라이브러리 변환 시 자주 발생하는 버그',
                '패턴_수': len(digital_patterns),
                '패턴': [
                    {
                        '오류': p.original,
                        '정답': p.corrected,
                        '빈도': p.frequency
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

    else:
        print(json.dumps({"error": f"알 수 없는 명령: {command}"}))


if __name__ == "__main__":
    main()
