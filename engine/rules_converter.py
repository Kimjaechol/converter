#!/usr/bin/env python3
"""
검수 규칙 변환기
================
Excel/CSV 파일을 JSON 형식으로 변환하여 AI 검수에 사용합니다.

사용법:
    python rules_converter.py                    # 기본 파일 변환
    python rules_converter.py custom_rules.xlsx  # 지정 파일 변환
"""

import os
import json
import sys
from pathlib import Path
from datetime import datetime

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


class RulesConverter:
    """Excel/CSV → JSON 변환기"""

    def __init__(self):
        self.rules_dir = Path(__file__).parent
        self.default_excel = self.rules_dir / "review_rules.xlsx"
        self.default_csv = self.rules_dir / "review_rules.csv"
        self.output_json = self.rules_dir / "review_rules.json"

    def convert_excel_to_json(self, excel_path: str = None) -> dict:
        """
        Excel 파일을 JSON으로 변환

        Excel 파일 구조:
        - Sheet1 '오류규칙': 카테고리, 유형, 오류예시, 검수방법, 중요도
        - Sheet2 '자주틀리는단어': 정확한표현, 오류1, 오류2, 오류3, 분류
        - Sheet3 '시스템설정': 설정키, 설정값
        """
        if not HAS_PANDAS:
            raise ImportError("pandas가 필요합니다: pip install pandas openpyxl")

        excel_path = excel_path or str(self.default_excel)

        if not os.path.exists(excel_path):
            print(f"Excel 파일이 없습니다: {excel_path}")
            print("기본 템플릿을 생성합니다...")
            self.create_excel_template(excel_path)
            return self.load_existing_json()

        print(f"Excel 파일 변환 중: {excel_path}")

        result = {
            "_설명": "Excel에서 자동 변환된 검수 규칙입니다.",
            "_버전": "1.0.0",
            "_수정일": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "_원본파일": os.path.basename(excel_path)
        }

        try:
            # 시트별로 읽기
            xl = pd.ExcelFile(excel_path)

            # 오류 규칙 시트
            if '오류규칙' in xl.sheet_names:
                df = pd.read_excel(xl, sheet_name='오류규칙')
                result['오류_카테고리'] = self._parse_error_rules(df)

            # 자주 틀리는 단어 시트
            if '자주틀리는단어' in xl.sheet_names:
                df = pd.read_excel(xl, sheet_name='자주틀리는단어')
                result['자주_틀리는_단어'] = self._parse_common_errors(df)

            # 시스템 설정 시트
            if '시스템설정' in xl.sheet_names:
                df = pd.read_excel(xl, sheet_name='시스템설정')
                result['시스템_지시'] = self._parse_system_settings(df)

            # 프롬프트 템플릿 시트
            if '프롬프트' in xl.sheet_names:
                df = pd.read_excel(xl, sheet_name='프롬프트')
                result['검수_프롬프트_템플릿'] = self._parse_prompts(df)

        except Exception as e:
            print(f"Excel 파싱 오류: {e}")
            return self.load_existing_json()

        # JSON 저장
        self._save_json(result)
        return result

    def convert_csv_to_json(self, csv_path: str = None) -> dict:
        """CSV 파일을 JSON으로 변환 (간단한 형식)"""
        if not HAS_PANDAS:
            raise ImportError("pandas가 필요합니다: pip install pandas")

        csv_path = csv_path or str(self.default_csv)

        if not os.path.exists(csv_path):
            print(f"CSV 파일이 없습니다: {csv_path}")
            return self.load_existing_json()

        print(f"CSV 파일 변환 중: {csv_path}")

        df = pd.read_csv(csv_path, encoding='utf-8-sig')
        result = {
            "_설명": "CSV에서 자동 변환된 검수 규칙입니다.",
            "_버전": "1.0.0",
            "_수정일": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "오류_카테고리": self._parse_error_rules(df)
        }

        self._save_json(result)
        return result

    def _parse_error_rules(self, df: 'pd.DataFrame') -> dict:
        """오류 규칙 파싱"""
        categories = {}

        for _, row in df.iterrows():
            category = str(row.get('카테고리', '')).strip()
            if not category or category == 'nan':
                continue

            if category not in categories:
                categories[category] = {
                    "설명": str(row.get('카테고리설명', category)),
                    "중요도": str(row.get('중요도', '중간')),
                    "규칙": []
                }

            rule = {
                "유형": str(row.get('유형', '')),
                "오류_예시": self._split_examples(row.get('오류예시', '')),
                "검수_방법": str(row.get('검수방법', ''))
            }

            # 정확한 표현이 있으면 추가
            if pd.notna(row.get('정확한표현')):
                rule["정확한_표현"] = self._split_examples(row.get('정확한표현', ''))

            categories[category]["규칙"].append(rule)

        return categories

    def _parse_common_errors(self, df: 'pd.DataFrame') -> dict:
        """자주 틀리는 단어 파싱"""
        result = {}

        for _, row in df.iterrows():
            category = str(row.get('분류', '일반')).strip()
            word = str(row.get('정확한표현', '')).strip()

            if not word or word == 'nan':
                continue

            if category not in result:
                result[category] = {}

            # 오류 예시들 수집
            errors = []
            for col in ['오류1', '오류2', '오류3', '오류4', '오류5']:
                if col in row and pd.notna(row[col]):
                    errors.append(str(row[col]).strip())

            if errors:
                result[category][word] = errors

        return result

    def _parse_system_settings(self, df: 'pd.DataFrame') -> dict:
        """시스템 설정 파싱"""
        settings = {"역할": "", "원칙": [], "출력_형식": ""}

        for _, row in df.iterrows():
            key = str(row.get('설정키', '')).strip()
            value = str(row.get('설정값', '')).strip()

            if key == '역할':
                settings['역할'] = value
            elif key == '원칙':
                settings['원칙'].append(value)
            elif key == '출력형식':
                settings['출력_형식'] = value

        return settings

    def _parse_prompts(self, df: 'pd.DataFrame') -> dict:
        """프롬프트 템플릿 파싱"""
        prompts = {}

        for _, row in df.iterrows():
            name = str(row.get('템플릿명', '')).strip()
            content = str(row.get('내용', '')).strip()

            if name and content and name != 'nan':
                prompts[name] = content

        return prompts

    def _split_examples(self, text) -> list:
        """예시 텍스트를 리스트로 분리"""
        if pd.isna(text):
            return []
        text = str(text)
        # 쉼표, 세미콜론, 줄바꿈으로 분리
        for sep in [',', ';', '\n', '/', '|']:
            if sep in text:
                return [x.strip() for x in text.split(sep) if x.strip()]
        return [text.strip()] if text.strip() else []

    def _save_json(self, data: dict):
        """JSON 파일 저장"""
        with open(self.output_json, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"JSON 저장 완료: {self.output_json}")

    def load_existing_json(self) -> dict:
        """기존 JSON 파일 로드"""
        if self.output_json.exists():
            with open(self.output_json, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def create_excel_template(self, output_path: str = None):
        """빈 Excel 템플릿 생성"""
        if not HAS_PANDAS:
            raise ImportError("pandas가 필요합니다: pip install pandas openpyxl")

        output_path = output_path or str(self.default_excel)

        # 오류규칙 시트
        rules_data = {
            '카테고리': ['1_글자_오인식', '1_글자_오인식', '2_띄어쓰기_오류', '3_누락_오류', '5_법률_용어_오류'],
            '카테고리설명': ['OCR이 비슷한 글자를 잘못 인식', '', '띄어쓰기가 잘못된 경우', '글자/단어/문장 누락', '법률 전문용어 오류'],
            '중요도': ['높음', '높음', '중간', '높음', '매우높음'],
            '유형': ['한글 유사 글자', '숫자-문자 혼동', '붙여야 할 것을 띄어씀', '글자 누락', '소송 당사자'],
            '오류예시': ['ㄱ↔ㅋ, ㄷ↔ㅌ, ㅂ↔ㅍ', '0↔O, 1↔l↔I, 5↔S', '원 고→원고, 피 고→피고', '원고→원, 피고인→피인', '원고/피고 표기 오류'],
            '검수방법': ['문맥상 어색한 단어 확인', '숫자/문자 위치 확인', '법률용어는 붙여쓰기', '불완전한 단어 확인', '당사자 표시 일관성 확인'],
            '정확한표현': ['', '', '', '', '원고, 피고, 항소인, 피항소인']
        }
        df_rules = pd.DataFrame(rules_data)

        # 자주틀리는단어 시트
        words_data = {
            '정확한표현': ['원고', '피고', '판결', '청구', '따라서', '그러나'],
            '오류1': ['월고', '피ㄱ', '판겸', '청ㄱ', '따랴서', '그라나'],
            '오류2': ['원ㄱ', '피거', '판견', '청규', '따라셔', '그러니'],
            '오류3': ['원ㅗ', '피ㅗ', '팜결', '쳥구', '따락서', '그럼나'],
            '오류4': ['', '', '', '', '', ''],
            '오류5': ['', '', '', '', '', ''],
            '분류': ['법률용어', '법률용어', '법률용어', '법률용어', '접속사', '접속사']
        }
        df_words = pd.DataFrame(words_data)

        # 시스템설정 시트
        settings_data = {
            '설정키': ['역할', '원칙', '원칙', '원칙', '원칙', '출력형식'],
            '설정값': [
                '당신은 법률 문서 전문 교정사입니다.',
                '원본의 의미와 맥락을 최대한 보존합니다',
                '확실하지 않은 수정은 [?]로 표시합니다',
                '수정한 부분은 명확히 표시합니다',
                '법률 용어는 정확한 표현을 사용합니다',
                '수정된 HTML + 수정 내역 요약'
            ]
        }
        df_settings = pd.DataFrame(settings_data)

        # 프롬프트 시트
        prompts_data = {
            '템플릿명': ['기본', '상세'],
            '내용': [
                '다음 HTML 문서에서 OCR 오류를 찾아 수정해주세요.\n\n{문서_내용}',
                '당신은 법률 문서 전문 교정사입니다.\n\n[검수 항목]\n{검수_항목}\n\n[문서]\n{문서_내용}\n\n수정된 HTML과 수정 내역을 출력해주세요.'
            ]
        }
        df_prompts = pd.DataFrame(prompts_data)

        # Excel 파일로 저장
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df_rules.to_excel(writer, sheet_name='오류규칙', index=False)
            df_words.to_excel(writer, sheet_name='자주틀리는단어', index=False)
            df_settings.to_excel(writer, sheet_name='시스템설정', index=False)
            df_prompts.to_excel(writer, sheet_name='프롬프트', index=False)

        print(f"Excel 템플릿 생성 완료: {output_path}")

    def create_csv_template(self, output_path: str = None):
        """간단한 CSV 템플릿 생성"""
        if not HAS_PANDAS:
            raise ImportError("pandas가 필요합니다: pip install pandas")

        output_path = output_path or str(self.default_csv)

        data = {
            '카테고리': ['글자_오인식', '글자_오인식', '띄어쓰기_오류', '누락_오류'],
            '카테고리설명': ['OCR 글자 오인식', '', '띄어쓰기 오류', '내용 누락'],
            '중요도': ['높음', '높음', '중간', '높음'],
            '유형': ['한글 유사 글자', '숫자-문자 혼동', '법률용어 띄어쓰기', '글자 누락'],
            '오류예시': ['ㄱ↔ㅋ, ㄷ↔ㅌ', '0↔O, 1↔l', '원 고→원고', '원고→원'],
            '검수방법': ['문맥 확인', '위치 확인', '붙여쓰기', '완전성 확인']
        }
        df = pd.DataFrame(data)
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"CSV 템플릿 생성 완료: {output_path}")


