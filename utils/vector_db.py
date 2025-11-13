"""
ChromaDB 벡터 데이터베이스 관리 모듈
문서 임베딩 및 유사도 검색 기능을 제공합니다.
"""
import chromadb
from chromadb.config import Settings
import os
from typing import List, Dict, Optional
import streamlit as st


class VectorDBManager:
    """ChromaDB 벡터 데이터베이스 관리 클래스"""
    
    def __init__(self, collection_name: str = "documents"):
        """
        VectorDBManager 초기화
        
        Args:
            collection_name: 컬렉션 이름
        """
        # ChromaDB 클라이언트 초기화 (임베디드 모드)
        db_path = os.path.join(os.getcwd(), "chroma_db")
        os.makedirs(db_path, exist_ok=True)
        
        self.client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection_name = collection_name
        self.collection = None
        
    def get_or_create_collection(self):
        """컬렉션을 가져오거나 생성합니다."""
        try:
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            return self.collection
        except Exception as e:
            st.error(f"컬렉션 생성 오류: {str(e)}")
            return None
    
    def add_documents(self, texts: List[str], metadatas: Optional[List[Dict]] = None, ids: Optional[List[str]] = None):
        """
        문서를 벡터 데이터베이스에 추가합니다.
        
        Args:
            texts: 문서 텍스트 리스트
            metadatas: 메타데이터 리스트
            ids: 문서 ID 리스트
        """
        if not self.collection:
            self.get_or_create_collection()
        
        if not self.collection:
            return False
        
        try:
            # ID가 제공되지 않으면 자동 생성
            if not ids:
                ids = [f"doc_{i}" for i in range(len(texts))]
            
            # 메타데이터가 없으면 빈 딕셔너리 리스트 생성
            if not metadatas:
                metadatas = [{}] * len(texts)
            
            self.collection.add(
                documents=texts,
                metadatas=metadatas,
                ids=ids
            )
            return True
        except Exception as e:
            st.error(f"문서 추가 오류: {str(e)}")
            return False
    
    def search_similar(self, query: str, n_results: int = 5) -> List[Dict]:
        """
        유사한 문서를 검색합니다.
        
        Args:
            query: 검색 쿼리
            n_results: 반환할 결과 수
            
        Returns:
            검색 결과 리스트
        """
        if not self.collection:
            self.get_or_create_collection()
        
        if not self.collection:
            return []
        
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
            # 결과를 딕셔너리 리스트로 변환
            output = []
            if results['documents'] and len(results['documents'][0]) > 0:
                for i in range(len(results['documents'][0])):
                    output.append({
                        "text": results['documents'][0][i],
                        "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                        "distance": results['distances'][0][i] if results['distances'] else None
                    })
            return output
        except Exception as e:
            st.error(f"검색 오류: {str(e)}")
            return []
    
    def clear_collection(self):
        """컬렉션의 모든 문서를 삭제합니다."""
        if self.collection:
            try:
                self.client.delete_collection(name=self.collection_name)
                self.collection = None
                return True
            except Exception as e:
                st.error(f"컬렉션 삭제 오류: {str(e)}")
                return False
        return True

