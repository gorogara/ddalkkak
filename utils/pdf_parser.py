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
    patterns = {
        "sentence_endings": [],
        "technical_terms": [],
        "section_transitions": []
    }
    
    # 문장 종결어미 패턴 추출 (예: ~다, ~습니다, ~음)
    import re
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

