#!/usr/bin/env python3
"""
LawPro Fast Converter - Gemini Backup Agent
=============================================
Claude 사용량 소진 시 Gemini로 문서 검수를 수행하는 백업 에이전트

Supported Models:
- gemini-2.0-flash (최신, 권장)
- gemini-1.5-flash (안정적)
- gemini-1.5-pro (고품질)
"""

import os
import sys
import json
import re
import time
from datetime import datetime
from glob import glob
from typing import Optional, List, Dict, Any

try:
    import google.generativeai as genai
except ImportError:
    print(json.dumps({
        "type": "error",
        "msg": "google-generativeai 패키지가 설치되어 있지 않습니다."
    }), flush=True)
    sys.exit(1)

# 검수 규칙 로드
try:
    from rules_converter import get_review_rules, generate_review_prompt
    HAS_RULES = True
except ImportError:
    HAS_RULES = False

# 오류 학습 시스템 로드
try:
    from error_learning import PatternStore
    HAS_ERROR_LEARNING = True
except ImportError:
    HAS_ERROR_LEARNING = False


def load_system_prompt() -> str:
    """검수 규칙에서 시스템 프롬프트 생성"""
    if HAS_RULES:
        rules = get_review_rules()
        system = rules.get('시스템_지시', {})
        role = system.get('역할', '당신은 법률 문서 OCR 검수 전문가입니다.')
        principles = system.get('원칙', [])

        # 오류 카테고리 추출
        categories = rules.get('오류_카테고리', {})
        rules_text = []
        for cat_name, cat_data in categories.items():
            if isinstance(cat_data, dict):
                rules_text.append(f"\n### {cat_name}")
                rules_text.append(f"**설명**: {cat_data.get('설명', '')}")
                rules_text.append(f"**중요도**: {cat_data.get('중요도', '중간')}")
                for rule in cat_data.get('규칙', []):
                    if isinstance(rule, dict):
                        rules_text.append(f"- {rule.get('유형', '')}: {', '.join(rule.get('오류_예시', [])[:5])}")

        # 자주 틀리는 단어
        common = rules.get('자주_틀리는_단어', {})
        common_text = []
        for category, words in common.items():
            if isinstance(words, dict):
                for correct, errors in list(words.items())[:10]:
                    if isinstance(errors, list):
                        common_text.append(f"- {correct}: {', '.join(errors[:3])}")

        return f"""{role}

## 역할 원칙
{chr(10).join(f'- {p}' for p in principles)}

## 검수 항목
{chr(10).join(rules_text)}

## 자주 틀리는 단어 (오류 → 정답)
{chr(10).join(common_text)}

## 출력 형식
다음 구조로 출력하세요:

===HTML_START===
(수정된 HTML 내용 - 확실/불확실 모든 수정 적용)
===HTML_END===

===확정_수정_START===
| 위치 | 원본 | 수정 | 이유 |
|------|------|------|------|
(확실한 수정만 나열)
===확정_수정_END===

===검토필요_START===
| 위치 | 원본 | 수정 | 이유 |
|------|------|------|------|
(불확실한 수정 - 사용자 검토 필요)
===검토필요_END===
"""

    # 기본 프롬프트 (규칙 파일이 없을 때)
    return SYSTEM_PROMPT_DEFAULT


SYSTEM_PROMPT_DEFAULT = """당신은 LawPro 법률 문서 OCR 검수 전문가입니다.

## 임무
OCR로 변환된 HTML 문서에서 오류를 찾아 수정합니다.

## 주요 OCR 오류 패턴

### 1. 한글-영문 혼동 (가장 흔함)
| 원래 글자 | 오인식 예시 |
|-----------|-------------|
| 을 | Z, z, 2 |
| 를 | Z, z |
| 은 | E, e |
| 이 | 0, O, l, 1 |
| 의 | 9, Q |
| 가 | 7, 71 |

예시:
- "계약Z 체결" → "계약을 체결"
- "권리Z 행사" → "권리를 행사"
- "것E 아니다" → "것은 아니다"

### 2. 숫자-문자 혼동
- 0 ↔ O, o
- 1 ↔ l, I, |
- 2 ↔ Z
- 5 ↔ S, s

### 3. 법률 용어 특수 오류
- "제1조" → "게1초", "게1조", "게l조"
- "제2항" → "게2향", "게Z항"
- "법률" → "벌률", "법을"
- "권리" → "컨리", "권리Z"

## 수정 규칙

1. **HTML 태그 보존**: 모든 HTML 태그는 그대로 유지
2. **텍스트만 수정**: 태그 내부의 텍스트 오류만 수정
3. **문맥 고려**: 문맥상 자연스러운 수정만 적용
4. **고유명사 유지**: 회사명, 인명 등은 수정하지 않음
5. **확실한 경우만**: 불확실한 경우 원문 유지

## 출력 형식

다음 구조로 출력하세요:

===HTML_START===
(수정된 HTML 내용 - 확실/불확실 모든 수정 적용)
===HTML_END===

===확정_수정_START===
| 위치 | 원본 | 수정 | 이유 |
|------|------|------|------|
(확실한 수정만 나열)
===확정_수정_END===

===검토필요_START===
| 위치 | 원본 | 수정 | 이유 |
|------|------|------|------|
(불확실한 수정 - 사용자 검토 필요)
===검토필요_END===
"""


