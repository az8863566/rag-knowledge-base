"""FAISS 向量存储封装"""

import hashlib
import json
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any

import faiss
import numpy as np

from config import config
from logger import logger


# FAISS 向量维度（bge-m3 模型输出 1024 维向量）
VECTOR_DIMENSION = 1024


class VectorStoreError(Exception):
    """向量存储错误异常"""
    pass


class VectorStore:
    """FAISS 向量存储"""

    def __init__(self):
        self._index = None
        self._documents: list[str] = []  # 存储原始文本
        self._metadatas: list[dict] = []  # 存储元数据
        self._id_to_index: dict[str, int] = {}  # ID 到索引的映射
        self._persist_dir: Path | None = None
        self._initialized = False

    def initialize(self) -> None:
        """初始化 FAISS 索引"""
        if self._initialized:
            return
            
        self._persist_dir = Path(config.persist_directory)
        
        try:
            self._persist_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise VectorStoreError(f"无法创建持久化目录 {self._persist_dir}: {e}")

        # 尝试加载已有数据
        if self._load():
            logger.info(f"已加载现有知识库，包含 {len(self._documents)} 个文档块")
        else:
            # 创建新的空索引（使用内积作为相似度度量，后续用归一化向量实现余弦相似度）
            self._index = faiss.IndexFlatIP(VECTOR_DIMENSION)
            logger.info("创建新的知识库")
        
        self._initialized = True

    def _get_persist_paths(self) -> dict[str, str]:
        """获取持久化文件路径"""
        base = self._persist_dir / config.collection_name
        return {
            "index": str(base) + "_index.faiss",
            "docs": str(base) + "_docs.pkl",
            "meta": str(base) + "_meta.pkl",
            "mapping": str(base) + "_mapping.pkl",
        }

    def _save(self) -> None:
        """保存数据到磁盘"""
        paths = self._get_persist_paths()
        try:
            faiss.write_index(self._index, paths["index"])
            with open(paths["docs"], "wb") as f:
                pickle.dump(self._documents, f)
            with open(paths["meta"], "wb") as f:
                pickle.dump(self._metadatas, f)
            with open(paths["mapping"], "wb") as f:
                pickle.dump(self._id_to_index, f)
            logger.debug(f"知识库已保存，共 {len(self._documents)} 个文档块")
        except Exception as e:
            logger.error(f"保存知识库失败: {e}")
            raise VectorStoreError(f"保存知识库失败: {e}")

    def _load(self) -> bool:
        """从磁盘加载数据"""
        paths = self._get_persist_paths()
        
        if not Path(paths["index"]).exists():
            return False

        try:
            self._index = faiss.read_index(paths["index"])
            
            # 验证索引维度
            if self._index.d != VECTOR_DIMENSION:
                logger.warning(f"索引维度不匹配: 期望 {VECTOR_DIMENSION}, 实际 {self._index.d}")
                return False
            
            with open(paths["docs"], "rb") as f:
                self._documents = pickle.load(f)
            with open(paths["meta"], "rb") as f:
                self._metadatas = pickle.load(f)
            with open(paths["mapping"], "rb") as f:
                self._id_to_index = pickle.load(f)
            
            # 数据一致性检查
            if len(self._documents) != self._index.ntotal:
                logger.warning(f"数据不一致: 文档数 {len(self._documents)} != 向量数 {self._index.ntotal}")
                return False
                
            return True
        except Exception as e:
            logger.warning(f"加载知识库失败: {e}")
            return False

    @property
    def collection(self):
        """兼容旧接口"""
        if not self._initialized:
            self.initialize()
        return self

    @property
    def name(self) -> str:
        return config.collection_name

    def _normalize_vectors(self, vectors: np.ndarray) -> np.ndarray:
        """归一化向量，用于余弦相似度计算"""
        if vectors.size == 0:
            return vectors
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)  # 避免除以零
        return vectors / norms

    def _validate_embeddings(self, embeddings: list[list[float]]) -> np.ndarray:
        """验证并转换嵌入向量"""
        if not embeddings:
            raise VectorStoreError("嵌入向量列表为空")
        
        vectors = np.array(embeddings, dtype=np.float32)
        
        if vectors.ndim != 2:
            raise VectorStoreError(f"嵌入向量维度错误: 期望 2D, 实际 {vectors.ndim}D")
        
        if vectors.shape[1] != VECTOR_DIMENSION:
            raise VectorStoreError(f"嵌入向量维度不匹配: 期望 {VECTOR_DIMENSION}, 实际 {vectors.shape[1]}")
        
        return vectors

    def add_documents(
        self,
        chunks: list[str],
        embeddings: list[list[float]],
        file_path: str,
    ) -> int:
        """
        添加文档块到向量库
        
        Args:
            chunks: 文本块列表
            embeddings: 对应的嵌入向量列表
            file_path: 源文件路径
            
        Returns:
            插入的文档数量
            
        Raises:
            VectorStoreError: 添加失败时抛出
        """
        if not self._initialized:
            self.initialize()
            
        if not chunks:
            return 0
        
        if len(chunks) != len(embeddings):
            raise VectorStoreError(f"文本块数量 ({len(chunks)}) 与嵌入向量数量 ({len(embeddings)}) 不匹配")

        # 验证嵌入向量
        vectors = self._validate_embeddings(embeddings)

        # 生成文档 ID（基于文件路径的哈希）
        doc_id = hashlib.md5(file_path.encode()).hexdigest()[:12]
        file_name = Path(file_path).name
        file_type = Path(file_path).suffix.lower()
        timestamp = datetime.now().isoformat()

        # 准备数据
        start_idx = len(self._documents)
        
        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_{i}"
            self._documents.append(chunk)
            self._metadatas.append({
                "doc_id": doc_id,
                "file_name": file_name,
                "file_type": file_type,
                "chunk_index": i,
                "timestamp": timestamp,
                "chunk_id": chunk_id,
            })
            self._id_to_index[chunk_id] = start_idx + i

        # 归一化并添加向量到 FAISS 索引
        vectors = self._normalize_vectors(vectors)
        self._index.add(vectors)

        # 保存到磁盘
        self._save()

        logger.info(f"添加文档: {file_name}, {len(chunks)} 个文档块")
        return len(chunks)

    def query(
        self,
        query_embedding: list[float],
        n_results: int | None = None,
    ) -> dict[str, Any]:
        """
        向量相似度查询
        
        Args:
            query_embedding: 查询向量
            n_results: 返回结果数量，默认使用配置值
            
        Returns:
            查询结果字典，包含 documents, metadatas, distances
        """
        if not self._initialized:
            self.initialize()
            
        if n_results is None:
            n_results = config.retrieval_initial_k

        if self._index.ntotal == 0:
            return {"documents": [], "metadatas": [], "distances": []}

        # 验证查询向量
        if not query_embedding:
            raise VectorStoreError("查询向量为空")
        
        if len(query_embedding) != VECTOR_DIMENSION:
            raise VectorStoreError(f"查询向量维度不匹配: 期望 {VECTOR_DIMENSION}, 实际 {len(query_embedding)}")

        # 归一化查询向量
        query_vector = np.array([query_embedding], dtype=np.float32)
        query_vector = self._normalize_vectors(query_vector)

        # 搜索
        k = min(n_results, self._index.ntotal)
        distances, indices = self._index.search(query_vector, k)

        # 整理结果
        documents = []
        metadatas = []
        dists = []

        for idx, dist in zip(indices[0], distances[0]):
            if 0 <= idx < len(self._documents):
                documents.append(self._documents[idx])
                metadatas.append(self._metadatas[idx])
                # FAISS 内积返回的是余弦相似度（因为向量已归一化）
                # 转换为距离：1 - 相似度
                dists.append(float(1 - dist))

        return {
            "documents": documents,
            "metadatas": metadatas,
            "distances": dists,
        }

    def get_stats(self) -> dict[str, Any]:
        """获取存储统计信息"""
        if not self._initialized:
            self.initialize()
        return {
            "total_chunks": len(self._documents),
            "total_vectors": self._index.ntotal if self._index else 0,
            "collection_name": config.collection_name,
        }

    def list_documents(self) -> list[dict]:
        """
        列出知识库中所有已导入的文档
        
        Returns:
            文档列表，每项包含文件路径、文档ID、块数量、导入时间等信息
        """
        if not self._initialized:
            self.initialize()
            
        # 按 doc_id 分组统计
        doc_groups: dict[str, dict] = {}
        for meta in self._metadatas:
            doc_id = meta.get("doc_id", "unknown")
            if doc_id not in doc_groups:
                doc_groups[doc_id] = {
                    "doc_id": doc_id,
                    "file_name": meta.get("file_name", "unknown"),
                    "file_type": meta.get("file_type", ""),
                    "timestamp": meta.get("timestamp", ""),
                    "chunk_count": 0,
                }
            doc_groups[doc_id]["chunk_count"] += 1
        
        # 转换为列表并按时间排序
        docs = list(doc_groups.values())
        docs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return docs

    def delete_by_doc_id(self, doc_id: str) -> int:
        """
        根据文档ID删除所有相关文档块
        
        Args:
            doc_id: 文档ID（文件路径的MD5哈希前12位）
            
        Returns:
            删除的文档块数量
        """
        if not self._initialized:
            self.initialize()
            
        # 找到需要删除的索引
        indices_to_delete = []
        for i, meta in enumerate(self._metadatas):
            if meta.get("doc_id") == doc_id:
                indices_to_delete.append(i)
        
        if not indices_to_delete:
            return 0
        
        # 重建数据（FAISS IndexFlatIP 不支持直接删除）
        # 保留不需要删除的数据
        new_documents: list[str] = []
        new_metadatas: list[dict] = []
        new_vectors: list[np.ndarray] = []
        
        # 获取所有现有向量
        if self._index.ntotal > 0:
            all_vectors = self._index.reconstruct_n(0, self._index.ntotal)
        else:
            all_vectors = np.array([]).reshape(0, VECTOR_DIMENSION).astype(np.float32)
        
        indices_to_keep = [i for i in range(len(self._documents)) if i not in indices_to_delete]
        
        for i in indices_to_keep:
            new_documents.append(self._documents[i])
            new_metadatas.append(self._metadatas[i])
            if i < len(all_vectors):
                new_vectors.append(all_vectors[i])
        
        # 重建索引
        self._index = faiss.IndexFlatIP(VECTOR_DIMENSION)
        if new_vectors:
            self._index.add(np.array(new_vectors, dtype=np.float32))
        
        self._documents = new_documents
        self._metadatas = new_metadatas
        
        # 重建ID映射
        self._id_to_index = {}
        for i, meta in enumerate(self._metadatas):
            chunk_id = meta.get("chunk_id")
            if chunk_id:
                self._id_to_index[chunk_id] = i
        
        # 保存到磁盘
        self._save()
        
        logger.info(f"删除文档: doc_id={doc_id}, {len(indices_to_delete)} 个文档块")
        return len(indices_to_delete)

    def delete_by_file_path(self, file_path: str) -> int:
        """
        根据文件路径删除文档
        
        Args:
            file_path: 文件路径
            
        Returns:
            删除的文档块数量
        """
        doc_id = hashlib.md5(file_path.encode()).hexdigest()[:12]
        return self.delete_by_doc_id(doc_id)

    def clear(self) -> None:
        """清空集合（危险操作）"""
        if not self._initialized:
            self.initialize()
            
        self._index = faiss.IndexFlatIP(VECTOR_DIMENSION)
        self._documents = []
        self._metadatas = []
        self._id_to_index = {}
        self._save()
        logger.warning("知识库已清空")


# 全局向量存储实例
vectorstore = VectorStore()
