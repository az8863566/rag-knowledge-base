"""配置模块：加载和管理 config.yaml 配置"""

import os
from pathlib import Path
from typing import Any

import yaml

from logger import logger


class ConfigError(Exception):
    """配置错误异常"""
    pass


class Config:
    """配置管理类"""

    _instance = None
    _config: dict = {}
    _loaded: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self, config_path: str | None = None) -> None:
        """加载配置文件"""
        if config_path is None:
            # 优先检查 Docker 环境路径，然后是项目根目录
            docker_path = Path("/app/config.yaml")
            local_path = Path(__file__).parent.parent / "config.yaml"
            
            if docker_path.exists():
                config_path = docker_path
            else:
                config_path = local_path
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            raise ConfigError(
                f"配置文件不存在: {config_path}\n"
                "请复制 config.yaml.example 为 config.yaml 并填入 API Key"
            )

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ConfigError(f"配置文件格式错误: {e}")

        self._validate()
        self._loaded = True
        logger.info(f"配置加载成功: {config_path}")

    def _validate(self) -> None:
        """验证必填配置项"""
        api_key = self.get("siliconflow.api_key", "")
        if not api_key or api_key == "sk-your-api-key-here":
            raise ConfigError("请在 config.yaml 中配置有效的 siliconflow.api_key")
        
        # 验证数值类型配置
        batch_size = self.get("embedding.batch_size", 500)
        if not isinstance(batch_size, int) or batch_size <= 0:
            raise ConfigError("embedding.batch_size 必须是正整数")
        
        chunk_size = self.get("text_splitting.chunk_size", 800)
        if not isinstance(chunk_size, int) or chunk_size <= 0:
            raise ConfigError("text_splitting.chunk_size 必须是正整数")
        
        chunk_overlap = self.get("text_splitting.chunk_overlap", 100)
        if not isinstance(chunk_overlap, int) or chunk_overlap < 0:
            raise ConfigError("text_splitting.chunk_overlap 必须是非负整数")
        
        if chunk_overlap >= chunk_size:
            raise ConfigError("text_splitting.chunk_overlap 必须小于 chunk_size")

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值，支持点号分隔的嵌套键
        例如: config.get("siliconflow.api_key")
        """
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    @property
    def is_loaded(self) -> bool:
        """检查配置是否已加载"""
        return self._loaded

    @property
    def siliconflow_api_key(self) -> str:
        return self.get("siliconflow.api_key", "")

    @property
    def siliconflow_base_url(self) -> str:
        return self.get("siliconflow.base_url", "https://api.siliconflow.cn/v1")

    @property
    def embedding_model(self) -> str:
        return self.get("embedding.model", "BAAI/bge-m3")

    @property
    def embedding_batch_size(self) -> int:
        return self.get("embedding.batch_size", 500)

    @property
    def reranking_model(self) -> str:
        return self.get("reranking.model", "BAAI/bge-reranker-v2-m3")

    @property
    def reranking_top_k(self) -> int:
        return self.get("reranking.top_k", 10)

    @property
    def chunk_size(self) -> int:
        return self.get("text_splitting.chunk_size", 800)

    @property
    def chunk_overlap(self) -> int:
        return self.get("text_splitting.chunk_overlap", 100)

    @property
    def persist_directory(self) -> str:
        return self.get("vectorstore.persist_directory", "./faiss_data")

    @property
    def collection_name(self) -> str:
        return self.get("vectorstore.collection_name", "knowledge_base")

    @property
    def retrieval_initial_k(self) -> int:
        return self.get("retrieval.initial_k", 100)

    @property
    def retrieval_similarity_threshold(self) -> float:
        """获取检索相似度阈值，低于此值认为未命中"""
        threshold = self.get("retrieval.similarity_threshold", 0.8)
        # 确保值在 0-1 范围内
        if not isinstance(threshold, (int, float)) or threshold < 0 or threshold > 1:
            logger.warning(f"similarity_threshold 值无效，使用默认值 0.8")
            return 0.8
        return float(threshold)

    @property
    def mcp_name(self) -> str:
        return self.get("mcp.name", "RAG Knowledge Base")

    @property
    def mcp_host(self) -> str:
        return self.get("mcp.host", "0.0.0.0")

    @property
    def mcp_port(self) -> int:
        return self.get("mcp.port", 8001)

    @property
    def mcp_transport(self) -> str:
        return self.get("mcp.transport", "stdio")

    # API 服务配置
    @property
    def api_host(self) -> str:
        return self.get("api.host", "0.0.0.0")

    @property
    def api_port(self) -> int:
        return self.get("api.port", 8000)

    @property
    def api_upload_dir(self) -> str:
        return self.get("api.upload_dir", "./uploads")

    @property
    def api_max_file_size(self) -> int:
        size_str = self.get("api.max_file_size", "50MB")
        # 解析文件大小字符串 (如 "50MB" -> 52428800)
        size_str = size_str.upper().strip()
        # 按长度从长到短检查，避免 "MB" 被误匹配为 "B"
        multipliers = [("GB", 1024**3), ("MB", 1024**2), ("KB", 1024), ("B", 1)]
        for suffix, multiplier in multipliers:
            if size_str.endswith(suffix):
                return int(size_str[:-len(suffix)]) * multiplier
        return int(size_str)

    @property
    def api_secret_key(self) -> str:
        return self.get("api.secret_key", "your-secret-key-change-in-production")

    # 认证配置
    @property
    def auth_admin_username(self) -> str:
        return self.get("auth.admin_username", "admin")

    @property
    def auth_admin_password(self) -> str:
        return self.get("auth.admin_password", "admin123")

    @property
    def auth_token_expire_hours(self) -> int:
        return self.get("auth.token_expire_hours", 24)


# 全局配置实例
config = Config()
