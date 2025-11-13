"""
연도 기반 콘텐츠 필터링 모듈
"""
import re
from typing import List, Dict, Tuple


def detect_next_year_sections(table_of_contents: List[Dict]) -> Tuple[bool, List[str]]:
    """
    목차에서 다음 연도 계획 섹션을 감지합니다.
    
    Args:
        table_of_contents: 목차 리스트
        
    Returns:
        (has_next_year_section, matching_section_titles) 튜플
    """
    next_year_patterns = [
        r'다음년도\s*수행\s*계획',
        r'다음년도\s*계획',
        r'차년도\s*계획',
        r'차년도\s*수행\s*계획',
        r'내년\s*계획',
        r'내년\s*수행\s*계획',
        r'익년도\s*계획',
        r'익년도\s*수행\s*계획',
        r'향후\s*계획',
        r'\d+차년도\s*계획',
        r'\d+차년도\s*수행\s*계획'
    ]
    
    matching_sections = []
    
    for section in table_of_contents:
        title = section.get('title', '').strip()
        if not title:
            continue
        
        for pattern in next_year_patterns:
            if re.search(pattern, title, re.IGNORECASE):
                matching_sections.append(title)
                break
    
    return len(matching_sections) > 0, matching_sections


def extract_year_from_text(text: str) -> List[int]:
    """
    텍스트에서 연도 정보를 추출합니다.
    
    Args:
        text: 텍스트
        
    Returns:
        발견된 연도 리스트 (예: [1, 2, 3] for "1차년도", "2차년도", "3차년도")
    """
    # 패턴: N차년도, N차, N년차 등
    patterns = [
        r'(\d+)차년도',
        r'(\d+)차\s*년도',
        r'(\d+)년차',
        r'(\d+)차',
    ]
    
    years = set()
    
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            try:
                year = int(match)
                if 1 <= year <= 10:  # 합리적인 범위
                    years.add(year)
            except ValueError:
                continue
    
    return sorted(list(years))


def should_include_content(
    content_text: str,
    current_year: int,
    section_title: str,
    has_next_year_section: bool,
    matching_sections: List[str]
) -> bool:
    """
    콘텐츠를 포함할지 결정합니다.
    
    Args:
        content_text: 콘텐츠 텍스트
        current_year: 현재 연도 (예: 2 for 2차년도)
        section_title: 현재 생성 중인 섹션 제목
        has_next_year_section: 목차에 다음 연도 계획 섹션이 있는지
        matching_sections: 다음 연도 계획 섹션 제목 리스트
        
    Returns:
        포함 여부 (True/False)
    """
    # 콘텐츠에서 연도 추출
    content_years = extract_year_from_text(content_text)
    
    if not content_years:
        # 연도 정보가 없으면 포함 (기본값)
        return True
    
    # 현재 섹션이 다음 연도 계획 섹션인지 확인
    is_next_year_section = False
    for matching_section in matching_sections:
        if matching_section in section_title or section_title in matching_section:
            is_next_year_section = True
            break
    
    # 각 연도에 대해 판단
    for year in content_years:
        # 과거 연도: 항상 제외
        if year < current_year:
            return False
        
        # 현재 연도: 항상 포함
        if year == current_year:
            return True
        
        # 다음 연도 (current_year + 1)
        if year == current_year + 1:
            # 다음 연도 계획 섹션이 있고, 현재 섹션이 그 섹션이면 포함
            if has_next_year_section and is_next_year_section:
                return True
            # 그 외에는 제외
            return False
        
        # 현재 연도 + 2 이상: 항상 제외
        if year > current_year + 1:
            return False
    
    # 연도 정보가 있지만 위 조건에 해당하지 않으면 포함 (안전장치)
    return True


def filter_content_by_year(
    content_text: str,
    current_year: int,
    section_title: str,
    has_next_year_section: bool,
    matching_sections: List[str]
) -> str:
    """
    연도 기반으로 콘텐츠를 필터링합니다.
    
    Args:
        content_text: 원본 콘텐츠
        current_year: 현재 연도
        section_title: 현재 섹션 제목
        has_next_year_section: 다음 연도 계획 섹션 존재 여부
        matching_sections: 다음 연도 계획 섹션 제목 리스트
        
    Returns:
        필터링된 콘텐츠
    """
    # 문장 단위로 분리
    sentences = re.split(r'[.!?。！？]\s*', content_text)
    
    filtered_sentences = []
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        
        # 각 문장에 대해 포함 여부 결정
        if should_include_content(
            sentence,
            current_year,
            section_title,
            has_next_year_section,
            matching_sections
        ):
            filtered_sentences.append(sentence)
    
    return '. '.join(filtered_sentences) + '.' if filtered_sentences else ""

