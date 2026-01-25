#!/usr/bin/env python3
"""
LawPro Fast Converter - Gemini 3.0 Flash 교정 모듈
====================================================
모든 문서 변환 결과를 Gemini 3.0 Flash로 교정합니다.

이미지 PDF/이미지 파일: 원본 파일과 HTML을 비교 대조하여 교정
디지털 PDF: 원본 PDF와 HTML을 비교 대조하여 교정
일반 문서(docx, hwpx, xlsx, pptx): HTML 텍스트의 문맥/서식 교정

사용 모델: gemini-3-flash-preview (Gemini 3.0 Flash)
SDK: google-genai (0.3+)
"""

import os
import sys
import json
import re
import time
import base64
import mimetypes
from typing import Optional, Dict, Any

# Gemini SDK 로드 (google-genai)
try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False


# ============================================================
# 교정 프롬프트: 원본 파일 대조 가능한 경우 (PDF, 이미지)
# ============================================================
CORRECTION_WITH_ORIGINAL_PROMPT = """당신은 문서 변환 결과를 교정하는 최고 수준의 전문가입니다.

## 핵심 지시사항
교정을 할 때 절대로 하나도 빠트리지 말고 전체 페이지를 정밀하게 검토하고, 조금이라도 문맥이 안 맞거나 내용이 원본과 다를 수 있다고 의심이 되는 부분은 반드시 원본 문서와 대조 비교해서 검토하여 원본과 동일한 내용과 형식으로 변환할 것.

## 임무
아래에 두 가지가 주어집니다:
1. **원본 문서** (PDF 또는 이미지 파일)
2. **변환된 HTML** (문서 변환 엔진이 출력한 결과)

당신의 임무는 **원본 문서와 변환된 HTML을 철저히 비교 대조하여**, 변환 과정에서 발생한 모든 오류를 빠짐없이 찾아 수정하는 것입니다.

## 교정 원칙

### 1. 원본과 완벽한 대조 (가장 중요)
- 원본 문서의 모든 페이지, 모든 문단, 모든 표, 모든 항목을 빠짐없이 확인하세요
- 원본에 있는 내용이 HTML에 누락되었다면 반드시 복원하세요
- 원본에 없는 내용이 HTML에 추가되었다면 반드시 제거하세요
- 한 글자, 한 숫자도 놓치지 마세요

### 2. 문맥 연결성 정밀 확인
- 문장의 앞뒤 문맥이 자연스럽게 연결되는지 모든 문장을 확인하세요
- 의미가 통하지 않는 부분은 반드시 원본을 다시 확인하여 교정하세요
- 한국어 문법에 맞지 않는 부분을 교정하세요
- 조금이라도 의심스러운 부분은 반드시 원본과 대조하세요

### 3. OCR 오류 패턴 주의 (스캔 문서의 경우)
- 한글-영문 혼동: "을" → "Z", "를" → "Z", "은" → "E", "이" → "0/l"
- 숫자-문자 혼동: 0↔O, 1↔l/I, 2↔Z, 5↔S, 6↔b, 8↔B
- 글자 누락: 조사나 어미 등 작은 글자가 빠지는 경우
- 비슷한 글자 혼동: "가"↔"71", "의"↔"9", "제"↔"게", "대"↔"머"
- 띄어쓰기 오류, 줄바꿈 오류
- 특수문자 누락 또는 변환 오류

### 4. HTML 구조 절대 보존
- 모든 HTML 태그는 반드시 그대로 유지하세요
- 표(table) 구조를 절대 변경하지 마세요 (rowspan, colspan, thead, tbody 포함)
- 서식 태그(strong, em, u, b, i 등)를 유지하세요
- class, style, id 등 모든 속성을 보존하세요
- 텍스트 내용만 교정하세요

### 5. 서식 정확도
- 제목(h1, h2, h3 등)의 텍스트를 정확히 교정하세요
- 볼드체(strong/b)와 이탤릭체(em/i) 안의 텍스트도 교정하세요
- 표 셀(td, th) 안의 텍스트를 원본과 대조하여 교정하세요
- 리스트(ul, ol, li) 항목의 텍스트를 교정하세요
- 각주, 미주, 주석의 텍스트도 확인하세요

## 출력 형식
교정된 HTML만 출력하세요. 설명이나 주석 없이, 순수한 HTML 코드만 반환하세요.
다른 텍스트나 마크다운 코드블록(```)을 포함하지 마세요.
입력받은 HTML의 전체 구조를 유지하면서, 텍스트 오류만 수정하여 전체 HTML을 반환하세요."""