def parse_review_output(output: str) -> dict:
    """
    AI 검수 결과를 파싱하여 구조화된 데이터로 변환

    Returns:
        {
            'html': 수정된 HTML,
            'confirmed_corrections': 확정 수정 목록,
            'uncertain_corrections': 검토 필요 수정 목록
        }
    """
    result = {
        'html': '',
        'confirmed_corrections': [],
        'uncertain_corrections': []
    }

    # HTML 추출
    html_match = re.search(r'===HTML_START===\s*(.*?)\s*===HTML_END===', output, re.DOTALL)
    if html_match:
        result['html'] = html_match.group(1).strip()
    else:
        # 구조화된 출력이 없으면 전체를 HTML로 간주
        result['html'] = output.strip()

    # 확정 수정 추출
    confirmed_match = re.search(r'===확정_수정_START===\s*(.*?)\s*===확정_수정_END===', output, re.DOTALL)
    if confirmed_match:
        result['confirmed_corrections'] = parse_correction_table(confirmed_match.group(1))

    # 검토 필요 수정 추출
    uncertain_match = re.search(r'===검토필요_START===\s*(.*?)\s*===검토필요_END===', output, re.DOTALL)
    if uncertain_match:
        result['uncertain_corrections'] = parse_correction_table(uncertain_match.group(1))

    return result


def parse_correction_table(table_text: str) -> list:
    """
    마크다운 테이블을 파싱하여 수정 목록으로 변환

    Returns:
        [{'location': str, 'original': str, 'corrected': str, 'reason': str}, ...]
    """
    corrections = []
    lines = table_text.strip().split('\n')

    for line in lines:
        # 테이블 구분선이나 헤더 스킵
        if not line.strip() or line.startswith('|--') or '위치' in line:
            continue

        # 테이블 행 파싱
        parts = [p.strip() for p in line.split('|') if p.strip()]
        if len(parts) >= 4:
            corrections.append({
                'location': parts[0],
                'original': parts[1],
                'corrected': parts[2],
                'reason': parts[3]
            })

    return corrections


def track_pattern_usage(corrections: list, source: str = None):
    """
    AI가 수정한 내용과 학습된 패턴을 매칭하여 사용 횟수 기록

    Args:
        corrections: AI 수정 목록 [{'original': str, 'corrected': str, ...}, ...]
        source: 오류 출처 ('image_pdf' 또는 'digital_doc')
    """
    if not HAS_ERROR_LEARNING:
        return

    try:
        store = PatternStore()

        for corr in corrections:
            original = corr.get('original', '')
            corrected = corr.get('corrected', '')

            if original and corrected:
                store.mark_patterns_used_by_content(original, corrected, source)

    except Exception as e:
        # 패턴 추적 실패는 무시 (검수 본연의 기능에 영향 없음)
        pass


