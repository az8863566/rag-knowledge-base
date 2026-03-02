"""FastAPI 后端服务 - 提供文档管理和认证功能"""

import sys
import hashlib
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException, status, Query
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import config, ConfigError
from logger import logger
from vectorstore import vectorstore, VectorStoreError
from models import database, Document
from auth import create_access_token, verify_token, get_current_user, security
from tasks import task_manager, process_document, delete_document_task
from parsers import get_supported_extensions

# 创建 FastAPI 应用
app = FastAPI(
    title="RAG Knowledge Base API",
    description="RAG 知识库管理 API",
    version="1.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 确保上传目录存在
UPLOAD_DIR = Path(config.api_upload_dir)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 支持的文件扩展名
SUPPORTED_EXTENSIONS = set(get_supported_extensions())


# ============ Pydantic 模型 ============

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class DocumentResponse(BaseModel):
    id: str
    file_name: str
    file_path: str
    file_size: int
    file_type: str
    status: str
    chunk_count: int
    error_message: Optional[str]
    created_at: str
    updated_at: str


class DocumentListResponse(BaseModel):
    total: int
    documents: List[DocumentResponse]


class TaskStatusResponse(BaseModel):
    doc_id: str
    file_name: str
    status: str
    progress: int
    message: str
    chunk_count: int
    error_message: Optional[str]


class StatsResponse(BaseModel):
    total_chunks: int
    total_vectors: int
    total_documents: int
    collection_name: str


class MessageResponse(BaseModel):
    message: str


# ============ 认证接口 ============

@app.post("/api/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """管理员登录"""
    if not database.verify_admin(request.username, request.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    
    # 创建 JWT 令牌
    access_token = create_access_token(
        data={"sub": request.username}
    )
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=config.auth_token_expire_hours * 3600
    )


@app.get("/api/auth/verify")
async def verify(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """验证令牌有效性"""
    username = get_current_user(credentials)
    return {"valid": True, "username": username}


# ============ 文档管理接口 ============

@app.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """上传文档"""
    get_current_user(credentials)  # 验证用户
    
    # 检查文件类型
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型: {file_ext}"
        )
    
    # 检查文件大小
    contents = await file.read()
    if len(contents) > config.api_max_file_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件大小超过限制: {config.api_max_file_size / 1024 / 1024:.0f}MB"
        )
    
    # 生成文档ID
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{timestamp}_{file.filename}"
    file_path = UPLOAD_DIR / safe_filename
    
    # 保存文件
    with open(file_path, "wb") as f:
        f.write(contents)
    
    # 生成文档ID (MD5 of file path)
    doc_id = hashlib.md5(str(file_path).encode()).hexdigest()[:12]
    
    # 保存到数据库
    session = database.get_session()
    try:
        doc = Document(
            id=doc_id,
            file_name=file.filename,
            file_path=str(file_path),
            file_size=len(contents),
            file_type=file_ext,
            status="pending"
        )
        session.add(doc)
        session.commit()
    except Exception as e:
        session.rollback()
        file_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"保存文档信息失败: {str(e)}"
        )
    finally:
        session.close()
    
    # 创建异步处理任务
    import asyncio
    asyncio.create_task(process_document(str(file_path), doc_id))
    
    logger.info(f"文档上传成功: {file.filename}, doc_id={doc_id}")
    
    return {
        "status": "ok",
        "doc_id": doc_id,
        "file_name": file.filename,
        "message": "文档已上传，正在处理中"
    }


@app.get("/api/documents", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """获取文档列表"""
    get_current_user(credentials)
    
    session = database.get_session()
    try:
        query = session.query(Document)
        
        if status:
            query = query.filter(Document.status == status)
        
        total = query.count()
        
        # 分页
        offset = (page - 1) * page_size
        docs = query.order_by(Document.created_at.desc()).offset(offset).limit(page_size).all()
        
        documents = [
            DocumentResponse(
                id=doc.id,
                file_name=doc.file_name,
                file_path=doc.file_path,
                file_size=doc.file_size,
                file_type=doc.file_type,
                status=doc.status,
                chunk_count=doc.chunk_count,
                error_message=doc.error_message,
                created_at=doc.created_at.isoformat() if doc.created_at else "",
                updated_at=doc.updated_at.isoformat() if doc.updated_at else ""
            )
            for doc in docs
        ]
        
        return DocumentListResponse(total=total, documents=documents)
    finally:
        session.close()


@app.get("/api/documents/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """获取单个文档信息"""
    get_current_user(credentials)
    
    session = database.get_session()
    try:
        doc = session.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在"
            )
        
        return DocumentResponse(
            id=doc.id,
            file_name=doc.file_name,
            file_path=doc.file_path,
            file_size=doc.file_size,
            file_type=doc.file_type,
            status=doc.status,
            chunk_count=doc.chunk_count,
            error_message=doc.error_message,
            created_at=doc.created_at.isoformat() if doc.created_at else "",
            updated_at=doc.updated_at.isoformat() if doc.updated_at else ""
        )
    finally:
        session.close()


@app.get("/api/documents/{doc_id}/status", response_model=TaskStatusResponse)
async def get_document_status(
    doc_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """获取文档处理状态"""
    get_current_user(credentials)
    
    # 先检查任务管理器
    task = task_manager.get_task(doc_id)
    if task:
        return TaskStatusResponse(
            doc_id=task.doc_id,
            file_name=task.file_name,
            status=task.status,
            progress=task.progress,
            message=task.message,
            chunk_count=task.chunk_count,
            error_message=task.error_message
        )
    
    # 从数据库获取
    session = database.get_session()
    try:
        doc = session.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在"
            )
        
        return TaskStatusResponse(
            doc_id=doc.id,
            file_name=doc.file_name,
            status=doc.status,
            progress=100 if doc.status == "completed" else 0,
            message="处理完成" if doc.status == "completed" else doc.error_message or "",
            chunk_count=doc.chunk_count,
            error_message=doc.error_message
        )
    finally:
        session.close()


@app.delete("/api/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """删除文档"""
    get_current_user(credentials)
    
    session = database.get_session()
    try:
        doc = session.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在"
            )
        
        # 删除物理文件
        file_path = Path(doc.file_path)
        if file_path.exists():
            file_path.unlink()
        
        # 从向量库和数据库删除
        import asyncio
        await delete_document_task(doc_id)
        
        return {"status": "ok", "message": "文档已删除"}
    finally:
        session.close()


# ============ 统计接口 ============

@app.get("/api/stats", response_model=StatsResponse)
async def get_stats(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """获取统计信息"""
    get_current_user(credentials)
    
    try:
        stats = vectorstore.get_stats()
        
        session = database.get_session()
        try:
            total_docs = session.query(Document).count()
        finally:
            session.close()
        
        return StatsResponse(
            total_chunks=stats.get("total_chunks", 0),
            total_vectors=stats.get("total_vectors", 0),
            total_documents=total_docs,
            collection_name=stats.get("collection_name", "")
        )
    except VectorStoreError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取统计信息失败: {str(e)}"
        )


@app.get("/api/formats")
async def get_formats(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """获取支持的文件格式"""
    get_current_user(credentials)
    
    return {
        "supported_formats": list(SUPPORTED_EXTENSIONS),
        "max_file_size": config.api_max_file_size
    }


# ============ 前端静态文件 ============

# 挂载前端静态文件（如果存在）
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


# ============ 启动入口 ============

def main():
    """API Server 主入口"""
    try:
        # 加载配置
        config.load()
        logger.info(f"API Server 配置加载成功")
        
        # 初始化数据库
        database.initialize()
        
        # 初始化向量存储
        vectorstore.initialize()
        
        # 启动服务
        import uvicorn
        logger.info(f"API Server 启动中... {config.api_host}:{config.api_port}")
        uvicorn.run(
            app,
            host=config.api_host,
            port=config.api_port,
            log_level="info"
        )
        
    except ConfigError as e:
        logger.error(f"配置错误: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