# ============================================================
# 교정 프롬프트: 원본 파일 없이 텍스트만 교정 (docx, hwpx, xlsx, pptx)
# ============================================================
CORRECTION_TEXT_ONLY_PROMPT = """당신은 문서 변환 결과를 교정하는 최고 수준의 전문가입니다.

## 핵심 지시사항
교정을 할 때 절대로 하나도 빠트리지 말고 전체 페이지를 정밀하게 검토하고, 조금이라도 문맥이 안 맞거나 내용이 이상하다고 의심이 되는 부분은 반드시 꼼꼼히 검토하여 올바른 내용과 형식으로 교정할 것.

## 임무
아래에 문서 변환 엔진이 출력한 HTML이 주어집니다.
당신의 임무는 변환된 HTML의 텍스트를 철저히 검토하여 오류를 빠짐없이 찾아 수정하는 것입니다.

## 교정 원칙

### 1. 전체 페이지 정밀 검토 (가장 중요)
- 모든 문단, 모든 표, 모든 항목을 빠짐없이 확인하세요
- 한 글자, 한 숫자도 놓치지 마세요
- 변환 과정에서 깨진 글자나 인코딩 오류를 수정하세요
- 누락된 텍스트가 있는지 문맥으로 판단하세요

### 2. 문맥 연결성 정밀 확인
- 문장의 앞뒤 문맥이 자연스럽게 연결되는지 모든 문장을 확인하세요
- 의미가 통하지 않는 부분을 교정하세요
- 한국어 문법에 맞지 않는 부분을 교정하세요
- 오타, 탈자를 찾아 수정하세요
- 띄어쓰기 오류를 교정하세요

### 3. 변환 오류 패턴 주의
- 깨진 문자(mojibake): 인코딩 오류로 나타나는 깨진 글자
- 누락된 텍스트: 변환 과정에서 빠진 내용
- 잘못된 줄바꿈: 문단이 비정상적으로 분리된 경우
- 표 내용 누락: 셀 내부 텍스트가 빠진 경우
- 서식 태그 불일치: 열린 태그가 닫히지 않은 경우

### 4. HTML 구조 절대 보존
- 모든 HTML 태그는 반드시 그대로 유지하세요
- 표(table) 구조를 절대 변경하지 마세요 (rowspan, colspan, thead, tbody 포함)
- 서식 태그(strong, em, u, b, i 등)를 유지하세요
- class, style, id 등 모든 속성을 보존하세요
- 텍스트 내용만 교정하세요

### 5. 서식 정확도
- 제목(h1, h2, h3 등)의 텍스트를 정확히 교정하세요
- 볼드체(strong/b)와 이탤릭체(em/i) 안의 텍스트도 교정하세요
- 표 셀(td, th) 안의 텍스트를 교정하세요
- 리스트(ul, ol, li) 항목의 텍스트를 교정하세요

## 출력 형식
교정된 HTML만 출력하세요. 설명이나 주석 없이, 순수한 HTML 코드만 반환하세요.
다른 텍스트나 마크다운 코드블록(```)을 포함하지 마세요.
입력받은 HTML의 전체 구조를 유지하면서, 텍스트 오류만 수정하여 전체 HTML을 반환하세요."""


# ============================================================
# 청크 교정 프롬프트
# ============================================================
CORRECTION_CHUNK_WITH_ORIGINAL = """원본 문서와 비교하여 아래 HTML 부분의 텍스트 오류를 교정하세요.
절대로 하나도 빠트리지 말고 전체를 정밀하게 검토하고, 조금이라도 문맥이 안 맞거나 원본과 다를 수 있다고 의심이 되는 부분은 반드시 원본과 대조하여 수정하세요.
HTML 태그와 구조는 그대로 유지하고, 텍스트만 수정하세요.
교정된 HTML만 출력하세요 (설명 없이)."""

