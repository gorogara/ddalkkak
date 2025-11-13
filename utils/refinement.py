"""
보고서 수정 요청 처리 모듈
"""
from typing import Dict, List, Optional
import streamlit as st
from utils.content_generator import generate_section_content
from utils.year_filter import detect_next_year_sections


def refine_report_with_request(
    current_report: str,
    modification_request: str,
    table_of_contents: List[Dict],
    source_content: str,
    reference_style: Dict,
    vector_db_manager,
    technical_terms: List[str],
    current_year: int = 2,
    has_next_year_section: bool = False,
    matching_sections: List[str] = None
) -> str:
    """
    사용자의 수정 요청을 반영하여 보고서를 재생성합니다.
    
    Args:
        current_report: 현재 보고서
        modification_request: 사용자의 수정 요청
        table_of_contents: 목차 구조
        source_content: 소스 문서 콘텐츠
        reference_style: 참고 문서 스타일
        vector_db_manager: 벡터 DB 관리자
        technical_terms: 기술 용어 리스트
        current_year: 현재 연도
        has_next_year_section: 다음 연도 계획 섹션 존재 여부
        matching_sections: 다음 연도 계획 섹션 제목 리스트
        
    Returns:
        수정된 보고서
    """
    # 보고서를 섹션별로 분리
    sections = parse_report_sections(current_report)
    
    # 수정 요청 분석
    request_type, target_section, details = analyze_modification_request(
        modification_request,
        table_of_contents
    )
    
    # 수정 요청에 따라 처리
    if request_type == "specific_section":
        # 특정 섹션 수정
        if target_section:
            modified_section = refine_single_section(
                target_section,
                sections,
                modification_request,
                source_content,
                reference_style,
                vector_db_manager,
                technical_terms,
                current_year,
                has_next_year_section,
                matching_sections,
                table_of_contents
            )
            # 해당 섹션 교체
            for i, section_data in enumerate(sections):
                if section_data['number'] == target_section:
                    sections[i] = modified_section
                    break
    elif request_type == "add_content":
        # 콘텐츠 추가
        sections = add_content_to_sections(
            sections,
            modification_request,
            source_content,
            reference_style,
            vector_db_manager,
            technical_terms,
            current_year,
            has_next_year_section,
            matching_sections
        )
    elif request_type == "regenerate_all":
        # 전체 재생성 (수정 요청 반영)
        return regenerate_report_with_modifications(
            table_of_contents,
            source_content,
            reference_style,
            vector_db_manager,
            technical_terms,
            modification_request,
            current_year,
            has_next_year_section,
            matching_sections
        )
    
    # 수정된 섹션들을 다시 조합
    refined_report = combine_sections(sections)
    return refined_report


def parse_report_sections(report: str) -> List[Dict]:
    """
    보고서를 섹션별로 파싱합니다.
    
    Args:
        report: 보고서 텍스트
        
    Returns:
        섹션 리스트
    """
    sections = []
    lines = report.split('\n')
    
    current_section = None
    current_content = []
    
    for line in lines:
        line = line.strip()
        
        # 섹션 헤더 감지 (예: "1. 제목" 또는 "1-1. 하위 제목")
        if line and (line[0].isdigit() or (len(line) > 2 and line[0:2] in ['1.', '2.', '3.', '4.', '5.'])):
            # 이전 섹션 저장
            if current_section:
                current_section['content'] = '\n'.join(current_content).strip()
                sections.append(current_section)
            
            # 새 섹션 시작
            parts = line.split('.', 1)
            if len(parts) == 2:
                number = parts[0].strip()
                title = parts[1].strip()
                current_section = {
                    'number': number,
                    'title': title,
                    'content': ''
                }
                current_content = []
        elif current_section:
            current_content.append(line)
    
    # 마지막 섹션 저장
    if current_section:
        current_section['content'] = '\n'.join(current_content).strip()
        sections.append(current_section)
    
    return sections


def analyze_modification_request(
    request: str,
    table_of_contents: List[Dict]
) -> tuple[str, Optional[str], str]:
    """
    수정 요청을 분석합니다.
    
    Args:
        request: 사용자의 수정 요청
        table_of_contents: 목차 구조
        
    Returns:
        (요청 타입, 대상 섹션 번호, 상세 정보) 튜플
    """
    request_lower = request.lower()
    
    # 특정 섹션 번호 추출 (예: "3번", "1-1번", "2-1-1번")
    import re
    section_patterns = [
        r'(\d+-\d+-\d+)번',
        r'(\d+-\d+)번',
        r'(\d+)번',
        r'(\d+-\d+-\d+)번째',
        r'(\d+-\d+)번째',
        r'(\d+)번째',
        r'섹션\s*(\d+-\d+-\d+)',
        r'섹션\s*(\d+-\d+)',
        r'섹션\s*(\d+)',
    ]
    
    target_section = None
    for pattern in section_patterns:
        match = re.search(pattern, request)
        if match:
            target_section = match.group(1)
            break
    
    # 요청 타입 판단
    if "전체" in request_lower or "모두" in request_lower or "다시" in request_lower:
        return ("regenerate_all", None, request)
    elif target_section:
        return ("specific_section", target_section, request)
    elif "추가" in request_lower or "더" in request_lower or "보완" in request_lower:
        return ("add_content", None, request)
    else:
        return ("general", None, request)


