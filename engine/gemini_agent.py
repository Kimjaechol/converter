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


# ============================================================
# 시스템 프롬프트
# ============================================================
SYSTEM_PROMPT = """당신은 LawPro 법률 문서 OCR 검수 전문가입니다.

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

수정된 HTML을 그대로 출력합니다. 추가 설명이나 마크다운 코드 블록 없이 순수 HTML만 반환하세요.
"""


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

    def review_document(self, content: str) -> str:
        """
        단일 문서 검수

        Args:
            content: HTML 문서 내용

        Returns:
            수정된 HTML
        """
        # 문서가 너무 길면 청크로 분할
        if len(content) > self.CHUNK_SIZE:
            return self._review_chunked(content)

        return self._call_gemini(content)

    def _review_chunked(self, content: str) -> str:
        """대용량 문서 청크 처리"""
        # HTML을 논리적 단위로 분할 (주요 태그 기준)
        chunks = self._split_html(content)
        reviewed_chunks = []

        for i, chunk in enumerate(chunks):
            self._emit_progress(f"청크 {i+1}/{len(chunks)} 처리 중...")
            reviewed_chunk = self._call_gemini(chunk)
            reviewed_chunks.append(reviewed_chunk)
            time.sleep(0.5)  # Rate limit 방지

        return ''.join(reviewed_chunks)

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

    def _call_gemini(self, content: str) -> str:
        """Gemini API 호출"""
        try:
            prompt = f"""{SYSTEM_PROMPT}

---

## 검수할 문서

{content}

---

위 문서에서 OCR 오류를 찾아 수정하고, 수정된 HTML을 반환하세요.
HTML 태그는 그대로 유지하고 텍스트 오류만 수정합니다.
"""

            response = self.model.generate_content(prompt)

            if response.text:
                # 마크다운 코드 블록 제거
                result = response.text
                result = re.sub(r'^```html\s*', '', result)
                result = re.sub(r'^```\s*', '', result)
                result = re.sub(r'\s*```$', '', result)
                return result.strip()

            return content  # 실패 시 원본 반환

        except Exception as e:
            self._emit_error(f"Gemini API 오류: {str(e)}")
            return content

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
            reviewed_content = agent.review_document(content)
            elapsed = round(time.time() - start_time, 2)

            # 저장
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(reviewed_content)

            print(json.dumps({
                "type": "progress",
                "status": "success",
                "file": filename,
                "time": elapsed
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
def review_single_file(file_path: str, api_key: str, model_name: str = "flash-2.0") -> str:
    """단일 파일 검수"""
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