CORRECTION_CHUNK_TEXT_ONLY = """아래 HTML 부분의 텍스트 오류를 교정하세요.
절대로 하나도 빠트리지 말고 전체를 정밀하게 검토하고, 조금이라도 문맥이 안 맞거나 내용이 이상한 부분은 반드시 수정하세요.
HTML 태그와 구조는 그대로 유지하고, 텍스트만 수정하세요.
교정된 HTML만 출력하세요 (설명 없이)."""


# 원본 대조 가능한 파일 확장자
ORIGINAL_COMPARABLE_EXTENSIONS = (
    '.pdf',
    '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif', '.webp'
)


def _emit_log(msg: str, log_type: str = "log"):
    """로그 메시지 출력 (stderr로 Electron에 전달)"""
    print(json.dumps({"type": log_type, "msg": msg}), file=sys.stderr, flush=True)


class GeminiCorrector:
    """Gemini 3.0 Flash를 이용한 HTML 교정기"""

    MODEL_NAME = "gemini-3-flash-preview"
    CHUNK_SIZE = 25000  # 문자 단위 청크 크기
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # 초

    def __init__(self, api_key: str):
        """
        GeminiCorrector 초기화

        Args:
            api_key: Gemini API 키 (GEMINI_API_KEY)
        """
        if not HAS_GENAI:
            raise ImportError(
                "google-genai 패키지가 설치되어 있지 않습니다. "
                "'pip install google-genai' 명령어로 설치하세요."
            )

        self.api_key = api_key
        self.client = genai.Client(api_key=api_key)

    def correct_html(self, html_content: str, original_file_path: str) -> str:
        """
        변환된 HTML을 Gemini 3.0 Flash로 교정

        Args:
            html_content: 변환된 HTML 문자열
            original_file_path: 원본 파일 경로

        Returns:
            교정된 HTML 문자열 (오류 시 원본 반환)
        """
        filename = os.path.basename(original_file_path)
        ext = os.path.splitext(original_file_path)[1].lower()

        # 원본 대조 가능 여부 판단
        has_original = ext in ORIGINAL_COMPARABLE_EXTENSIONS

        if has_original:
            _emit_log(f"[Gemini 교정] {filename} - 원본 대조 교정 시작 (Gemini 3.0 Flash)")
        else:
            _emit_log(f"[Gemini 교정] {filename} - 텍스트 교정 시작 (Gemini 3.0 Flash)")

        try:
            # 원본 파일 준비 (대조 가능한 경우만)
            file_part = None
            if has_original:
                file_part = self._prepare_file(original_file_path)
                if file_part is None:
                    _emit_log(f"[Gemini 교정] {filename} - 원본 파일 준비 실패, 텍스트 전용 교정으로 전환", "warning")

            # HTML이 너무 긴 경우 청크로 분할
            if len(html_content) > self.CHUNK_SIZE:
                corrected = self._correct_chunked(html_content, file_part, filename)
            else:
                corrected = self._call_gemini(html_content, file_part, filename)

            if corrected and corrected.strip():
                _emit_log(f"[Gemini 교정] {filename} - 교정 완료")
                return corrected
            else:
                _emit_log(f"[Gemini 교정] {filename} - 교정 결과 비어있음, 원본 유지", "warning")
                return html_content

        except Exception as e:
            error_type = type(e).__name__
            _emit_log(f"[Gemini 교정] {filename} - 오류 발생 ({error_type}): {str(e)}", "warning")
            return html_content

    def _prepare_file(self, file_path: str) -> Optional[Any]:
        """
        원본 파일을 Gemini API에 전달할 수 있는 형태로 준비

        PDF → 파일 업로드
        이미지 → 인라인 바이트
        """
        ext = os.path.splitext(file_path)[1].lower()

        try:
            if ext == '.pdf':
                # PDF는 파일 업로드 사용
                _emit_log(f"[Gemini 교정] 원본 PDF 업로드 중...")
                uploaded_file = self.client.files.upload(
                    file=file_path,
                    config=types.UploadFileConfig(
                        mime_type="application/pdf"
                    )
                )
                # 업로드 완료 대기
                while uploaded_file.state == "PROCESSING":
                    time.sleep(1)
                    uploaded_file = self.client.files.get(name=uploaded_file.name)
                return uploaded_file

            elif ext in ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif', '.webp'):
                # 이미지는 인라인 바이트로 전달
                mime_type = mimetypes.guess_type(file_path)[0] or "image/png"
                with open(file_path, 'rb') as f:
                    image_data = f.read()
                return types.Part.from_bytes(data=image_data, mime_type=mime_type)

            else:
                return None

        except Exception as e:
            _emit_log(f"[Gemini 교정] 파일 준비 실패: {str(e)}", "warning")
            return None

    def _call_gemini(self, html_content: str, file_part: Optional[Any], filename: str) -> Optional[str]:
        """
        Gemini API 호출하여 HTML 교정

        Args:
            html_content: 교정할 HTML
            file_part: 원본 파일 (None이면 텍스트 전용 교정)
            filename: 파일명 (로그용)

        Returns:
            교정된 HTML 또는 None
        """
        # 원본 대조 가능 여부에 따라 프롬프트 선택
        if file_part is not None:
            system_prompt = CORRECTION_WITH_ORIGINAL_PROMPT
            suffix = "위 HTML을 원본 문서와 비교하여 교정된 HTML을 출력하세요.\n절대로 하나도 빠트리지 말고 전체를 정밀하게 검토하세요.\nHTML 구조와 태그를 절대 변경하지 말고, 텍스트 오류만 수정하세요."
        else:
            system_prompt = CORRECTION_TEXT_ONLY_PROMPT
            suffix = "위 HTML의 텍스트를 정밀하게 교정하여 교정된 HTML을 출력하세요.\n절대로 하나도 빠트리지 말고 전체를 정밀하게 검토하세요.\nHTML 구조와 태그를 절대 변경하지 말고, 텍스트 오류만 수정하세요."

        prompt_text = f"""{system_prompt}

---

## 변환된 HTML (교정 대상)

{html_content}

---

{suffix}"""

        # contents 구성
        if file_part is not None:
            contents = [file_part, prompt_text]
        else:
            contents = [prompt_text]

        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.client.models.generate_content(
                    model=self.MODEL_NAME,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        temperature=0.1,  # 정확성 최우선
                        top_p=0.95,
                        max_output_tokens=65536  # 충분한 출력 길이
                    )
                )

                if response and response.text:
                    result = response.text.strip()
                    # 마크다운 코드 블록 제거
                    result = re.sub(r'^```html\s*\n?', '', result)
                    result = re.sub(r'^```\s*\n?', '', result)
                    result = re.sub(r'\n?```\s*$', '', result)
                    return result.strip()

                _emit_log(f"[Gemini 교정] {filename} - 빈 응답 (시도 {attempt + 1}/{self.MAX_RETRIES})", "warning")

            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                    wait_time = self.RETRY_DELAY * (attempt + 1) * 2
                    _emit_log(f"[Gemini 교정] Rate limit, {wait_time}초 대기 후 재시도...", "warning")
                    time.sleep(wait_time)
                elif attempt < self.MAX_RETRIES - 1:
                    _emit_log(f"[Gemini 교정] 오류 발생, 재시도 {attempt + 1}/{self.MAX_RETRIES}: {error_msg}", "warning")
                    time.sleep(self.RETRY_DELAY)
                else:
                    _emit_log(f"[Gemini 교정] 최종 실패: {error_msg}", "error")

        return None

    def _correct_chunked(self, html_content: str, file_part: Optional[Any], filename: str) -> str:
        """
        대용량 HTML을 청크로 분할하여 교정

        Args:
            html_content: 전체 HTML
            file_part: 원본 파일 (None 가능)
            filename: 파일명

        Returns:
            교정된 전체 HTML
        """
        chunks = self._split_html(html_content)
        _emit_log(f"[Gemini 교정] {filename} - 대용량 문서, {len(chunks)}개 청크로 분할 교정")

        # 원본 대조 가능 여부에 따라 청크 프롬프트 선택
        if file_part is not None:
            chunk_base_prompt = CORRECTION_CHUNK_WITH_ORIGINAL
        else:
            chunk_base_prompt = CORRECTION_CHUNK_TEXT_ONLY

        corrected_parts = []

        for i, chunk in enumerate(chunks):
            _emit_log(f"[Gemini 교정] {filename} - 청크 {i + 1}/{len(chunks)} 교정 중...")

            chunk_prompt = f"""{chunk_base_prompt}

## 변환된 HTML (청크 {i + 1}/{len(chunks)})

{chunk}

---

교정된 HTML만 출력하세요."""

            # contents 구성
            if file_part is not None:
                contents = [file_part, chunk_prompt]
            else:
                contents = [chunk_prompt]

            corrected_chunk = None
            for attempt in range(self.MAX_RETRIES):
                try:
                    response = self.client.models.generate_content(
                        model=self.MODEL_NAME,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            temperature=0.1,
                            top_p=0.95,
                            max_output_tokens=65536
                        )
                    )

                    if response and response.text:
                        result = response.text.strip()
                        result = re.sub(r'^```html\s*\n?', '', result)
                        result = re.sub(r'^```\s*\n?', '', result)
                        result = re.sub(r'\n?```\s*$', '', result)
                        corrected_chunk = result.strip()
                        break

                except Exception as e:
                    if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                        time.sleep(self.RETRY_DELAY * (attempt + 1) * 2)
                    elif attempt < self.MAX_RETRIES - 1:
                        time.sleep(self.RETRY_DELAY)

            corrected_parts.append(corrected_chunk if corrected_chunk else chunk)

            # 청크 간 대기 (Rate limit 방지)
            if i < len(chunks) - 1:
                time.sleep(1)

        return '\n'.join(corrected_parts)

    def _split_html(self, content: str) -> list:
        """HTML을 논리적 청크로 분할"""
        chunks = []
        current_chunk = ""

        # 주요 분할 지점
        split_pattern = re.compile(r'(</div>|</table>|<hr[^>]*>|</section>|</article>)')
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


