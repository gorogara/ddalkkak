"""
PDF 파싱 유틸리티 모듈
참고 문서와 소스 문서의 텍스트를 추출합니다.
"""
import pdfplumber
import streamlit as st
from typing import Dict, List, Optional


def extract_text_from_pdf(pdf_file) -> str:
    """
    PDF 파일에서 텍스트를 추출합니다.
    
    Args:
        pdf_file: Streamlit UploadedFile 객체
        
    Returns:
        추출된 텍스트 문자열
    """
    try:
        text_content = []
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_content.append(text)
        return "\n\n".join(text_content)
    except Exception as e:
        st.error(f"PDF 파싱 오류: {str(e)}")
        return ""


def extract_formatting_patterns(text: str) -> Dict:
    """
    참고 문서에서 서식 패턴을 추출합니다.
    
    Args:
        text: 추출된 텍스트
        
    Returns:
        서식 패턴 딕셔너리
    """
    import re
    patterns = {
        "sentence_endings": [],
        "technical_terms": [],
        "section_transitions": [],
        "itemized_endings": [],
        "is_itemized_format": False
    }
    
    # 개조식 종결어미 패턴 추출 (~임, ~함, ~됨, ~예정임, ~계획임 등)
    itemized_patterns = re.findall(r'[임함됨]|예정임|계획임|목적임|필요함|중요함|완료됨|진행됨|제공함|적용함|개발함|구현함|완성함|수행함|실시함|추진함|강화함|개선함|확대함|보완함|확인함|검토함|분석함|평가함|활용함|운영함|관리함|지원함|협력함|공유함|연계함|연결함|통합함|연결됨|통합됨|구축됨|설치됨|적용됨|개선됨|완료됨|진행됨|제공됨|개발됨|구현됨|완성됨|수행됨|실시됨|추진됨|강화됨|확대됨|보완됨|확인됨|검토됨|분석됨|평가됨|활용됨|운영됨|관리됨|지원됨|협력됨|공유됨|연계됨', text)
    patterns["itemized_endings"] = list(set(itemized_patterns))
    
    # 개조식 형식 사용 여부 확인 (불릿 포인트 또는 대시로 시작하는 줄이 있는지)
    bullet_lines = re.findall(r'^[\*\-\•]\s+.+[임함됨]', text, re.MULTILINE)
    if len(bullet_lines) > 5:  # 5개 이상의 개조식 문장이 있으면 개조식 형식으로 판단
        patterns["is_itemized_format"] = True
    
    # 문장 종결어미 패턴 추출 (예: ~다, ~습니다, ~음)
    sentence_endings = re.findall(r'[다음임함됨]', text)
    patterns["sentence_endings"] = list(set(sentence_endings))
    
    # 기술 용어 추출 (대문자 약어, 표준 번호 등)
    # ALL-CAPS 약어 (2자 이상)
    acronyms = re.findall(r'\b[A-Z]{2,}\b', text)
    # 표준 번호 (S-100, ISO 19115 등)
    standards = re.findall(r'\b[A-Z]+[- ]?[0-9]+\b', text)
    # 괄호 안의 약어 (예: 국제수로기구(IHO))
    parentheses_terms = re.findall(r'\(([A-Z]{2,})\)', text)
    
    patterns["technical_terms"] = list(set(acronyms + standards + parentheses_terms))
    
    return patterns


def identify_section_structure(text: str) -> List[Dict]:
    """
    문서의 섹션 구조를 식별합니다.
    
    Args:
        text: 추출된 텍스트
        
    Returns:
        섹션 구조 리스트
    """
    import re
    sections = []
    
    # 섹션 헤더 패턴 찾기 (예: "1. 제목", "1-1. 하위 제목")
    section_patterns = [
        r'^\d+\.\s+(.+)$',  # 1. 제목
        r'^\d+-\d+\.\s+(.+)$',  # 1-1. 하위 제목
        r'^\d+-\d+-\d+\.\s+(.+)$',  # 1-1-1. 세부 제목
    ]
    
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        for pattern in section_patterns:
            match = re.match(pattern, line)
            if match:
                sections.append({
                    "level": pattern.count('\\d'),
                    "title": match.group(1),
                    "full_text": line
                })
                break
    
    return sections

