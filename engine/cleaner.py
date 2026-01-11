#!/usr/bin/env python3
"""
LawPro Fast Converter - Content Cleaner
========================================
AI 학습용 Clean HTML 생성 및 마크다운 변환 모듈

Features:
- 불필요한 JS/CSS 제거
- 태그 속성 정리 (토큰 절약)
- 표 구조 보존 (rowspan, colspan)
- 마크다운 변환
"""

import re
from typing import Optional, List, Tuple

try:
    from bs4 import BeautifulSoup, NavigableString, Comment
except ImportError:
    raise ImportError("beautifulsoup4 패키지가 필요합니다: pip install beautifulsoup4")

try:
    from markdownify import markdownify as md, MarkdownConverter
except ImportError:
    raise ImportError("markdownify 패키지가 필요합니다: pip install markdownify")


class ContentCleaner:
    """
    HTML 콘텐츠 정제 및 마크다운 변환 클래스

    AI/RAG 학습을 위해 불필요한 요소를 제거하고
    텍스트와 구조만 남긴 Clean HTML을 생성합니다.
    """

    # 완전히 제거할 태그 목록
    REMOVE_TAGS = [
        'script', 'style', 'meta', 'link', 'noscript',
        'svg', 'iframe', 'button', 'input', 'form',
        'nav', 'footer', 'aside', 'header',
        'canvas', 'video', 'audio', 'embed', 'object'
    ]

    # 보존할 속성 목록 (표 구조 및 링크용)
    PRESERVE_ATTRS = ['rowspan', 'colspan', 'href', 'src', 'alt']

    # 의미 있는 태그 (구조 유지)
    SEMANTIC_TAGS = [
        'html', 'body', 'head', 'title',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'p', 'br', 'hr',
        'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td',
        'ul', 'ol', 'li',
        'blockquote', 'pre', 'code',
        'strong', 'b', 'em', 'i', 'u', 's',
        'a', 'img',
        'div', 'span', 'section', 'article', 'main'
    ]

    def __init__(self, preserve_images: bool = False):
        """
        Args:
            preserve_images: 이미지 태그 보존 여부 (기본: False)
        """
        self.preserve_images = preserve_images

    def make_clean_html_for_ai(self, raw_html: str) -> str:
        """
        AI 학습/RAG를 위해 불필요한 태그와 속성을 제거하고 뼈대만 남김.

        Args:
            raw_html: 원본 HTML 문자열

        Returns:
            정제된 Clean HTML
        """
        soup = BeautifulSoup(raw_html, 'html.parser')

        # 1. 주석(Comments) 제거
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # 2. 노이즈 태그 완전 삭제
        for tag_name in self.REMOVE_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # 3. 이미지 처리
        if not self.preserve_images:
            for img in soup.find_all('img'):
                # alt 텍스트가 있으면 텍스트로 대체
                alt_text = img.get('alt', '')
                if alt_text:
                    img.replace_with(f'[이미지: {alt_text}]')
                else:
                    img.decompose()

        # 4. 태그 속성 청소 (토큰 절약)
        for tag in soup.find_all(True):
            # 현재 태그의 속성들
            attrs = dict(tag.attrs)

            # 허용된 속성만 남기고 다 지움
            tag.attrs = {k: v for k, v in attrs.items() if k in self.PRESERVE_ATTRS}

        # 5. 빈 태그 정리 (내용 없는 div, span 등)
        self._remove_empty_tags(soup)

        # 6. 연속 공백/줄바꿈 정리
        clean_html = str(soup)
        clean_html = self._normalize_whitespace(clean_html)

        # 7. 최소한의 HTML 구조 래핑
        if not clean_html.strip().startswith('<!DOCTYPE') and not clean_html.strip().startswith('<html'):
            clean_html = self._wrap_with_minimal_html(clean_html)

        return clean_html

    def _remove_empty_tags(self, soup: BeautifulSoup, depth: int = 0):
        """빈 태그 재귀적 제거 (최대 5회 반복)"""
        if depth > 5:
            return

        empty_tags = []
        for tag in soup.find_all(True):
            # 텍스트나 자식이 없고, 이미지/br/hr이 아닌 경우
            if tag.name not in ['img', 'br', 'hr', 'td', 'th']:
                text = tag.get_text(strip=True)
                if not text and not tag.find_all(True):
                    empty_tags.append(tag)

        if empty_tags:
            for tag in empty_tags:
                tag.decompose()
            # 재귀적으로 다시 확인
            self._remove_empty_tags(soup, depth + 1)

    def _normalize_whitespace(self, html: str) -> str:
        """연속 공백 및 줄바꿈 정규화"""
        # 연속된 공백을 하나로
        html = re.sub(r'[ \t]+', ' ', html)
        # 연속된 줄바꿈을 최대 2개로
        html = re.sub(r'\n{3,}', '\n\n', html)
        # 태그 사이 불필요한 공백 제거
        html = re.sub(r'>\s+<', '>\n<', html)
        return html.strip()

    def _wrap_with_minimal_html(self, content: str) -> str:
        """최소한의 HTML 구조로 래핑"""
        return f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>AI Ready Document</title>