# ============================================================
# Gemini Agent 클래스
# ============================================================
class GeminiReviewAgent:
    """Gemini 기반 문서 검수 에이전트"""

    # 지원 모델 목록
    MODELS = {
        "flash-2.0": "gemini-2.0-flash-exp",
        "flash-1.5": "gemini-1.5-flash",
        "pro-1.5": "gemini-1.5-pro"
    }

    # 토큰 제한 (안전 마진 포함)
    MAX_INPUT_TOKENS = 900000  # 1M 토큰 모델 기준
    CHUNK_SIZE = 30000  # 문자 단위 청크 크기

    def __init__(self, api_key: str, model_name: str = "flash-2.0"):
        self.api_key = api_key
        self.model_id = self.MODELS.get(model_name, self.MODELS["flash-2.0"])

        # API 설정
        genai.configure(api_key=api_key)

        # 모델 초기화
        self.model = genai.GenerativeModel(
            model_name=self.model_id,
            generation_config={
                "temperature": 0.1,  # 정확성 최우선
                "top_p": 0.95,
                "max_output_tokens": 8192
            },
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
        )

    def review_document(self, content: str) -> dict:
        """
        단일 문서 검수

        Args:
            content: HTML 문서 내용

        Returns:
            {
                'html': 수정된 HTML,
                'confirmed_corrections': 확정 수정 목록,
                'uncertain_corrections': 검토 필요 수정 목록
            }
        """
        # 문서가 너무 길면 청크로 분할
        if len(content) > self.CHUNK_SIZE:
            return self._review_chunked(content)

        return self._call_gemini(content)

    def _review_chunked(self, content: str) -> dict:
        """대용량 문서 청크 처리"""
        # HTML을 논리적 단위로 분할 (주요 태그 기준)
        chunks = self._split_html(content)
        reviewed_html_parts = []
        all_confirmed = []
        all_uncertain = []

        for i, chunk in enumerate(chunks):
            self._emit_progress(f"청크 {i+1}/{len(chunks)} 처리 중...")
            result = self._call_gemini(chunk)
            reviewed_html_parts.append(result.get('html', chunk))
            all_confirmed.extend(result.get('confirmed_corrections', []))
            all_uncertain.extend(result.get('uncertain_corrections', []))
            time.sleep(0.5)  # Rate limit 방지

        return {
            'html': ''.join(reviewed_html_parts),
            'confirmed_corrections': all_confirmed,
            'uncertain_corrections': all_uncertain
        }

    def _split_html(self, content: str) -> List[str]:
        """HTML을 논리적 청크로 분할"""
        chunks = []
        current_chunk = ""

        # 주요 분할 지점: </div>, </table>, <hr>, </section>
        split_pattern = re.compile(r'(</div>|</table>|<hr[^>]*>|</section>)')

        parts = split_pattern.split(content)

        for part in parts:
            if len(current_chunk) + len(part) > self.CHUNK_SIZE:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = part
            else:
                current_chunk += part

        if current_chunk:
            chunks.append(current_chunk)

        return chunks if chunks else [content]

    def _call_gemini(self, content: str) -> dict:
        """
        Gemini API 호출

        Returns:
            {
                'html': 수정된 HTML,
                'confirmed_corrections': 확정 수정 목록,
                'uncertain_corrections': 검토 필요 수정 목록,
                'raw_response': 원본 응답
            }
        """
        try:
            # 검수 규칙에서 시스템 프롬프트 로드
            system_prompt = load_system_prompt()

            prompt = f"""{system_prompt}

---

## 검수할 문서

{content}

---

위 문서에서 OCR 오류를 찾아 수정하세요.
HTML 태그는 그대로 유지하고 텍스트 오류만 수정합니다.

중요:
- HTML 본문에는 확실한 수정과 불확실한 수정을 모두 적용하세요
- 확정 수정표에는 확실한 수정만 기재하세요
- 검토필요 수정표에는 불확실한 수정(고유명사, 맥락상 애매한 경우 등)을 기재하세요

반드시 위의 출력 형식을 따라주세요.
"""

            response = self.model.generate_content(prompt)

            if response.text:
                # 마크다운 코드 블록 제거
                raw_result = response.text
                raw_result = re.sub(r'^```html\s*', '', raw_result)
                raw_result = re.sub(r'^```\s*', '', raw_result)
                raw_result = re.sub(r'\s*```$', '', raw_result)

                # 구조화된 출력 파싱
                parsed = parse_review_output(raw_result)
                parsed['raw_response'] = raw_result
                return parsed

            return {
                'html': content,
                'confirmed_corrections': [],
                'uncertain_corrections': [],
                'raw_response': ''
            }

        except json.JSONDecodeError as e:
            self._emit_error(f"JSON 파싱 오류: {str(e)} - 학습 패턴 파일을 확인하세요")
            return {
                'html': content,
                'confirmed_corrections': [],
                'uncertain_corrections': [],
                'raw_response': '',
                'error': f"JSON 파싱 오류: {str(e)}"
            }
        except Exception as e:
            error_type = type(e).__name__
            self._emit_error(f"Gemini API 오류 ({error_type}): {str(e)}")
            return {
                'html': content,
                'confirmed_corrections': [],
                'uncertain_corrections': [],
                'raw_response': '',
                'error': str(e)
            }

    def _emit_progress(self, msg: str):
        """진행 상황 출력"""
        print(json.dumps({"type": "log", "msg": msg}), flush=True)

    def _emit_error(self, msg: str):
        """오류 출력"""
        print(json.dumps({"type": "error", "msg": msg}), flush=True)