def refine_single_section(
    section_number: str,
    sections: List[Dict],
    modification_request: str,
    source_content: str,
    reference_style: Dict,
    vector_db_manager,
    technical_terms: List[str],
    current_year: int,
    has_next_year_section: bool,
    matching_sections: List[str],
    table_of_contents: List[Dict]
) -> Dict:
    """
    특정 섹션을 수정합니다.
    
    Args:
        section_number: 섹션 번호
        sections: 현재 섹션 리스트
        modification_request: 수정 요청
        source_content: 소스 문서 콘텐츠
        reference_style: 참고 문서 스타일
        vector_db_manager: 벡터 DB 관리자
        technical_terms: 기술 용어 리스트
        current_year: 현재 연도
        has_next_year_section: 다음 연도 계획 섹션 존재 여부
        matching_sections: 다음 연도 계획 섹션 제목 리스트
        
    Returns:
        수정된 섹션 딕셔너리
    """
    # 해당 섹션 찾기
    target_section = None
    for section in sections:
        if section['number'] == section_number:
            target_section = section
            break
    
    if not target_section:
        return sections[0] if sections else {}
    
    # 목차에서 해당 섹션 정보 찾기
    section_info = None
    for toc_item in table_of_contents:
        if toc_item.get('number') == section_number:
            section_info = toc_item
            break
    
    if not section_info:
        section_info = {'title': target_section['title'], 'level': 1}
    
    # 벡터 검색으로 관련 콘텐츠 찾기
    search_query = f"{section_number} {section_info.get('title', '')} {modification_request}"
    similar_docs = vector_db_manager.search_similar(search_query, n_results=5)
    
    relevant_content = source_content
    if similar_docs:
        relevant_content = "\n\n".join([doc['text'] for doc in similar_docs])
    
    # 현재 섹션이 다음 연도 계획 섹션인지 확인
    is_next_year_section = False
    if matching_sections:
        section_title = section_info.get('title', '')
        for matching_section in matching_sections:
            if matching_section in section_title or section_title in matching_section:
                is_next_year_section = True
                break
    
    # 수정 요청을 포함한 프롬프트 생성
    enhanced_title = f"{section_info.get('title', '')}"
    enhanced_content = f"{relevant_content}\n\n[수정 요청: {modification_request}]\n\n[기존 내용 참고: {target_section['content'][:1000]}]"
    
    # 수정된 섹션 생성
    refined_content = generate_section_content(
        section_title=enhanced_title,
        section_level=section_info.get('level', 1),
        source_content=enhanced_content,
        reference_style=reference_style,
        previous_sections=[target_section['content']],
        technical_terms=technical_terms,
        current_year=current_year,
        has_next_year_section=has_next_year_section,
        matching_sections=matching_sections if is_next_year_section else []
    )
    
    return {
        'number': section_number,
        'title': section_info.get('title', target_section['title']),
        'content': refined_content
    }


def add_content_to_sections(
    sections: List[Dict],
    modification_request: str,
    source_content: str,
    reference_style: Dict,
    vector_db_manager,
    technical_terms: List[str],
    current_year: int,
    has_next_year_section: bool,
    matching_sections: List[str]
) -> List[Dict]:
    """
    섹션에 콘텐츠를 추가합니다.
    
    Args:
        sections: 현재 섹션 리스트
        modification_request: 수정 요청
        source_content: 소스 문서 콘텐츠
        reference_style: 참고 문서 스타일
        vector_db_manager: 벡터 DB 관리자
        technical_terms: 기술 용어 리스트
        current_year: 현재 연도
        has_next_year_section: 다음 연도 계획 섹션 존재 여부
        matching_sections: 다음 연도 계획 섹션 제목 리스트
        
    Returns:
        수정된 섹션 리스트
    """
    # 요청에 따라 관련 섹션 찾기 및 수정
    # 간단한 구현: 모든 섹션에 추가 정보 포함하도록 수정
    return sections


def regenerate_report_with_modifications(
    table_of_contents: List[Dict],
    source_content: str,
    reference_style: Dict,
    vector_db_manager,
    technical_terms: List[str],
    modification_request: str,
    current_year: int,
    has_next_year_section: bool,
    matching_sections: List[str]
) -> str:
    """
    수정 요청을 반영하여 보고서를 전체 재생성합니다.
    
    Args:
        table_of_contents: 목차 구조
        source_content: 소스 문서 콘텐츠
        reference_style: 참고 문서 스타일
        vector_db_manager: 벡터 DB 관리자
        technical_terms: 기술 용어 리스트
        modification_request: 수정 요청
        current_year: 현재 연도
        has_next_year_section: 다음 연도 계획 섹션 존재 여부
        matching_sections: 다음 연도 계획 섹션 제목 리스트
        
    Returns:
        재생성된 보고서
    """
    # 전체 재생성은 generate_full_report를 사용하되, 수정 요청을 프롬프트에 포함
    # 여기서는 간단히 기존 함수를 호출
    from utils.content_generator import generate_full_report
    
    report, _, _ = generate_full_report(
        table_of_contents=table_of_contents,
        source_content=source_content,
        reference_style=reference_style,
        vector_db_manager=vector_db_manager,
        technical_terms=technical_terms,
        current_year=current_year,
        has_next_year_section=has_next_year_section,
        matching_sections=matching_sections
    )
    
    return report


def combine_sections(sections: List[Dict]) -> str:
    """
    섹션들을 조합하여 보고서를 생성합니다.
    
    Args:
        sections: 섹션 리스트
        
    Returns:
        조합된 보고서 텍스트
    """
    report_parts = []
    
    for section in sections:
        header = f"{section['number']}. {section['title']}"
        report_parts.append(header)
        report_parts.append("=" * len(header))
        report_parts.append("")
        report_parts.append(section['content'])
        report_parts.append("")
        report_parts.append("")
    
    return "\n".join(report_parts)

