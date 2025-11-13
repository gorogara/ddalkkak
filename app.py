"""
AI 보고서 자동화 도구 - 메인 애플리케이션
Streamlit 기반 보고서 생성 도구
"""
import streamlit as st
import os
from dotenv import load_dotenv
from utils.pdf_parser import extract_text_from_pdf, extract_formatting_patterns, identify_section_structure
from utils.vector_db import VectorDBManager
from utils.content_generator import generate_full_report, extract_technical_terms, count_tokens, MAX_TOKEN_LIMIT

# 환경 변수 로드
load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="AI 보고서 자동화 도구",
    page_icon="📊",
    layout="wide"
)

# 세션 상태 초기화
if 'reference_text' not in st.session_state:
    st.session_state.reference_text = ""
if 'reference_patterns' not in st.session_state:
    st.session_state.reference_patterns = {}
if 'source_text' not in st.session_state:
    st.session_state.source_text = ""
if 'table_of_contents' not in st.session_state:
    st.session_state.table_of_contents = []
if 'vector_db' not in st.session_state:
    st.session_state.vector_db = None
if 'generated_report' not in st.session_state:
    st.session_state.generated_report = ""
if 'technical_terms' not in st.session_state:
    st.session_state.technical_terms = []
if 'report_generation_progress' not in st.session_state:
    st.session_state.report_generation_progress = {
        'current_section_index': 0,
        'completed_sections': [],
        'total_sections': 0,
        'is_generating': False
    }


def add_section(parent_number: str = "", level: int = 1):
    """
    목차에 새 섹션을 추가합니다.
    
    Args:
        parent_number: 부모 섹션 번호 (예: "1", "1-1")
        level: 섹션 레벨 (1, 2, 3)
    """
    if level == 1:
        # 최상위 레벨
        max_num = 0
        for section in st.session_state.table_of_contents:
            if section['level'] == 1:
                num = int(section['number'].split('-')[0])
                max_num = max(max_num, num)
        new_number = str(max_num + 1)
    elif level == 2:
        # 2단계 레벨
        parent_prefix = parent_number.split('-')[0]
        max_num = 0
        for section in st.session_state.table_of_contents:
            if section['level'] == 2 and section['number'].startswith(parent_prefix + '-'):
                parts = section['number'].split('-')
                if len(parts) >= 2:
                    num = int(parts[1])
                    max_num = max(max_num, num)
        new_number = f"{parent_prefix}-{max_num + 1}"
    else:  # level == 3
        # 3단계 레벨
        parent_parts = parent_number.split('-')
        if len(parent_parts) >= 2:
            max_num = 0
            for section in st.session_state.table_of_contents:
                if section['level'] == 3 and section['number'].startswith(parent_number + '-'):
                    parts = section['number'].split('-')
                    if len(parts) >= 3:
                        num = int(parts[2])
                        max_num = max(max_num, num)
            new_number = f"{parent_number}-{max_num + 1}"
        else:
            return
    
    st.session_state.table_of_contents.append({
        'number': new_number,
        'title': '',
        'level': level,
        'word_count': None,
        'emphasis': 'standard'
    })


def delete_section(index: int):
    """목차에서 섹션을 삭제합니다."""
    if 0 <= index < len(st.session_state.table_of_contents):
        deleted = st.session_state.table_of_contents.pop(index)
        # 하위 섹션도 삭제
        deleted_number = deleted['number']
        st.session_state.table_of_contents = [
            s for s in st.session_state.table_of_contents
            if not s['number'].startswith(deleted_number + '-')
        ]


