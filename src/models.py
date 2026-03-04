"""数据库模型 - SQLAlchemy"""

import hashlib
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from config import config
from logger import logger

Base = declarative_base()


class Document(Base):
    """文档元数据表"""
    __tablename__ = "documents"
    
    id = Column(String, primary_key=True)  # MD5 hash of file_path
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False, unique=True)
    file_size = Column(Integer, default=0)
    file_type = Column(String)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    chunk_count = Column(Integer, default=0)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AdminUser(Base):
    """管理员用户表（单管理员模式）"""
    __tablename__ = "admin_user"
    
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)  # bcrypt hash
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)


class Database:
    """数据库管理类"""
    
    def __init__(self):
        self._engine = None
        self._session_maker = None
        self._initialized = False
    
    def initialize(self) -> None:
        """初始化数据库连接"""
        if self._initialized:
            return
        
        # 使用 SQLite 作为数据库
        db_path = config.persist_directory + "/app.db"
        self._engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False}
        )
        
        # 创建表
        Base.metadata.create_all(self._engine)
        self._session_maker = sessionmaker(bind=self._engine)
        
        # 初始化管理员账号
        self._init_admin_user()
        
        self._initialized = True
        logger.info(f"数据库初始化完成: {db_path}")
    
    def _init_admin_user(self) -> None:
        """初始化管理员账号"""
        import bcrypt
        session = self._session_maker()
        
        try:
            # 检查是否已存在管理员
            admin = session.query(AdminUser).filter(
                AdminUser.username == config.auth_admin_username
            ).first()
            
            if not admin:
                # 创建管理员账号
                password = config.auth_admin_password.encode('utf-8')
                password_hash = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')
                admin = AdminUser(
                    username=config.auth_admin_username,
                    password_hash=password_hash
                )
                session.add(admin)
                session.commit()
                logger.info(f"管理员账号已创建: {config.auth_admin_username}")
        except Exception as e:
            logger.error(f"初始化管理员账号失败: {e}")
            session.rollback()
        finally:
            session.close()
    
    def get_session(self) -> Session:
        """获取数据库会话"""
        if not self._initialized:
            self.initialize()
        return self._session_maker()
    
    def verify_admin(self, username: str, password: str) -> bool:
        """验证管理员账号密码"""
        import bcrypt
        session = self.get_session()
        
        try:
            admin = session.query(AdminUser).filter(
                AdminUser.username == username
            ).first()
            
            if admin:
                password_bytes = password.encode('utf-8')
                hash_bytes = admin.password_hash.encode('utf-8')
                if bcrypt.checkpw(password_bytes, hash_bytes):
                    # 更新最后登录时间
                    admin.last_login = datetime.utcnow()
                    session.commit()
                    return True
            return False
        finally:
            session.close()


# 全局数据库实例
database = Database()
