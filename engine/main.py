#!/usr/bin/env python3
"""
LawPro Fast Converter - Main Engine
===================================
고성능 병렬 문서 변환 엔진

Features:
- CPU 코어 기반 최적화된 병렬 처리
- 실시간 진행 상황 JSON 출력 (Electron IPC 통신)
- 하이브리드 라우팅 (로컬/Upstage API)
"""

import os
import sys
import json
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
from processor import FileProcessor

# 병렬 처리 설정
# - 로컬 변환 (DOCX, HWPX 등): CPU 코어 수 기반
# - API 변환 (이미지 PDF): Upstage 권장사항 - 동시 요청 금지, 순차 처리만
MAX_WORKERS_LOCAL = min(8, (os.cpu_count() or 4))
MAX_WORKERS_API = 1  # Upstage: "send images one at a time in series" (동시 요청 시 429 에러)

# 지원 파일 확장자
SUPPORTED_EXTENSIONS = (
    '.hwpx', '.hwp',      # 한글
    '.docx', '.doc',      # Word
    '.xlsx', '.xls',      # Excel
    '.pptx', '.ppt',      # PowerPoint
    '.pdf',               # PDF (디지털/이미지)
    '.jpg', '.jpeg',      # 이미지 파일
    '.png', '.bmp',
    '.tiff', '.tif',
    '.gif', '.webp'
)


def emit_message(msg_type: str, **kwargs):
    """Electron으로 JSON 메시지 전송"""
    message = {"type": msg_type, **kwargs}
    print(json.dumps(message, ensure_ascii=False), flush=True)


def collect_files(input_folder: str) -> List[str]:
    """변환 대상 파일 수집"""
    tasks = []
    for root, dirs, files in os.walk(input_folder):
        # 출력 폴더 제외
        excluded = ('Converted_HTML', 'Final_Reviewed', 'Final_Reviewed_Gemini', 'Final_Reviewed_OpenAI', 'Archive')
        dirs[:] = [d for d in dirs if d not in excluded]

        for file in files:
            if file.lower().endswith(SUPPORTED_EXTENSIONS):
                # 숨김 파일 제외
                if not file.startswith('.'):
                    tasks.append(os.path.join(root, file))

    return tasks


def main():
    """
    메인 실행 함수

    인자:
        [1] input_folder: 변환할 문서가 있는 폴더 경로
        [2] upstage_key: Upstage API 키 (선택)
        [3] generate_clean: Clean HTML 생성 여부 (true/false, 기본: true)
        [4] generate_markdown: 마크다운 생성 여부 (true/false, 기본: true)
        [5] gemini_api_key: Gemini API 키 (Upstage 변환 후 자동 교정용, 선택)
        [6] enable_gemini_correction: Gemini 교정 활성화 여부 (true/false, 기본: true)
    """
    try:
        # 인자 파싱
        if len(sys.argv) < 2:
            emit_message("error", msg="폴더 경로가 필요합니다")
            return 1

        input_folder = sys.argv[1]
        upstage_key = sys.argv[2] if len(sys.argv) > 2 else ""

        # 출력 옵션 (기본값: 모두 생성)
        generate_clean = sys.argv[3].lower() != 'false' if len(sys.argv) > 3 else True
        generate_markdown = sys.argv[4].lower() != 'false' if len(sys.argv) > 4 else True

        # Gemini 교정 옵션
        gemini_api_key = sys.argv[5] if len(sys.argv) > 5 else os.environ.get('GEMINI_API_KEY', '')
        enable_gemini_correction = sys.argv[6].lower() != 'false' if len(sys.argv) > 6 else True

        # 입력 폴더 검증
        if not os.path.isdir(input_folder):
            emit_message("error", msg=f"폴더를 찾을 수 없습니다: {input_folder}")
            return 1

        # 출력 폴더 생성
        output_folder = os.path.join(input_folder, "Converted_HTML")
        os.makedirs(output_folder, exist_ok=True)

        # 프로세서 초기화
        processor = FileProcessor(
            api_key=upstage_key,
            output_folder=output_folder,
            generate_clean_html=generate_clean,
            generate_markdown=generate_markdown,
            gemini_api_key=gemini_api_key,
            enable_gemini_correction=enable_gemini_correction
        )

        # Gemini 교정 상태 로그
        if enable_gemini_correction and gemini_api_key:
            emit_message("log", msg="Gemini 3.0 Flash 자동 교정: 활성화 (모든 문서 변환 시 적용)")
        else:
            if not gemini_api_key:
                emit_message("log", msg="Gemini 3.0 Flash 자동 교정: 비활성화 (API 키 미설정)")
            elif not enable_gemini_correction:
                emit_message("log", msg="Gemini 3.0 Flash 자동 교정: 비활성화 (사용자 설정)")

        # 파일 수집
        tasks = collect_files(input_folder)

        if not tasks:
            emit_message("warning", msg="변환할 파일이 없습니다")
            return 0

        # 워커 수 결정 (이미지 PDF/이미지 파일이 있으면 API 제한 적용)
        api_extensions = ('.pdf', '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif', '.webp')
        has_api_files = any(f.lower().endswith(api_extensions) for f in tasks)
        workers = MAX_WORKERS_API if has_api_files else MAX_WORKERS_LOCAL

        # 초기화 메시지
        emit_message("init",
            total=len(tasks),
            workers=workers,
            output_folder=output_folder
        )

        # 통계
        stats = {
            "success": 0,
            "fail": 0,
            "total_time": 0,
            "by_method": {"local": 0, "upstage": 0, "local_gemini": 0, "upstage_gemini": 0}
        }

        start_time = time.time()

        # 병렬 처리 실행
        with ThreadPoolExecutor(max_workers=workers) as executor:
            # 작업 제출
            future_to_file = {
                executor.submit(processor.process, filepath): filepath
                for filepath in tasks
            }

            # 결과 수집
            for future in as_completed(future_to_file):
                filepath = future_to_file[future]
                try:
                    result = future.result()
                    emit_message("progress", **result)

                    if result.get("status") == "success":
                        stats["success"] += 1
                        method = result.get("method", "local").lower()
                        if "gemini" in method and "upstage" in method:
                            stats["by_method"]["upstage_gemini"] += 1
                        elif "gemini" in method:
                            stats["by_method"]["local_gemini"] += 1
                        elif "upstage" in method:
                            stats["by_method"]["upstage"] += 1
                        else:
                            stats["by_method"]["local"] += 1
                        stats["total_time"] += result.get("time", 0)
                    else:
                        stats["fail"] += 1

                except Exception as e:
                    stats["fail"] += 1
                    emit_message("progress",
                        status="fail",
                        file=os.path.basename(filepath),
                        error=str(e)
                    )

        # 완료 메시지
        total_elapsed = round(time.time() - start_time, 2)
        emit_message("complete",
            success=stats["success"],
            fail=stats["fail"],
            total_time=total_elapsed,
            avg_time=round(stats["total_time"] / max(stats["success"], 1), 2),
            by_method=stats["by_method"],
            output_folder=output_folder
        )

        return 0 if stats["fail"] == 0 else 1

    except Exception as e:
        emit_message("error", msg=str(e), trace=traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
