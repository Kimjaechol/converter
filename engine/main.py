#!/usr/bin/env python3
"""
LawPro Fast Converter - Main Engine (Pipeline Architecture)
============================================================
고성능 파이프라인 문서 변환 엔진

Architecture:
- API 호출 (Upstage): 순차 처리 (Rate Limit 준수)
- 로컬 변환 (DOCX, HWPX 등): 병렬 처리
- 후처리 (Clean HTML, Markdown): 병렬 처리

Pipeline Flow:
1. 파일 분류 → PDF(API) / 로컬 파일
2. 로컬 파일: 즉시 병렬 처리
3. PDF 파일: API 순차 호출 → 후처리 병렬 처리
"""

import os
import sys
import json
import time
import traceback
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Tuple
from processor import FileProcessor

# 병렬 처리 설정
MAX_WORKERS_LOCAL = min(8, (os.cpu_count() or 4))  # 로컬 변환 워커
MAX_WORKERS_POSTPROCESS = min(4, (os.cpu_count() or 2))  # 후처리 워커

# 지원 파일 확장자
SUPPORTED_EXTENSIONS = (
    '.hwpx', '.hwp',      # 한글
    '.docx', '.doc',      # Word
    '.xlsx', '.xls',      # Excel
    '.pptx', '.ppt',      # PowerPoint
    '.pdf'                # PDF (디지털/이미지)
)


def emit_message(msg_type: str, **kwargs):
    """Electron으로 JSON 메시지 전송"""
    message = {"type": msg_type, **kwargs}
    print(json.dumps(message, ensure_ascii=False), flush=True)


def collect_files(input_folder: str) -> Tuple[List[str], List[str]]:
    """
    변환 대상 파일 수집 및 분류

    Returns:
        (pdf_files, local_files): PDF 파일과 로컬 처리 파일 분리
    """
    pdf_files = []
    local_files = []

    for root, dirs, files in os.walk(input_folder):
        # 출력 폴더 제외
        excluded = ('Converted_HTML', 'Final_Reviewed', 'Final_Reviewed_Gemini', 'Final_Reviewed_OpenAI', 'Archive')
        dirs[:] = [d for d in dirs if d not in excluded]

        for file in files:
            if file.lower().endswith(SUPPORTED_EXTENSIONS):
                # 숨김 파일 제외
                if not file.startswith('.'):
                    filepath = os.path.join(root, file)
                    if file.lower().endswith('.pdf'):
                        pdf_files.append(filepath)
                    else:
                        local_files.append(filepath)

    return pdf_files, local_files


def process_local_files(processor: FileProcessor, local_files: List[str],
                       stats: Dict, stats_lock: threading.Lock) -> List[Dict]:
    """로컬 파일 병렬 처리"""
    results = []

    if not local_files:
        return results

    with ThreadPoolExecutor(max_workers=MAX_WORKERS_LOCAL) as executor:
        future_to_file = {
            executor.submit(processor.process, filepath): filepath
            for filepath in local_files
        }

        for future in as_completed(future_to_file):
            filepath = future_to_file[future]
            try:
                result = future.result()
                emit_message("progress", **result)

                with stats_lock:
                    if result.get("status") == "success":
                        stats["success"] += 1
                        stats["by_method"]["local"] += 1
                        stats["total_time"] += result.get("time", 0)
                    else:
                        stats["fail"] += 1

                results.append(result)

            except Exception as e:
                with stats_lock:
                    stats["fail"] += 1
                emit_message("progress",
                    status="fail",
                    file=os.path.basename(filepath),
                    error=str(e)
                )
                results.append({"status": "fail", "file": os.path.basename(filepath), "error": str(e)})

    return results


def process_pdf_files_pipeline(processor: FileProcessor, pdf_files: List[str],
                               stats: Dict, stats_lock: threading.Lock) -> List[Dict]:
    """
    PDF 파일 파이프라인 처리

    - API 호출: 순차 (Rate Limit 준수)
    - 후처리 (이미 processor.process 내부에서 수행): 순차

    Note: Upstage API는 한 번에 한 파일만 처리해야 하므로
    파일 단위로는 순차 처리하지만, 내부적으로 최적화됨
    """
    results = []

    if not pdf_files:
        return results

    for filepath in pdf_files:
        try:
            # PDF 처리 (API 호출 + 후처리)
            result = processor.process(filepath)
            emit_message("progress", **result)

            with stats_lock:
                if result.get("status") == "success":
                    stats["success"] += 1
                    method = result.get("method", "local").lower()
                    if "upstage" in method:
                        stats["by_method"]["upstage"] += 1
                    else:
                        stats["by_method"]["local"] += 1
                    stats["total_time"] += result.get("time", 0)
                else:
                    stats["fail"] += 1

            results.append(result)

        except Exception as e:
            with stats_lock:
                stats["fail"] += 1
            emit_message("progress",
                status="fail",
                file=os.path.basename(filepath),
                error=str(e)
            )
            results.append({"status": "fail", "file": os.path.basename(filepath), "error": str(e)})

    return results


def main():
    """
    메인 실행 함수 (파이프라인 아키텍처)

    인자:
        [1] input_folder: 변환할 문서가 있는 폴더 경로
        [2] upstage_key: Upstage API 키 (선택)
        [3] generate_clean: Clean HTML 생성 여부 (true/false, 기본: true)
        [4] generate_markdown: 마크다운 생성 여부 (true/false, 기본: true)
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
            generate_markdown=generate_markdown
        )

        # 파일 수집 및 분류
        pdf_files, local_files = collect_files(input_folder)
        total_files = len(pdf_files) + len(local_files)

        if total_files == 0:
            emit_message("warning", msg="변환할 파일이 없습니다")
            return 0

        # 초기화 메시지
        emit_message("init",
            total=total_files,
            pdf_count=len(pdf_files),
            local_count=len(local_files),
            workers_local=MAX_WORKERS_LOCAL,
            output_folder=output_folder
        )

        # 통계 (스레드 안전)
        stats = {
            "success": 0,
            "fail": 0,
            "total_time": 0,
            "by_method": {"local": 0, "upstage": 0}
        }
        stats_lock = threading.Lock()

        start_time = time.time()

        # === 파이프라인 실행 ===
        # 로컬 파일과 PDF 파일을 동시에 처리
        # - 로컬 파일: 별도 스레드에서 병렬 처리
        # - PDF 파일: 메인 흐름에서 순차 처리 (API Rate Limit)

        local_thread = None
        local_results = []

        # 로컬 파일이 있으면 별도 스레드에서 병렬 처리 시작
        if local_files:
            def process_local():
                nonlocal local_results
                local_results = process_local_files(processor, local_files, stats, stats_lock)

            local_thread = threading.Thread(target=process_local, daemon=True)
            local_thread.start()

        # PDF 파일 순차 처리 (API Rate Limit 준수)
        pdf_results = process_pdf_files_pipeline(processor, pdf_files, stats, stats_lock)

        # 로컬 파일 처리 완료 대기
        if local_thread:
            local_thread.join()

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
