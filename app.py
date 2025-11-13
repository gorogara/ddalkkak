"""
AI 보고서 자동화 도구 - 메인 애플리케이션
Streamlit 기반 보고서 생성 도구
"""
import streamlit as st
import os
from typing import List, Dict
from dotenv import load_dotenv
from utils.pdf_parser import extract_text_from_pdf, extract_formatting_patterns, identify_section_structure
from utils.vector_db import VectorDBManager
from utils.content_generator import generate_full_report, extract_technical_terms, count_tokens, MAX_TOKEN_LIMIT

# 환경 변수 로드
load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="보고서 딸깍",
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
if 'source_files' not in st.session_state:
    st.session_state.source_files = []
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
if 'current_year' not in st.session_state:
    st.session_state.current_year = 2  # 기본값: 2차년도
if 'total_years' not in st.session_state:
    st.session_state.total_years = 5  # 기본값: 5년 프로젝트
if 'refinement_chat_history' not in st.session_state:
    st.session_state.refinement_chat_history = []  # 채팅 히스토리
if 'is_refining' not in st.session_state:
    st.session_state.is_refining = False  # 수정 중 플래그


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


def sort_toc_by_hierarchy(table_of_contents: List[Dict]) -> List[Dict]:
    """
    목차를 계층 구조에 따라 정렬합니다.
    
    Args:
        table_of_contents: 목차 리스트
        
    Returns:
        계층 구조에 따라 정렬된 목차 리스트
    """
    if not table_of_contents:
        return []
    
    # 번호를 숫자 리스트로 변환하여 정렬 (예: "1-2-3" -> [1, 2, 3])
    def number_to_list(number_str: str) -> List[int]:
        try:
            return [int(x) for x in number_str.split('-')]
        except:
            return [0]
    
    # 정렬: 먼저 번호를 숫자 리스트로 변환하여 비교
    sorted_toc = sorted(table_of_contents, key=lambda x: number_to_list(x.get('number', '0')))
    
    return sorted_toc


