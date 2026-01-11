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

# 병렬 처리 최적화: CPU 코어 수의 2배 (I/O 바운드 작업에 최적)
MAX_WORKERS = min(32, (os.cpu_count() or 4) * 2)

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


def collect_files(input_folder: str) -> List[str]:
    """변환 대상 파일 수집"""
    tasks = []
    for root, dirs, files in os.walk(input_folder):
        # 출력 폴더 제외
        dirs[:] = [d for d in dirs if d not in ('Converted_HTML', 'Final_Reviewed', 'Final_Reviewed_Gemini')]

        for file in files:
            if file.lower().endswith(SUPPORTED_EXTENSIONS):
                # 숨김 파일 제외
                if not file.startswith('.'):
                    tasks.append(os.path.join(root, file))

    return tasks


def main():
    """메인 실행 함수"""
    try:
        # 인자 파싱
        if len(sys.argv) < 2:
            emit_message("error", msg="폴더 경로가 필요합니다")
            return 1

        input_folder = sys.argv[1]
        upstage_key = sys.argv[2] if len(sys.argv) > 2 else ""

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
            output_folder=output_folder
        )

        # 파일 수집
        tasks = collect_files(input_folder)

        if not tasks:
            emit_message("warning", msg="변환할 파일이 없습니다")
            return 0

        # 초기화 메시지
        emit_message("init",
            total=len(tasks),
            workers=MAX_WORKERS,
            output_folder=output_folder
        )

        # 통계
        stats = {
            "success": 0,
            "fail": 0,
            "total_time": 0,
            "by_method": {"local": 0, "upstage": 0}
        }

        start_time = time.time()

        # 병렬 처리 실행
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
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
                        if "upstage" in method:
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