def get_review_rules(include_learned: bool = True) -> dict:
    """
    검수 규칙 로드 (Excel이 있으면 변환, 없으면 JSON 사용)

    Args:
        include_learned: 학습된 패턴 포함 여부

    Returns:
        검수 규칙 dict (학습된 패턴 포함 가능)
    """
    converter = RulesConverter()

    # Excel 파일이 있고 JSON보다 최신이면 변환
    if converter.default_excel.exists():
        excel_mtime = converter.default_excel.stat().st_mtime
        json_mtime = converter.output_json.stat().st_mtime if converter.output_json.exists() else 0

        if excel_mtime > json_mtime:
            rules = converter.convert_excel_to_json()
        else:
            rules = converter.load_existing_json()
    else:
        rules = converter.load_existing_json()

    # 학습된 패턴 통합
    if include_learned:
        rules = integrate_learned_patterns(rules)

    return rules


def integrate_learned_patterns(rules: dict) -> dict:
    """
    학습된 오류 패턴을 검수 규칙에 통합

    Args:
        rules: 기존 검수 규칙

    Returns:
        학습된 패턴이 추가된 검수 규칙
    """
    try:
        from error_learning import PatternStore, PromptEnhancer, ERROR_SOURCES

        store = PatternStore()
        stats = store.get_stats()

        # 패턴이 없으면 그대로 반환
        if stats['total'] == 0:
            return rules

        enhancer = PromptEnhancer(store)
        enhanced = enhancer.enhance_review_rules(rules)

        # 통계 정보 추가
        enhanced['_학습_통계'] = {
            '총_패턴_수': stats['total'],
            '이미지_PDF_패턴': stats['by_source'].get('image_pdf', 0),
            '디지털_문서_패턴': stats['by_source'].get('digital_doc', 0),
            '최대_발생빈도': stats['top_frequency']
        }

        return enhanced

    except ImportError:
        # error_learning 모듈이 없으면 원본 반환
        return rules
    except Exception as e:
        print(f"[integrate_learned_patterns] 오류: {e}")
        return rules