def render_toc_builder():
    """동적 목차 빌더 UI를 렌더링합니다."""
    st.subheader("📋 목차 구성")
    
    # 최상위 레벨 추가 버튼
    if st.button("➕ 최상위 섹션 추가", key="add_level1"):
        add_section(level=1)
    
    st.divider()
    
    # 목차 항목 표시 및 편집
    if not st.session_state.table_of_contents:
        st.info("목차를 구성하려면 위의 '➕ 최상위 섹션 추가' 버튼을 클릭하세요.")
        return
    
    # 레벨별로 그룹화하여 표시
    level1_sections = [s for s in st.session_state.table_of_contents if s['level'] == 1]
    
    for i, section in enumerate(st.session_state.table_of_contents):
        level = section['level']
        number = section['number']
        
        # 들여쓰기
        indent = "  " * (level - 1)
        
        col1, col2, col3 = st.columns([0.1, 0.8, 0.1])
        
        with col1:
            st.write(f"**{indent}{number}**")
        
        with col2:
            # 제목 입력
            new_title = st.text_input(
                "제목",
                value=section['title'],
                key=f"title_{i}",
                label_visibility="collapsed",
                placeholder="섹션 제목을 입력하세요"
            )
            st.session_state.table_of_contents[i]['title'] = new_title
            
            # 하위 레벨 추가 버튼
            if level < 3:
                button_label = f"➕ {number} 하위 섹션 추가"
                if st.button(button_label, key=f"add_{i}"):
                    add_section(parent_number=number, level=level + 1)
        
        with col3:
            # 삭제 버튼
            if st.button("🗑️", key=f"delete_{i}", help="섹션 삭제"):
                delete_section(i)
                st.rerun()
        
        st.divider()


