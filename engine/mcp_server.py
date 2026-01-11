#!/usr/bin/env python3
"""
LawPro Fast Converter - MCP Server
===================================
Claude Desktop과 연결하여 문서 검수를 수행하는 MCP 서버

Features:
- 변환된 HTML 문서 목록 조회
- 문서 내용 읽기
- 검수 완료된 문서 저장
- OCR 오류 통계 분석
"""

import os
import sys
import json
import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

# MCP 임포트
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("Error: mcp[cli] 패키지가 설치되어 있지 않습니다.", file=sys.stderr)
    print("pip install 'mcp[cli]' 로 설치해주세요.", file=sys.stderr)
    sys.exit(1)


# ============================================================
# 설정
# ============================================================
APP_NAME = "LawPro Converter"

# 기본 작업 디렉토리 (환경 변수로 오버라이드 가능)
BASE_DIR = os.environ.get(
    "LAWPRO_OUTPUT_DIR",
    os.path.join(os.path.expanduser("~"), "Documents", "LawPro_Output")
)

INPUT_DIR = os.path.join(BASE_DIR, "Converted_HTML")
REVIEW_DIR = os.path.join(BASE_DIR, "Final_Reviewed")
STATS_FILE = os.path.join(BASE_DIR, "review_stats.json")

# 디렉토리 생성
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(REVIEW_DIR, exist_ok=True)

# MCP 서버 초기화
mcp = FastMCP(APP_NAME)


# ============================================================
# OCR 오류 패턴 (학습 데이터 기반)
# ============================================================
OCR_ERROR_PATTERNS = {
    # 한글 유사 문자 오인식
    "을": ["Z", "z", "2", "ㅡ"],
    "를": ["Z", "z", "2"],
    "은": ["E", "e", "ㅡ"],
    "의": ["9", "Q", "q"],
    "이": ["0", "O", "o", "l", "1"],
    "가": ["7", "71", "7l"],
    "에": ["M", "m"],
    "로": ["P", "p"],
    "하": ["8", "아"],
    "다": ["cl", "c1"],
    "와": ["9", "q"],
    "한": ["8"],
    "것": ["갓", "겄"],
    "수": ["子", "于"],

    # 숫자-문자 혼동
    "0": ["O", "o", "Q"],
    "1": ["l", "I", "|", "!"],
    "2": ["Z", "z"],
    "5": ["S", "s"],
    "6": ["G", "b"],
    "8": ["B", "&"],

    # 법률 용어 특수 패턴
    "조": ["초", "소"],
    "항": ["향", "왕"],
    "호": ["효", "후"],
    "법": ["벌", "범"],
    "제": ["게", "재"],
    "원": ["웬", "윈"],
    "권": ["컨", "권"],
    "자": ["차", "사"],
}


# ============================================================
# 도구 함수
# ============================================================
@mcp.tool()
def list_documents(status: str = "pending") -> str:
    """
    검수 대기 중인 HTML 문서 목록을 반환합니다.

    Args:
        status: "pending" (검수 대기), "reviewed" (검수 완료), "all" (전체)

    Returns:
        문서 목록 JSON
    """
    try:
        result = {"pending": [], "reviewed": [], "total": 0}

        # 변환된 문서 (검수 대기)
        if os.path.exists(INPUT_DIR):
            for f in os.listdir(INPUT_DIR):
                if f.endswith('.html'):
                    filepath = os.path.join(INPUT_DIR, f)
                    stat = os.stat(filepath)
                    result["pending"].append({
                        "filename": f,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })

        # 검수 완료 문서
        if os.path.exists(REVIEW_DIR):
            for f in os.listdir(REVIEW_DIR):
                if f.endswith('.html'):
                    filepath = os.path.join(REVIEW_DIR, f)
                    stat = os.stat(filepath)
                    result["reviewed"].append({
                        "filename": f,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })

        result["total"] = len(result["pending"]) + len(result["reviewed"])

        # 상태별 필터링
        if status == "pending":
            return json.dumps({"documents": result["pending"], "count": len(result["pending"])}, ensure_ascii=False, indent=2)
        elif status == "reviewed":
            return json.dumps({"documents": result["reviewed"], "count": len(result["reviewed"])}, ensure_ascii=False, indent=2)
        else:
            return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def read_document(filename: str) -> str:
    """
    HTML 문서의 내용을 읽습니다.

    Args:
        filename: 읽을 파일명 (예: "계약서.pdf.html")

    Returns:
        문서 HTML 내용
    """
    try:
        # 먼저 검수 대기 폴더에서 찾기
        filepath = os.path.join(INPUT_DIR, filename)

        if not os.path.exists(filepath):
            # 검수 완료 폴더에서 찾기
            filepath = os.path.join(REVIEW_DIR, filename)

        if not os.path.exists(filepath):
            return f"Error: 파일을 찾을 수 없습니다 - {filename}"

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        return content

    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