def generate_review_prompt(document_content: str, rules: dict = None,
                          document_source: str = None) -> str:
    """
    검수 프롬프트 생성

    Args:
        document_content: 검수할 문서 내용
        rules: 검수 규칙 (None이면 자동 로드)
        document_source: 문서 출처 ('image_pdf' 또는 'digital_doc')

    Returns:
        생성된 프롬프트
    """
    if rules is None:
        rules = get_review_rules(include_learned=True)

    # 시스템 지시 가져오기
    system = rules.get('시스템_지시', {})
    role = system.get('역할', '당신은 문서 교정 전문가입니다.')
    principles = system.get('원칙', [])

    # 오류 카테고리 요약
    categories = rules.get('오류_카테고리', {})
    rules_summary = []
    for cat_name, cat_data in categories.items():
        if isinstance(cat_data, dict):
            rules_summary.append(f"- {cat_name}: {cat_data.get('설명', '')}")

    # 자주 틀리는 단어 추가
    common_errors = rules.get('자주_틀리는_단어', {})
    common_words = []
    for category, words in common_errors.items():
        if isinstance(words, dict):
            for correct, errors in words.items():
                if isinstance(errors, list):
                    common_words.append(f"  - {correct}: {', '.join(errors[:3])}")

    # 학습된 오류 패턴 추가
    learned_section = ""
    learned_errors = rules.get('학습된_오류', {})
    if learned_errors:
        learned_lines = []

        # 문서 출처에 맞는 패턴 우선
        if document_source == 'image_pdf' and '이미지_PDF_OCR' in learned_errors:
            ocr_patterns = learned_errors['이미지_PDF_OCR'].get('패턴', [])[:30]
            if ocr_patterns:
                learned_lines.append("\n[학습된 OCR 오류 패턴 - 이미지 PDF]")
                for p in ocr_patterns:
                    learned_lines.append(f"  - {p.get('오류', '')} → {p.get('정답', '')} (빈도: {p.get('빈도', 1)})")

        elif document_source == 'digital_doc' and '디지털_문서' in learned_errors:
            doc_patterns = learned_errors['디지털_문서'].get('패턴', [])[:30]
            if doc_patterns:
                learned_lines.append("\n[학습된 변환 오류 패턴 - 디지털 문서]")
                for p in doc_patterns:
                    learned_lines.append(f"  - {p.get('오류', '')} → {p.get('정답', '')} (빈도: {p.get('빈도', 1)})")

        else:
            # 출처 불명 시 전체 포함 (상위 20개씩)
            for source_name, source_data in learned_errors.items():
                patterns = source_data.get('패턴', [])[:20]
                if patterns:
                    learned_lines.append(f"\n[학습된 오류 패턴 - {source_name}]")
                    for p in patterns:
                        learned_lines.append(f"  - {p.get('오류', '')} → {p.get('정답', '')} (빈도: {p.get('빈도', 1)})")

        if learned_lines:
            learned_section = chr(10).join(learned_lines)

    # 프롬프트 조합
    prompt = f"""{role}

[역할 원칙]
{chr(10).join(f'- {p}' for p in principles)}

[검수 항목]
{chr(10).join(rules_summary)}

[자주 틀리는 단어 (오류→정답)]
{chr(10).join(common_words[:20])}
{learned_section}

[검수할 문서]
{document_content}

[요청]
1. 위 문서에서 오류를 찾아 수정한 HTML을 출력해주세요.
2. 마지막에 수정 내역을 표로 정리해주세요:
   | 위치 | 원본 | 수정 | 이유 |
3. 확실하지 않은 수정은 [?]로 표시해주세요.
"""
    return prompt


# CLI 실행
if __name__ == "__main__":
    converter = RulesConverter()

    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        if input_file.endswith('.xlsx') or input_file.endswith('.xls'):
            converter.convert_excel_to_json(input_file)
        elif input_file.endswith('.csv'):
            converter.convert_csv_to_json(input_file)
        elif input_file == '--create-template':
            converter.create_excel_template()
            converter.create_csv_template()
        else:
            print(f"지원하지 않는 파일 형식: {input_file}")
    else:
        # 기본 동작: Excel이 있으면 변환, 없으면 템플릿 생성
        if converter.default_excel.exists():
            converter.convert_excel_to_json()
        else:
            print("Excel 파일이 없습니다. 템플릿을 생성합니다.")
            converter.create_excel_template()
