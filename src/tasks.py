"""异步任务处理 - 文档导入任务"""

import asyncio
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass, field

from models import database, Document
from parsers import parse_file, ParserError
from text_splitter import split_text, TextSplitterError
from siliconflow_client import siliconflow_client, SiliconFlowError
from vectorstore import vectorstore, VectorStoreError
from logger import logger


@dataclass
class TaskStatus:
    """任务状态"""
    doc_id: str
    file_name: str
    status: str  # pending, processing, completed, failed
    progress: int = 0  # 0-100
    message: str = ""
    chunk_count: int = 0
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class TaskManager:
    """任务管理器"""
    
    def __init__(self):
        self._tasks: Dict[str, TaskStatus] = {}
        self._lock = asyncio.Lock()
    
    def get_task(self, doc_id: str) -> Optional[TaskStatus]:
        """获取任务状态"""
        return self._tasks.get(doc_id)
    
    def get_all_tasks(self) -> Dict[str, TaskStatus]:
        """获取所有任务"""
        return self._tasks.copy()
    
    async def create_task(self, doc_id: str, file_name: str) -> TaskStatus:
        """创建新任务"""
        async with self._lock:
            task = TaskStatus(
                doc_id=doc_id,
                file_name=file_name,
                status="pending"
            )
            self._tasks[doc_id] = task
            return task
    
    async def update_task(self, doc_id: str, **kwargs) -> Optional[TaskStatus]:
        """更新任务状态"""
        async with self._lock:
            task = self._tasks.get(doc_id)
            if task:
                for key, value in kwargs.items():
                    if hasattr(task, key):
                        setattr(task, key, value)
                task.updated_at = datetime.utcnow()
            return task
    
    async def remove_task(self, doc_id: str) -> bool:
        """移除任务"""
        async with self._lock:
            if doc_id in self._tasks:
                del self._tasks[doc_id]
                return True
            return False


# 全局任务管理器
task_manager = TaskManager()


async def process_document(file_path: str, doc_id: str) -> None:
    """
    异步处理文档导入
    
    Args:
        file_path: 文件路径
        doc_id: 文档ID
    """
    file_name = Path(file_path).name
    
    try:
        # 更新任务状态为处理中
        await task_manager.update_task(
            doc_id,
            status="processing",
            progress=10,
            message="正在解析文件..."
        )
        
        # 1. 解析文件
        try:
            text = parse_file(file_path)
            await task_manager.update_task(
                doc_id,
                progress=30,
                message="文件解析完成，正在分块..."
            )
        except ParserError as e:
            raise Exception(f"文件解析失败: {e}")
        
        if not text or not text.strip():
            raise Exception("文件内容为空")
        
        # 2. 文本分块
        try:
            chunks = split_text(text)
            await task_manager.update_task(
                doc_id,
                progress=50,
                message=f"文本分块完成，共 {len(chunks)} 块，正在生成嵌入..."
            )
        except TextSplitterError as e:
            raise Exception(f"文本分块失败: {e}")
        
        if not chunks:
            raise Exception("文本分块失败：无法生成有效的文本块")
        
        # 3. 生成嵌入
        try:
            embeddings = await asyncio.to_thread(siliconflow_client.embed_texts, chunks)
            await task_manager.update_task(
                doc_id,
                progress=80,
                message="嵌入生成完成，正在存入向量库..."
            )
        except SiliconFlowError as e:
            raise Exception(f"嵌入生成失败: {e}")
        
        if len(embeddings) != len(chunks):
            raise Exception(f"嵌入向量数量不匹配：期望 {len(chunks)}，实际 {len(embeddings)}")
        
        # 4. 存入向量库
        try:
            count = await asyncio.to_thread(
                vectorstore.add_documents,
                chunks,
                embeddings,
                file_path
            )
            await task_manager.update_task(
                doc_id,
                progress=100,
                message=f"文档导入成功，共 {count} 个块",
                chunk_count=count
            )
        except VectorStoreError as e:
            raise Exception(f"向量存储失败: {e}")
        
        # 5. 更新数据库状态
        session = database.get_session()
        try:
            doc = session.query(Document).filter(Document.id == doc_id).first()
            if doc:
                doc.status = "completed"
                doc.chunk_count = count
                doc.updated_at = datetime.utcnow()
                session.commit()
        except Exception as e:
            logger.error(f"更新数据库状态失败: {e}")
            session.rollback()
        finally:
            session.close()
        
        # 更新任务状态为完成
        await task_manager.update_task(
            doc_id,
            status="completed",
            progress=100,
            message=f"成功导入 {count} 个文档块"
        )
        
        logger.info(f"文档处理完成: {file_name}, {count} 个块")
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"文档处理失败: {file_name}, {error_msg}")
        
        # 更新任务状态为失败
        await task_manager.update_task(
            doc_id,
            status="failed",
            message="处理失败",
            error_message=error_msg
        )
        
        # 更新数据库状态
        session = database.get_session()
        try:
            doc = session.query(Document).filter(Document.id == doc_id).first()
            if doc:
                doc.status = "failed"
                doc.error_message = error_msg
                doc.updated_at = datetime.utcnow()
                session.commit()
        except Exception as db_e:
            logger.error(f"更新数据库失败状态失败: {db_e}")
            session.rollback()
        finally:
            session.close()


async def delete_document_task(doc_id: str) -> bool:
    """
    异步删除文档
    
    Args:
        doc_id: 文档ID
        
    Returns:
        是否删除成功
    """
    try:
        # 从向量库删除
        count = await asyncio.to_thread(vectorstore.delete_by_doc_id, doc_id)
        
        # 从数据库删除
        session = database.get_session()
        try:
            doc = session.query(Document).filter(Document.id == doc_id).first()
            if doc:
                session.delete(doc)
                session.commit()
                logger.info(f"文档已从数据库删除: {doc_id}")
        except Exception as e:
            logger.error(f"从数据库删除文档失败: {e}")
            session.rollback()
        finally:
            session.close()
        
        logger.info(f"文档删除完成: {doc_id}, {count} 个块")
        return True
        
    except Exception as e:
        logger.error(f"删除文档失败: {doc_id}, {e}")
        return False