def analyze_ocr_errors(filename: str) -> str:
    """
    문서의 잠재적 OCR 오류를 분석합니다.

    Args:
        filename: 분석할 파일명

    Returns:
        발견된 잠재적 오류 목록
    """
    try:
        filepath = os.path.join(INPUT_DIR, filename)
        if not os.path.exists(filepath):
            return json.dumps({"error": "파일을 찾을 수 없습니다"}, ensure_ascii=False)

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # HTML 태그 제거하고 텍스트만 추출
        text = re.sub(r'<[^>]+>', ' ', content)

        potential_errors = []

        # 패턴 매칭
        for correct, wrong_list in OCR_ERROR_PATTERNS.items():
            for wrong in wrong_list:
                # 단어 경계 내 오류 패턴 찾기
                pattern = re.compile(rf'([가-힣])({re.escape(wrong)})([가-힣])')
                matches = pattern.findall(text)

                for match in matches:
                    context = ''.join(match)
                    potential_errors.append({
                        "found": wrong,
                        "expected": correct,
                        "context": context,
                        "suggestion": match[0] + correct + match[2]
                    })

        # 중복 제거
        unique_errors = []
        seen = set()
        for err in potential_errors:
            key = (err["found"], err["context"])
            if key not in seen:
                seen.add(key)
                unique_errors.append(err)

        return json.dumps({
            "filename": filename,
            "potential_errors": unique_errors[:50],  # 최대 50개
            "total_found": len(unique_errors)
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def save_reviewed_document(filename: str, content: str) -> str:
    """
    검수 완료된 문서를 저장합니다.

    Args:
        filename: 저장할 파일명
        content: 수정된 HTML 내용

    Returns:
        저장 결과 메시지
    """
    try:
        # 저장 경로
        save_path = os.path.join(REVIEW_DIR, filename)

        # 백업 (기존 파일이 있으면)
        if os.path.exists(save_path):
            backup_path = save_path + f".backup.{int(datetime.now().timestamp())}"
            os.rename(save_path, backup_path)

        # 저장
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # 원본 파일 삭제 또는 이동
        original_path = os.path.join(INPUT_DIR, filename)
        if os.path.exists(original_path):
            archive_dir = os.path.join(BASE_DIR, "Archive")
            os.makedirs(archive_dir, exist_ok=True)
            archive_path = os.path.join(archive_dir, filename)
            os.rename(original_path, archive_path)

        # 통계 업데이트
        _update_stats(filename, content)

        return json.dumps({
            "success": True,
            "saved_to": save_path,
            "message": f"검수 완료: {filename}"
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


@mcp.tool()
def batch_review_with_prompt() -> str:
    """
    배치 검수를 위한 시스템 프롬프트와 작업 지침을 반환합니다.

    Returns:
        검수 작업용 프롬프트
    """
    prompt = """
# LawPro 문서 검수 작업 가이드

## 당신의 역할
당신은 법률 문서 OCR 검수 전문가입니다. 변환된 HTML 문서에서 OCR 오류를 찾아 수정합니다.

## 주요 OCR 오류 패턴

### 1. 한글-영문 혼동 (가장 흔함)
- "을" → "Z" 또는 "z" (예: "계약Z 체결" → "계약을 체결")
- "를" → "Z" (예: "권리Z" → "권리를")
- "은" → "E" (예: "것E" → "것은")
- "이" → "0", "O", "l", "1" (예: "권l" → "권이")

### 2. 숫자-문자 혼동
- "0" ↔ "O", "o"
- "1" ↔ "l", "I", "|"
- "2" ↔ "Z"
- "5" ↔ "S"

### 3. 법률 용어 특수 오류
- "제1조" → "게1초", "게1조"
- "제2항" → "게2향"
- "법률" → "벌률"
- "권리" → "컨리"

## 검수 절차

1. `list_documents(status="pending")`로 검수 대기 문서 확인
2. `read_document(filename)`로 문서 내용 읽기
3. `analyze_ocr_errors(filename)`로 잠재 오류 분석
4. 오류 수정 후 `save_reviewed_document(filename, content)`로 저장

## 주의사항

- HTML 태그는 절대 수정하지 마세요
- 의미가 명확하지 않은 경우 원문 유지
- 법률 용어는 특히 신중하게 검토
- 고유명사(회사명, 인명)는 수정하지 않음

## 작업 시작

1. 먼저 검수 대기 문서 목록을 확인하세요
2. 각 문서를 순서대로 검수합니다
3. 모든 문서 검수가 완료되면 알려주세요
"""
    return prompt


@mcp.tool()
def get_review_stats() -> str:
    """
    검수 통계를 조회합니다.

    Returns:
        검수 통계 JSON
    """
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                stats = json.load(f)
        else:
            stats = {
                "total_reviewed": 0,
                "total_corrections": 0,
                "common_errors": {},
                "last_updated": None
            }

        # 현재 상태 추가
        pending_count = len([f for f in os.listdir(INPUT_DIR) if f.endswith('.html')]) if os.path.exists(INPUT_DIR) else 0
        reviewed_count = len([f for f in os.listdir(REVIEW_DIR) if f.endswith('.html')]) if os.path.exists(REVIEW_DIR) else 0

        stats["current_pending"] = pending_count
        stats["current_reviewed"] = reviewed_count

        return json.dumps(stats, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def set_working_directory(path: str) -> str:
    """
    작업 디렉토리를 설정합니다.

    Args:
        path: 새로운 작업 디렉토리 경로

    Returns:
        설정 결과
    """
    global BASE_DIR, INPUT_DIR, REVIEW_DIR, STATS_FILE

    try:
        if not os.path.exists(path):
            return json.dumps({"error": f"경로가 존재하지 않습니다: {path}"}, ensure_ascii=False)

        # Converted_HTML 폴더 확인
        converted_dir = os.path.join(path, "Converted_HTML")
        if not os.path.exists(converted_dir):
            return json.dumps({"error": f"Converted_HTML 폴더가 없습니다: {path}"}, ensure_ascii=False)

        # 경로 업데이트
        BASE_DIR = path
        INPUT_DIR = converted_dir
        REVIEW_DIR = os.path.join(path, "Final_Reviewed")
        STATS_FILE = os.path.join(path, "review_stats.json")

        os.makedirs(REVIEW_DIR, exist_ok=True)

        return json.dumps({
            "success": True,
            "base_dir": BASE_DIR,
            "input_dir": INPUT_DIR,
            "review_dir": REVIEW_DIR
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ============================================================
# 내부 헬퍼 함수
# ============================================================
def _update_stats(filename: str, content: str):
    """검수 통계 업데이트"""
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                stats = json.load(f)
        else:
            stats = {
                "total_reviewed": 0,
                "total_corrections": 0,
                "common_errors": {},
                "reviews": []
            }

        stats["total_reviewed"] += 1
        stats["last_updated"] = datetime.now().isoformat()
        stats["reviews"].append({
            "filename": filename,
            "reviewed_at": datetime.now().isoformat()
        })

        # 최근 100개만 유지
        stats["reviews"] = stats["reviews"][-100:]

        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

    except Exception:
        pass  # 통계 실패는 무시


# ============================================================
# 리소스 (프롬프트 템플릿)
# ============================================================
@mcp.resource("prompts://review-system")
def get_review_system_prompt() -> str:
    """검수 시스템 프롬프트"""
    return """당신은 LawPro 문서 검수 AI입니다.

주요 임무:
1. OCR 변환된 법률 문서의 오류를 찾아 수정합니다.
2. 한글-영문 혼동, 숫자-문자 혼동을 집중적으로 확인합니다.
3. HTML 구조는 유지하면서 텍스트만 수정합니다.

사용 가능한 도구:
- list_documents: 검수 대기 문서 목록 조회
- read_document: 문서 내용 읽기
- analyze_ocr_errors: 잠재적 OCR 오류 분석
- save_reviewed_document: 검수 완료 문서 저장
- get_review_stats: 검수 통계 조회

작업을 시작하려면 'list_documents()'를 호출하세요."""


@mcp.resource("prompts://error-patterns")
def get_error_patterns() -> str:
    """오류 패턴 목록"""
    return json.dumps(OCR_ERROR_PATTERNS, ensure_ascii=False, indent=2)


# ============================================================
# 메인 실행
# ============================================================
if __name__ == "__main__":
    print(f"LawPro MCP Server starting...", file=sys.stderr)
    print(f"Base Directory: {BASE_DIR}", file=sys.stderr)
    print(f"Input Directory: {INPUT_DIR}", file=sys.stderr)
    print(f"Review Directory: {REVIEW_DIR}", file=sys.stderr)
    mcp.run()
