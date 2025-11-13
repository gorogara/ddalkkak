# AI 보고서 자동화 도구

AI 기반 보고서 자동화 도구로, 기존 템플릿을 학습하여 일관된 형식의 보고서를 생성합니다.

## 주요 기능

- 📄 **문서 업로드**: 참고 문서(형식 템플릿)와 소스 문서(원본 콘텐츠) 업로드
- 📋 **동적 목차 구성**: 3단계 계층 구조의 목차 빌더
- 🤖 **AI 콘텐츠 생성**: GPT-4o를 사용한 한국어 보고서 생성
- 🔍 **벡터 검색**: ChromaDB를 활용한 의미 기반 콘텐츠 검색
- 🖼️ **이미지 추천**: 맥락에 적절한 이미지 추천 포함
- 🔤 **기술 용어 보존**: 기술 용어, 약어, 표준 번호 자동 보존

## 설치 방법

### 1. 저장소 클론

```bash
git clone <repository-url>
cd ddalkkak
```

### 2. 가상 환경 생성 및 활성화

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

### 4. 환경 변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 다음 내용을 추가하세요:

```env
OPENAI_API_KEY=your-openai-api-key-here
MAX_TOKEN_LIMIT=128000
```

⚠️ **중요**: `.env` 파일은 절대 Git에 커밋하지 마세요!

## 실행 방법

```bash
streamlit run app.py
```

브라우저에서 자동으로 열리며, 기본 주소는 `http://localhost:8501`입니다.

## 사용 방법

### 1. 참고 문서 업로드

- 사이드바에서 "참고 문서 (형식 템플릿)" 섹션에 PDF 파일을 업로드
- "참고 문서 분석" 버튼 클릭
- 시스템이 문서의 스타일, 용어, 구조를 분석

### 2. 소스 문서 업로드

- "소스 문서 (원본 콘텐츠)" 섹션에 PDF 파일을 업로드
- "소스 문서 분석" 버튼 클릭
- 콘텐츠가 벡터 데이터베이스에 저장됨

### 3. 목차 구성

- "목차 구성" 탭에서 "➕ 최상위 섹션 추가" 버튼 클릭
- 각 섹션의 제목을 입력
- 하위 섹션을 추가하려면 각 섹션 옆의 "➕ 하위 섹션 추가" 버튼 클릭
- 최대 3단계 계층 구조 지원 (1 → 1-1 → 1-1-1)

### 4. 보고서 생성

- "보고서 생성" 탭으로 이동
- 모든 전제 조건이 충족되었는지 확인
- "🚀 보고서 생성" 버튼 클릭
- 생성된 보고서를 확인하고 다운로드

## 프로젝트 구조

```
ddalkkak/
├── app.py                 # 메인 Streamlit 애플리케이션
├── requirements.txt       # Python 의존성
├── .env.example          # 환경 변수 템플릿
├── .gitignore            # Git 무시 파일
├── README.md             # 프로젝트 문서
└── utils/                # 유틸리티 모듈
    ├── __init__.py
    ├── pdf_parser.py     # PDF 파싱 모듈
    ├── vector_db.py      # ChromaDB 벡터 데이터베이스 관리
    └── content_generator.py  # GPT-4o 콘텐츠 생성 엔진
```

## 기술 스택

- **Frontend/Backend**: Streamlit
- **LLM**: OpenAI GPT-4o
- **Vector Database**: ChromaDB (임베디드 모드)
- **PDF Parsing**: pdfplumber
- **Language Chain**: LangChain

## 주요 특징

### 한국어 출력

모든 생성된 보고서 콘텐츠는 한국어로 출력되며, 공식 비즈니스 보고서 스타일을 따릅니다.

### 기술 용어 보존

다음과 같은 기술 용어는 자동으로 보존됩니다:
- 약어 (IHO, VTS, ECDIS, AIS 등)
- 표준 번호 (S-100, S-57, ISO 19115 등)
- 조직 이름
- 제품 이름

### 이미지 추천

생성된 보고서에는 맥락에 적절한 지점에 이미지 추천이 포함됩니다:
```
[이미지 추천: 설명 - 위치 맥락]
```

## 문제 해결

### OpenAI API 키 오류

`.env` 파일에 `OPENAI_API_KEY`가 올바르게 설정되었는지 확인하세요.

### PDF 파싱 오류

PDF 파일이 손상되었거나 암호화되어 있을 수 있습니다. 다른 PDF 파일로 시도해보세요.

### 벡터 DB 오류

`chroma_db` 폴더의 권한을 확인하거나, 애플리케이션을 재시작해보세요.

## 라이선스

이 프로젝트는 내부 사용을 위한 것입니다.

## 기여

버그 리포트나 기능 제안은 이슈 트래커를 통해 제출해주세요.