</head>
<body>
{content}
</body>
</html>'''

    def convert_to_markdown(self, html: str, strip_images: bool = True) -> str:
        """
        HTML을 마크다운으로 변환.

        Args:
            html: HTML 문자열 (Clean HTML 권장)
            strip_images: 이미지 태그 제거 여부

        Returns:
            마크다운 문자열
        """
        # markdownify 옵션
        options = {
            'heading_style': 'ATX',  # # 스타일 제목
            'bullets': '-',          # 리스트 불릿
            'strong_em_symbol': '*', # 볼드/이탤릭
            'strip': ['script', 'style'] if not strip_images else ['script', 'style', 'img']
        }

        # 변환 실행
        markdown_text = md(html, **options)

        # 후처리
        markdown_text = self._clean_markdown(markdown_text)

        return markdown_text

    def _clean_markdown(self, text: str) -> str:
        """마크다운 후처리 정리"""
        # 연속된 빈 줄 제거
        text = re.sub(r'\n{3,}', '\n\n', text)

        # 줄 끝 공백 제거
        lines = [line.rstrip() for line in text.split('\n')]

        # 연속된 빈 줄 제거 (다시)
        cleaned_lines = []
        prev_empty = False
        for line in lines:
            is_empty = not line.strip()
            if is_empty and prev_empty:
                continue
            cleaned_lines.append(line)
            prev_empty = is_empty

        return '\n'.join(cleaned_lines).strip()

    def extract_text_only(self, html: str) -> str:
        """
        HTML에서 순수 텍스트만 추출 (표 구조 제거)

        Args:
            html: HTML 문자열

        Returns:
            순수 텍스트
        """
        soup = BeautifulSoup(html, 'html.parser')

        # 노이즈 태그 제거
        for tag_name in self.REMOVE_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # 텍스트 추출
        text = soup.get_text(separator='\n', strip=True)

        # 연속 줄바꿈 정리
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()


class LegalMarkdownConverter(MarkdownConverter):
    """
    법률 문서 특화 마크다운 변환기

    표(Table)와 법률 조항 구조를 더 잘 보존합니다.
    """

    def convert_table(self, el, text, convert_as_inline):
        """표를 마크다운 테이블로 변환"""
        rows = el.find_all('tr')
        if not rows:
            return text

        md_lines = []

        for i, row in enumerate(rows):
            cells = row.find_all(['th', 'td'])
            cell_texts = []

            for cell in cells:
                # 셀 텍스트 정리
                cell_text = cell.get_text(strip=True)
                cell_text = cell_text.replace('|', '\\|')  # 파이프 이스케이프
                cell_text = cell_text.replace('\n', ' ')   # 줄바꿈 제거
                cell_texts.append(cell_text)

            md_lines.append('| ' + ' | '.join(cell_texts) + ' |')

            # 첫 번째 행 다음에 구분선 추가
            if i == 0:
                separator = '| ' + ' | '.join(['---'] * len(cells)) + ' |'
                md_lines.append(separator)

        return '\n'.join(md_lines) + '\n\n'


def create_ai_ready_html(raw_html: str) -> str:
    """
    편의 함수: AI 학습용 Clean HTML 생성

    Args:
        raw_html: 원본 HTML

    Returns:
        Clean HTML
    """
    cleaner = ContentCleaner()
    return cleaner.make_clean_html_for_ai(raw_html)


def html_to_markdown(html: str) -> str:
    """
    편의 함수: HTML을 마크다운으로 변환

    Args:
        html: HTML 문자열

    Returns:
        마크다운 문자열
    """
    cleaner = ContentCleaner()
    clean_html = cleaner.make_clean_html_for_ai(html)
    return cleaner.convert_to_markdown(clean_html)


# ============================================================
# CLI 지원
# ============================================================
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("사용법: python cleaner.py <input.html> [output_prefix]")
        print("  output_prefix를 지정하면 {prefix}_clean.html, {prefix}.md 파일 생성")
        sys.exit(1)

    input_file = sys.argv[1]
    output_prefix = sys.argv[2] if len(sys.argv) > 2 else None

    with open(input_file, 'r', encoding='utf-8') as f:
        raw_html = f.read()

    cleaner = ContentCleaner()

    # Clean HTML 생성
    clean_html = cleaner.make_clean_html_for_ai(raw_html)

    # 마크다운 변환
    markdown = cleaner.convert_to_markdown(clean_html)

    if output_prefix:
        # 파일로 저장
        with open(f"{output_prefix}_clean.html", 'w', encoding='utf-8') as f:
            f.write(clean_html)
        with open(f"{output_prefix}.md", 'w', encoding='utf-8') as f:
            f.write(markdown)
        print(f"생성 완료: {output_prefix}_clean.html, {output_prefix}.md")
    else:
        # 표준 출력
        print("=== Clean HTML ===")
        print(clean_html[:1000] + "..." if len(clean_html) > 1000 else clean_html)
        print("\n=== Markdown ===")
        print(markdown[:1000] + "..." if len(markdown) > 1000 else markdown)