def main():
    """메인 애플리케이션"""
    st.title("📊 AI 보고서 자동화 도구")
    st.markdown("---")
    
    # 사이드바: 문서 업로드
    with st.sidebar:
        st.header("📁 문서 업로드")
        
        # 참고 문서 업로드
        st.subheader("1. 참고 문서 (형식 템플릿)")
        reference_file = st.file_uploader(
            "PDF 파일을 업로드하세요",
            type=['pdf'],
            key="reference_uploader",
            help="표준 보고서 형식이 포함된 PDF 파일"
        )
        
        if reference_file is not None:
            if st.button("참고 문서 분석", key="analyze_reference"):
                with st.spinner("참고 문서를 분석하는 중..."):
                    st.session_state.reference_text = extract_text_from_pdf(reference_file)
                    st.session_state.reference_patterns = extract_formatting_patterns(st.session_state.reference_text)
                    st.session_state.technical_terms = extract_technical_terms(st.session_state.reference_text)
                    
                    st.success("✅ 참고 문서 분석 완료!")
                    st.info(f"추출된 텍스트 길이: {len(st.session_state.reference_text)} 문자")
                    st.info(f"발견된 기술 용어: {len(st.session_state.technical_terms)}개")
        
        st.divider()
        
        # 소스 문서 업로드
        st.subheader("2. 소스 문서 (원본 콘텐츠)")
        source_file = st.file_uploader(
            "PDF 파일을 업로드하세요",
            type=['pdf'],
            key="source_uploader",
            help="보고서에 포함할 원본 콘텐츠가 있는 PDF 파일"
        )
        
        if source_file is not None:
            if st.button("소스 문서 분석", key="analyze_source"):
                with st.spinner("소스 문서를 분석하는 중..."):
                    st.session_state.source_text = extract_text_from_pdf(source_file)
                    
                    # 벡터 DB 초기화 및 문서 추가
                    if st.session_state.vector_db is None:
                        st.session_state.vector_db = VectorDBManager()
                        st.session_state.vector_db.get_or_create_collection()
                    
                    # 텍스트를 청크로 나누어 벡터 DB에 추가
                    chunk_size = 1000
                    chunks = [
                        st.session_state.source_text[i:i+chunk_size]
                        for i in range(0, len(st.session_state.source_text), chunk_size)
                    ]
                    
                    st.session_state.vector_db.add_documents(
                        texts=chunks,
                        ids=[f"chunk_{i}" for i in range(len(chunks))]
                    )
                    
                    st.success("✅ 소스 문서 분석 완료!")
                    st.info(f"추출된 텍스트 길이: {len(st.session_state.source_text)} 문자")
                    st.info(f"벡터 DB에 추가된 청크: {len(chunks)}개")
        
        st.divider()
        
        # 초기화 버튼
        if st.button("🔄 모든 데이터 초기화", help="업로드된 문서와 목차를 모두 초기화합니다"):
            st.session_state.reference_text = ""
            st.session_state.reference_patterns = {}
            st.session_state.source_text = ""
            st.session_state.table_of_contents = []
            st.session_state.generated_report = ""
            st.session_state.technical_terms = []
            st.session_state.report_generation_progress = {
                'current_section_index': 0,
                'completed_sections': [],
                'total_sections': 0,
                'is_generating': False
            }
            if st.session_state.vector_db:
                st.session_state.vector_db.clear_collection()
                st.session_state.vector_db = None
            st.success("초기화 완료!")
            st.rerun()
    
    # 메인 영역: 목차 구성 및 보고서 생성
    tab1, tab2, tab3 = st.tabs(["📋 목차 구성", "⚙️ 설정", "📄 보고서 생성"])
    
    with tab1:
        render_toc_builder()
    
    with tab2:
        st.subheader("⚙️ 생성 설정")
        
        # 목차 검증
        if st.session_state.table_of_contents:
            st.info(f"현재 {len(st.session_state.table_of_contents)}개의 섹션이 구성되어 있습니다.")
            
            # 빈 제목 검사
            empty_titles = [s for s in st.session_state.table_of_contents if not s.get('title', '').strip()]
            if empty_titles:
                st.warning(f"⚠️ 제목이 없는 섹션이 {len(empty_titles)}개 있습니다.")
        else:
            st.warning("목차를 먼저 구성해주세요.")
    
    with tab3:
        st.subheader("📄 보고서 생성")
        
        # 전제 조건 확인
        checks = {
            "참고 문서 업로드": bool(st.session_state.reference_text),
            "소스 문서 업로드": bool(st.session_state.source_text),
            "목차 구성": len(st.session_state.table_of_contents) > 0,
            "벡터 DB 준비": st.session_state.vector_db is not None
        }
        
        all_ready = all(checks.values())
        
        # 상태 표시
        for check_name, status in checks.items():
            icon = "✅" if status else "❌"
            st.write(f"{icon} {check_name}")
        
        if not all_ready:
            st.warning("⚠️ 보고서 생성을 위해 위의 모든 항목이 준비되어야 합니다.")
        else:
            # 보고서 생성 버튼
            progress = st.session_state.report_generation_progress
            
            if not progress['is_generating']:
                if st.button("🚀 보고서 생성", type="primary", use_container_width=True):
                    if not os.getenv("OPENAI_API_KEY"):
                        st.error("⚠️ OPENAI_API_KEY가 .env 파일에 설정되지 않았습니다.")
                    else:
                        # 진행 상황 초기화
                        progress['current_section_index'] = 0
                        progress['completed_sections'] = []
                        progress['total_sections'] = len(st.session_state.table_of_contents)
                        progress['is_generating'] = True
                        st.session_state.generated_report = ""
                        st.rerun()
            
            # 보고서 생성 진행
            if progress['is_generating']:
                is_complete = False
                with st.spinner(f"보고서를 생성하는 중... ({progress['current_section_index']}/{progress['total_sections']} 섹션 완료)"):
                    try:
                        # 보고서 생성 (재개 지원)
                        report, completed, is_complete = generate_full_report(
                            table_of_contents=st.session_state.table_of_contents,
                            source_content=st.session_state.source_text,
                            reference_style=st.session_state.reference_patterns,
                            vector_db_manager=st.session_state.vector_db,
                            technical_terms=st.session_state.technical_terms,
                            start_index=progress['current_section_index'],
                            existing_report=st.session_state.generated_report
                        )
                        
                        st.session_state.generated_report = report
                        progress['current_section_index'] = completed
                        
                        if is_complete:
                            progress['is_generating'] = False
                            st.success("✅ 보고서 생성 완료!")
                            st.rerun()
                        else:
                            st.warning(f"⚠️ 일부 섹션만 생성되었습니다 ({completed}/{progress['total_sections']}). 계속 생성하려면 아래 버튼을 클릭하세요.")
                    except Exception as e:
                        progress['is_generating'] = False
                        st.error(f"보고서 생성 중 오류 발생: {str(e)}")
                        st.rerun()
                
                # 계속 출력하기 버튼
                if not is_complete and progress['current_section_index'] < progress['total_sections']:
                    if st.button("계속 출력하기", type="primary", use_container_width=True):
                        st.rerun()
            
            # 생성된 보고서 표시
            if st.session_state.generated_report:
                st.divider()
                st.subheader("📄 생성된 보고서")
                
                # 토큰 수 표시
                token_count = count_tokens(st.session_state.generated_report)
                st.info(f"생성된 콘텐츠 토큰 수: {token_count:,} / {MAX_TOKEN_LIMIT:,}")
                
                # 보고서 내용 표시
                st.markdown(st.session_state.generated_report)
                
                # 복사 버튼
                st.download_button(
                    label="📥 보고서 다운로드 (텍스트)",
                    data=st.session_state.generated_report,
                    file_name="generated_report.txt",
                    mime="text/plain"
                )


if __name__ == "__main__":
    main()