# ============================================================
# 배치 처리
# ============================================================
def batch_review(folder_path: str, api_key: str, model_name: str = "flash-2.0"):
    """
    폴더 내 모든 문서 배치 검수

    Args:
        folder_path: 작업 폴더 경로
        api_key: Gemini API 키
        model_name: 사용할 모델 (flash-2.0, flash-1.5, pro-1.5)
    """
    # 입출력 경로 설정
    input_dir = os.path.join(folder_path, "Converted_HTML")
    output_dir = os.path.join(folder_path, "Final_Reviewed_Gemini")

    if not os.path.exists(input_dir):
        print(json.dumps({
            "type": "error",
            "msg": f"입력 폴더가 없습니다: {input_dir}"
        }), flush=True)
        return

    os.makedirs(output_dir, exist_ok=True)

    # HTML 파일 목록 (새 구조: Converted_HTML/{doc_name}/view.html)
    html_files = glob(os.path.join(input_dir, "*", "view.html"))

    # 기존 구조도 지원 (Converted_HTML/*.html)
    html_files.extend(glob(os.path.join(input_dir, "*.html")))

    if not html_files:
        print(json.dumps({
            "type": "warning",
            "msg": "검수할 HTML 파일이 없습니다"
        }), flush=True)
        return

    # 초기화 메시지
    print(json.dumps({
        "type": "init",
        "total": len(html_files),
        "model": model_name,
        "output_dir": output_dir
    }), flush=True)

    # 에이전트 초기화
    agent = GeminiReviewAgent(api_key=api_key, model_name=model_name)

    # 통계
    stats = {"success": 0, "fail": 0, "skipped": 0}

    for file_path in html_files:
        filename = os.path.basename(file_path)
        output_path = os.path.join(output_dir, filename)
        corrections_path = os.path.join(output_dir, filename.replace('.html', '_corrections.json'))

        try:
            # 이미 검수된 파일 스킵
            if os.path.exists(output_path):
                print(json.dumps({
                    "type": "progress",
                    "status": "skipped",
                    "file": filename,
                    "msg": "이미 검수 완료"
                }), flush=True)
                stats["skipped"] += 1
                continue

            # 문서 읽기
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 검수 실행
            start_time = time.time()
            result = agent.review_document(content)
            elapsed = round(time.time() - start_time, 2)

            # HTML 저장
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(result.get('html', content))

            # 수정 내역 저장 (JSON)
            confirmed = result.get('confirmed_corrections', [])
            uncertain = result.get('uncertain_corrections', [])

            corrections_data = {
                'file': filename,
                'reviewed_at': datetime.now().isoformat(),
                'confirmed_corrections': confirmed,
                'uncertain_corrections': uncertain,
                'stats': {
                    'confirmed_count': len(confirmed),
                    'uncertain_count': len(uncertain)
                }
            }
            with open(corrections_path, 'w', encoding='utf-8') as f:
                json.dump(corrections_data, f, ensure_ascii=False, indent=2)

            # 학습된 패턴 사용 기록 (확정 수정만)
            all_corrections = confirmed + uncertain
            if all_corrections:
                track_pattern_usage(all_corrections)

            # 검토 필요 항목 수
            uncertain_count = len(result.get('uncertain_corrections', []))

            print(json.dumps({
                "type": "progress",
                "status": "success",
                "file": filename,
                "time": elapsed,
                "confirmed_count": len(result.get('confirmed_corrections', [])),
                "uncertain_count": uncertain_count,
                "needs_review": uncertain_count > 0
            }), flush=True)

            stats["success"] += 1

            # Rate limit 방지
            time.sleep(1)

        except Exception as e:
            print(json.dumps({
                "type": "progress",
                "status": "fail",
                "file": filename,
                "error": str(e)
            }), flush=True)
            stats["fail"] += 1

    # 완료 메시지
    print(json.dumps({
        "type": "complete",
        "success": stats["success"],
        "fail": stats["fail"],
        "skipped": stats["skipped"],
        "output_dir": output_dir
    }), flush=True)


# ============================================================
# 단일 파일 처리
# ============================================================
def review_single_file(file_path: str, api_key: str, model_name: str = "flash-2.0") -> dict:
    """
    단일 파일 검수

    Returns:
        {
            'html': 수정된 HTML,
            'confirmed_corrections': 확정 수정 목록,
            'uncertain_corrections': 검토 필요 수정 목록
        }
    """
    agent = GeminiReviewAgent(api_key=api_key, model_name=model_name)

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    return agent.review_document(content)


# ============================================================
# 메인 실행
# ============================================================
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({
            "type": "error",
            "msg": "사용법: python gemini_agent.py <폴더경로> <API키> [모델명]"
        }), flush=True)
        sys.exit(1)

    folder_path = sys.argv[1]
    api_key = sys.argv[2]
    model_name = sys.argv[3] if len(sys.argv) > 3 else "flash-2.0"

    batch_review(folder_path, api_key, model_name)
