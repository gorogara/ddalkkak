"""
콘텐츠 생성 엔진 모듈
GPT-4o를 사용하여 보고서 섹션을 생성합니다.
"""
import os
from dotenv import load_dotenv
from openai import OpenAI
from typing import Dict, List, Optional
import streamlit as st
import tiktoken

# 환경 변수 로드
load_dotenv()

# OpenAI API 키 검증
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = None
if OPENAI_API_KEY:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception:
        client = None

MAX_TOKEN_LIMIT = int(os.getenv("MAX_TOKEN_LIMIT", 128000))


def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """
    텍스트의 토큰 수를 계산합니다.
    
    Args:
        text: 텍스트
        model: 모델 이름
        
    Returns:
        토큰 수
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except:
        # 폴백: 대략적인 계산
        return len(text) // 4


def extract_technical_terms(text: str) -> List[str]:
    """
    기술 용어를 추출합니다.
    
    Args:
        text: 텍스트
        
    Returns:
        기술 용어 리스트
    """
    import re
    terms = []
    
    # ALL-CAPS 약어 (2자 이상)
    acronyms = re.findall(r'\b[A-Z]{2,}\b', text)
    # 표준 번호 (S-100, ISO 19115 등)
    standards = re.findall(r'\b[A-Z]+[- ]?[0-9]+\b', text)
    # 괄호 안의 약어
    parentheses_terms = re.findall(r'\(([A-Z]{2,})\)', text)
    
    terms.extend(acronyms)
    terms.extend(standards)
    terms.extend(parentheses_terms)
    
    return list(set(terms))


def build_system_prompt(reference_patterns: Dict, technical_terms: List[str]) -> str:
    """
    시스템 프롬프트를 생성합니다.
    
    Args:
        reference_patterns: 참고 문서의 패턴
        technical_terms: 기술 용어 리스트
        
    Returns:
        시스템 프롬프트 문자열
    """
    terms_list = ", ".join(technical_terms[:50])  # 처음 50개만 포함
    
    prompt = f"""당신은 한국어 비즈니스 보고서 자동화 어시스턴트입니다. 당신의 작업:

- 참고 문서의 작성 스타일을 분석합니다 (톤, 용어, 문장 구조)
- 소스 문서에서 목차에 맞는 콘텐츠를 추출합니다
- 참고 스타일을 정확히 반영하는 한국어 섹션을 생성합니다
- 추가나 생략 없이 모든 사실 정보를 보존합니다
- 맥락에 적절한 지점에 관련 이미지를 추천합니다 (설명은 한국어로)

중요 요구사항:
- 모든 출력 텍스트는 반드시 한국어여야 합니다
- 한국어 문장 종결어미를 참고 스타일에 정확히 맞춥니다 (예: ~다, ~습니다, ~음)
- 정부 보고서에 적합한 공식 비즈니스 한국어를 사용합니다
- 참고 문서의 작성 스타일(종결어미)을 복제합니다


기술 용어 보존:
- 기술 약어를 절대 번역하지 마세요 (IHO, VTS, ECDIS, AIS, S-100, S-57 등)
- 표준 식별자를 절대 번역하지 마세요 (S-100, ISO 19115 등)
- 조직 이름을 절대 번역하지 마세요 (원본 그대로 또는 참고 문서의 형식 사용)
- 참고에서 "국제수로기구(IHO)"를 사용하면 정확한 형식을 복제합니다
- ALL CAPS 또는 영숫자 형식의 용어는 정확히 보존합니다
- 확실하지 않으면 한국어 번역을 만들어내기보다 원본 영어 용어를 보존합니다
- 해양/수로 도메인 용어는 특별한 주의가 필요합니다 (S-100, S-101, ENC, ECDIS, VTS, AIS, ARPA 등)

보호된 기술 용어 목록: {terms_list}

제약사항:
- 제공된 정보를 넘어서는 데이터나 주장을 만들어내지 마세요
- 콘텐츠를 임의로 판단하여 생략하거나 수정하지 마세요
- 기술적 정확성을 유지합니다
- 간결함보다 완전성과 품질을 우선시합니다
- BLUEMAP 회사와 관련 없는 내용을 결과에 포함하지 않습니다.
- 문서 콘텐츠의 품질과 양이 비용 절감보다 우선입니다"""
    
    return prompt


def generate_section_content(
    section_title: str,
    section_level: int,
    source_content: str,
    reference_style: Dict,
    previous_sections: List[str] = None,
    technical_terms: List[str] = None
) -> str:
    """
    보고서 섹션 콘텐츠를 생성합니다.
    
    Args:
        section_title: 섹션 제목
        section_level: 섹션 레벨 (1, 2, 3)
        source_content: 소스 문서 콘텐츠
        reference_style: 참고 문서 스타일
        previous_sections: 이전 섹션들 (컨텍스트용)
        technical_terms: 기술 용어 리스트
        
    Returns:
        생성된 섹션 콘텐츠
    """
    global client
    if not OPENAI_API_KEY or not client:
        return "⚠️ OpenAI API 키가 설정되지 않았습니다."
    
    if technical_terms is None:
        technical_terms = []
    
    # 시스템 프롬프트 생성
    system_prompt = build_system_prompt(reference_style, technical_terms)
    
    # 사용자 프롬프트 구성
    context = ""
    if previous_sections:
        context = "\n\n이전 섹션들:\n" + "\n\n".join(previous_sections[-3:])  # 최근 3개 섹션만
    
    user_prompt = f"""다음 섹션을 생성해주세요:

섹션 제목: {section_title}
섹션 레벨: {section_level}

소스 문서 콘텐츠:
{source_content[:5000]}  # 처음 5000자만 사용

{context}

요구사항:
1. 한국어로 작성하세요
2. 참고 문서의 스타일을 정확히 따르세요
3. 소스 문서의 정보만 사용하고 추가 정보를 만들어내지 마세요
4. 기술 용어는 원본 그대로 보존하세요
5. 맥락에 적절한 지점에 이미지 추천을 포함하세요 (형식: [이미지 추천: 설명 - 위치 맥락])
6. 공식 비즈니스 보고서 톤을 유지하세요"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=4000
        )
        
        generated_content = response.choices[0].message.content
        return generated_content
    except Exception as e:
        st.error(f"콘텐츠 생성 오류: {str(e)}")
        return f"⚠️ 콘텐츠 생성 중 오류가 발생했습니다: {str(e)}"


def generate_full_report(
    table_of_contents: List[Dict],
    source_content: str,
    reference_style: Dict,
    vector_db_manager,
    technical_terms: List[str],
    start_index: int = 0,
    existing_report: str = ""
) -> tuple[str, int, bool]:
    """
    전체 보고서를 생성합니다. (진행 상황 추적 지원)
    
    Args:
        table_of_contents: 목차 구조
        source_content: 소스 문서 콘텐츠
        reference_style: 참고 문서 스타일
        vector_db_manager: 벡터 DB 관리자
        technical_terms: 기술 용어 리스트
        start_index: 시작할 섹션 인덱스 (재개용)
        existing_report: 기존에 생성된 보고서 (재개용)
        
    Returns:
        (생성된 보고서, 완료된 섹션 수, 완료 여부) 튜플
    """
    full_report = []
    if existing_report:
        full_report.append(existing_report)
    
    previous_sections = []
    if existing_report:
        # 기존 보고서에서 이전 섹션 추출
        sections = existing_report.split("\n\n\n")
        previous_sections = sections[-3:] if len(sections) >= 3 else sections
    
    # 목차를 레벨별로 정렬
    sorted_toc = sorted(table_of_contents, key=lambda x: (
        x.get('level', 1),
        x.get('number', '')
    ))
    
    total_sections = len(sorted_toc)
    completed_count = start_index
    
    # 토큰 제한 확인
    current_tokens = count_tokens(existing_report) if existing_report else 0
    
    for i, section in enumerate(sorted_toc[start_index:], start=start_index):
        section_title = section.get('title', '')
        section_level = section.get('level', 1)
        section_number = section.get('number', '')
        
        # 토큰 제한 확인
        if current_tokens > MAX_TOKEN_LIMIT * 0.9:  # 90% 도달 시 중단
            return "\n".join(full_report), completed_count, False
        
        # 벡터 검색으로 관련 콘텐츠 찾기
        search_query = f"{section_number} {section_title}"
        similar_docs = vector_db_manager.search_similar(search_query, n_results=3)
        
        # 관련 콘텐츠 결합
        relevant_content = source_content
        if similar_docs:
            relevant_content = "\n\n".join([doc['text'] for doc in similar_docs])
        
        # 섹션 생성
        section_content = generate_section_content(
            section_title=section_title,
            section_level=section_level,
            source_content=relevant_content,
            reference_style=reference_style,
            previous_sections=previous_sections,
            technical_terms=technical_terms
        )
        
        # 섹션 헤더 추가
        header = f"{section_number}. {section_title}"
        full_report.append(header)
        full_report.append("=" * len(header))
        full_report.append("")
        full_report.append(section_content)
        full_report.append("")
        full_report.append("")
        
        previous_sections.append(f"{header}\n{section_content}")
        completed_count += 1
        
        # 토큰 수 업데이트
        section_text = "\n".join([header, section_content])
        current_tokens += count_tokens(section_text)
    
    is_complete = completed_count >= total_sections
    return "\n".join(full_report), completed_count, is_complete