def renumber_toc_by_hierarchy(table_of_contents: List[Dict]) -> List[Dict]:
    """
    목차를 계층 구조에 따라 재번호 매깁니다.
    
    Args:
        table_of_contents: 목차 리스트
        
    Returns:
        재번호가 매겨진 목차 리스트
    """
    if not table_of_contents:
        return []
    
    # 계층 구조에 따라 정렬
    sorted_toc = sort_toc_by_hierarchy(table_of_contents)
    
    # 재번호 매기기
    renumbered = []
    level1_counter = 0
    level2_counters = {}  # {parent_number: counter}
    level3_counters = {}  # {parent_number: counter} (레벨 2 번호를 키로 사용)
    
    for section in sorted_toc:
        level = section.get('level', 1)
        old_number = section.get('number', '')
        
        new_section = section.copy()
        
        if level == 1:
            level1_counter += 1
            new_number = str(level1_counter)
            level2_counters[new_number] = 0
        elif level == 2:
            # 부모 번호 찾기: 가장 최근의 레벨 1 섹션
            parent_number = None
            for prev_section in reversed(renumbered):
                if prev_section.get('level', 1) == 1:
                    parent_number = prev_section.get('number', '')
                    break
            
            if parent_number is None:
                # 부모를 찾을 수 없으면 현재 레벨 1 카운터를 부모로 사용
                parent_number = str(level1_counter)
            
            if parent_number not in level2_counters:
                level2_counters[parent_number] = 0
            
            level2_counters[parent_number] += 1
            new_number = f"{parent_number}-{level2_counters[parent_number]}"
            level3_counters[new_number] = 0
        elif level == 3:
            # 부모 번호 찾기: 가장 최근의 레벨 2 섹션
            parent_number = None
            for prev_section in reversed(renumbered):
                if prev_section.get('level', 1) == 2:
                    parent_number = prev_section.get('number', '')
                    break
            
            if parent_number is None:
                # 부모를 찾을 수 없으면 레벨 2처럼 처리
                new_number = old_number
            else:
                if parent_number not in level3_counters:
                    level3_counters[parent_number] = 0
                level3_counters[parent_number] += 1
                new_number = f"{parent_number}-{level3_counters[parent_number]}"
        
        new_section['number'] = new_number
        renumbered.append(new_section)
    
    return renumbered


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
    
    # 계층 구조에 따라 정렬된 목차 가져오기
    sorted_toc = sort_toc_by_hierarchy(st.session_state.table_of_contents)
    
    # 원본 인덱스를 찾기 위한 매핑 생성
    original_indices = {}
    for idx, section in enumerate(st.session_state.table_of_contents):
        # 고유 키 생성 (번호 + 레벨)
        key = f"{section.get('number', '')}_{section.get('level', 1)}"
        original_indices[key] = idx
    
    for sorted_idx, section in enumerate(sorted_toc):
        level = section['level']
        number = section['number']
        
        # 원본 인덱스 찾기
        key = f"{number}_{level}"
        original_idx = original_indices.get(key, sorted_idx)
        
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
                key=f"title_{original_idx}_{sorted_idx}",
                label_visibility="collapsed",
                placeholder="섹션 제목을 입력하세요"
            )
            # 원본 목차 업데이트
            if original_idx < len(st.session_state.table_of_contents):
                st.session_state.table_of_contents[original_idx]['title'] = new_title
            
            # 하위 레벨 추가 버튼
            if level < 3:
                button_label = f"➕ {number} 하위 섹션 추가"
                if st.button(button_label, key=f"add_{original_idx}_{sorted_idx}"):
                    add_section(parent_number=number, level=level + 1)
                    st.rerun()
        
        with col3:
            # 삭제 버튼
            if st.button("🗑️", key=f"delete_{original_idx}_{sorted_idx}", help="섹션 삭제"):
                delete_section(original_idx)
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
        source_files = st.file_uploader(
            "PDF 파일을 업로드하세요 (최대 3개)",
            type=['pdf'],
            key="source_uploader",
            help="보고서에 포함할 원본 콘텐츠가 있는 PDF 파일",
            accept_multiple_files=True
        )
        
        # 파일 개수 검증
        if source_files is not None and len(source_files) > 3:
            st.error("⚠️ 최대 3개의 파일만 업로드할 수 있습니다.")
            source_files = source_files[:3]  # 처음 3개만 사용
        
        # 업로드된 파일 목록 표시
        if source_files is not None and len(source_files) > 0:
            st.info(f"📁 {len(source_files)}/3 파일 업로드됨")
            
            # 파일 목록 표시
            for idx, file in enumerate(source_files, 1):
                # 파일 크기 계산 (bytes)
                file_size = file.size if hasattr(file, 'size') else len(file.getvalue())
                file_size_kb = file_size / 1024
                file_size_mb = file_size_kb / 1024
                if file_size_mb >= 1:
                    size_str = f"{file_size_mb:.2f} MB"
                else:
                    size_str = f"{file_size_kb:.2f} KB"
                st.write(f"  • **{file.name}** ({size_str})")
        
        if source_files is not None and len(source_files) > 0:
            if st.button("소스 문서 분석", key="analyze_source"):
                with st.spinner("소스 문서를 분석하는 중..."):
                    all_texts = []
                    all_chunks = []
                    chunk_id_counter = 0
                    
                    # 벡터 DB 초기화
                    if st.session_state.vector_db is None:
                        st.session_state.vector_db = VectorDBManager()
                        st.session_state.vector_db.get_or_create_collection()
                    
                    # 각 파일 처리
                    for idx, source_file in enumerate(source_files, 1):
                        file_text = extract_text_from_pdf(source_file)
                        all_texts.append(file_text)
                        
                        # 텍스트를 청크로 나누어 벡터 DB에 추가
                        chunk_size = 1000
                        file_chunks = [
                            file_text[i:i+chunk_size]
                            for i in range(0, len(file_text), chunk_size)
                        ]
                        
                        # 각 청크에 source_doc_N 접두사 추가
                        chunk_ids = [
                            f"source_doc_{idx}_chunk_{i}"
                            for i in range(len(file_chunks))
                        ]
                        
                        # 메타데이터에 파일명 포함
                        metadatas = [
                            {"source_file": f"source_doc_{idx}", "file_name": source_file.name}
                            for _ in file_chunks
                        ]
                        
                        st.session_state.vector_db.add_documents(
                            texts=file_chunks,
                            ids=chunk_ids,
                            metadatas=metadatas
                        )
                        
                        all_chunks.extend(file_chunks)
                        chunk_id_counter += len(file_chunks)
                    
                    # 모든 텍스트 결합
                    st.session_state.source_text = "\n\n".join(all_texts)
                    st.session_state.source_files = [f.name for f in source_files]
                    
                    st.success("✅ 소스 문서 분석 완료!")
                    st.info(f"업로드된 파일: {len(source_files)}개")
                    st.info(f"추출된 텍스트 길이: {len(st.session_state.source_text):,} 문자")
                    st.info(f"벡터 DB에 추가된 청크: {chunk_id_counter}개")
        
        st.divider()
        
        # 초기화 버튼
        if st.button("🔄 모든 데이터 초기화", help="업로드된 문서와 목차를 모두 초기화합니다"):
            st.session_state.reference_text = ""
            st.session_state.reference_patterns = {}
            st.session_state.source_text = ""
            st.session_state.source_files = []
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
        
        # 연도 설정
        st.markdown("### 📅 연도 설정")
        col1, col2 = st.columns(2)
        with col1:
            current_year = st.number_input(
                "현재 연도 (차년도)",
                min_value=1,
                max_value=10,
                value=st.session_state.current_year,
                help="예: 2차년도 보고서인 경우 2를 입력"
            )
            st.session_state.current_year = current_year
        
        with col2:
            total_years = st.number_input(
                "전체 프로젝트 기간 (차년도)",
                min_value=1,
                max_value=10,
                value=st.session_state.total_years,
                help="예: 5년 프로젝트인 경우 5를 입력"
            )
            st.session_state.total_years = total_years
        
        # 다음 연도 계획 섹션 감지
        from utils.year_filter import detect_next_year_sections
        has_next_year, matching_sections = detect_next_year_sections(st.session_state.table_of_contents)
        
        if has_next_year:
            st.success(f"✅ 다음 연도 계획 섹션 감지됨: {', '.join(matching_sections)}")
            st.info(f"📌 {current_year + 1}차년도 콘텐츠는 다음 연도 계획 섹션에만 포함됩니다.")
        else:
            st.info(f"ℹ️ 다음 연도 계획 섹션이 없습니다. {current_year}차년도 콘텐츠만 포함됩니다.")
        
        st.divider()
        
        # 목차 검증
        st.markdown("### 📋 목차 검증")
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
            "소스 문서 업로드": bool(st.session_state.source_text) and len(st.session_state.source_files) > 0,
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
                with st.spinner(f"보고서를 생성하는 중... (목차가 많을 수록 오래 걸립니다.)"):
                    try:
                        # 다음 연도 계획 섹션 감지
                        from utils.year_filter import detect_next_year_sections
                        has_next_year, matching_sections = detect_next_year_sections(st.session_state.table_of_contents)
                        
                        # 보고서 생성 (재개 지원)
                        report, completed, is_complete = generate_full_report(
                            table_of_contents=st.session_state.table_of_contents,
                            source_content=st.session_state.source_text,
                            reference_style=st.session_state.reference_patterns,
                            vector_db_manager=st.session_state.vector_db,
                            technical_terms=st.session_state.technical_terms,
                            start_index=progress['current_section_index'],
                            existing_report=st.session_state.generated_report,
                            current_year=st.session_state.current_year,
                            has_next_year_section=has_next_year,
                            matching_sections=matching_sections
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
                
                # 보고서 수정 인터페이스
                st.divider()
                st.subheader("💬 보고서 수정")
                st.markdown("생성된 보고서를 수정하고 싶으시면 아래에 요청사항을 입력해주세요.")
                st.markdown("**예시:** \"3번 섹션 더 자세히\", \"전문 용어 설명 추가\", \"1-1번 섹션 보완\"")
                
                # 채팅 히스토리 표시
                if st.session_state.refinement_chat_history:
                    st.markdown("### 💭 수정 이력")
                    for i, chat_item in enumerate(st.session_state.refinement_chat_history):
                        with st.expander(f"수정 요청 {i+1}: {chat_item['request'][:50]}..."):
                            st.markdown(f"**요청:** {chat_item['request']}")
                            st.markdown(f"**수정 시간:** {chat_item['timestamp']}")
                
                # 수정 요청 입력
                modification_request = st.text_area(
                    "수정 요청을 입력하세요",
                    key="modification_request",
                    placeholder="예: 3번 섹션을 더 자세히 작성해주세요",
                    height=100
                )
                
                col1, col2 = st.columns([1, 4])
                with col1:
                    if st.button("🔧 수정 적용", type="primary", use_container_width=True):
                        if modification_request.strip():
                            from datetime import datetime
                            st.session_state.is_refining = True
                            st.session_state.refinement_chat_history.append({
                                'request': modification_request,
                                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            })
                            st.rerun()
                        else:
                            st.warning("수정 요청을 입력해주세요.")
                
                with col2:
                    if st.button("🔄 수정 초기화", help="수정 이력을 초기화합니다"):
                        st.session_state.refinement_chat_history = []
                        st.rerun()
                
                # 수정 처리
                if st.session_state.is_refining and st.session_state.refinement_chat_history:
                    latest_request = st.session_state.refinement_chat_history[-1]['request']
                    
                    with st.spinner("보고서를 수정하는 중..."):
                        try:
                            from utils.refinement import refine_report_with_request
                            from utils.year_filter import detect_next_year_sections
                            
                            has_next_year, matching_sections = detect_next_year_sections(st.session_state.table_of_contents)
                            
                            refined_report = refine_report_with_request(
                                current_report=st.session_state.generated_report,
                                modification_request=latest_request,
                                table_of_contents=st.session_state.table_of_contents,
                                source_content=st.session_state.source_text,
                                reference_style=st.session_state.reference_patterns,
                                vector_db_manager=st.session_state.vector_db,
                                technical_terms=st.session_state.technical_terms,
                                current_year=st.session_state.current_year,
                                has_next_year_section=has_next_year,
                                matching_sections=matching_sections
                            )
                            
                            st.session_state.generated_report = refined_report
                            st.session_state.is_refining = False
                            st.success("✅ 보고서 수정 완료!")
                            st.rerun()
                        except Exception as e:
                            st.session_state.is_refining = False
                            st.error(f"보고서 수정 중 오류 발생: {str(e)}")
                            st.rerun()


if __name__ == "__main__":
    main()