def get_gemini_api_key() -> Optional[str]:
    """
    Gemini API 키를 환경변수 또는 설정에서 가져오기

    우선순위:
    1. GEMINI_API_KEY 환경변수
    2. admin_config.json의 gemini_api_key
    3. electron-store에 저장된 키 (main.js에서 전달)
    """
    # 1. 환경변수
    key = os.environ.get('GEMINI_API_KEY', '')
    if key:
        return key

    # 2. admin_config
    try:
        from admin_config import get_admin_config
        config = get_admin_config()
        key = config.get('gemini_api_key', '')
        if key:
            return key
    except (ImportError, Exception):
        pass

    return None


def correct_html_with_gemini(html_content: str, original_file_path: str,
                              api_key: Optional[str] = None) -> str:
    """
    편의 함수: Gemini 3.0 Flash로 HTML 교정

    모든 문서 유형에 대해 교정 수행:
    - PDF/이미지: 원본 파일과 대조하여 교정
    - 일반 문서: 텍스트 문맥/서식 교정

    Args:
        html_content: 변환된 HTML
        original_file_path: 원본 파일 경로
        api_key: Gemini API 키 (None이면 자동 감지)

    Returns:
        교정된 HTML (실패 시 원본 반환)
    """
    if not HAS_GENAI:
        _emit_log("[Gemini 교정] google-genai 패키지 미설치, 교정 건너뜀", "warning")
        return html_content

    # API 키 확인
    key = api_key or get_gemini_api_key()
    if not key:
        _emit_log("[Gemini 교정] Gemini API 키 미설정, 교정 건너뜀", "warning")
        return html_content

    try:
        corrector = GeminiCorrector(api_key=key)
        return corrector.correct_html(html_content, original_file_path)
    except Exception as e:
        _emit_log(f"[Gemini 교정] 초기화 실패: {str(e)}", "warning")
        return html_content
