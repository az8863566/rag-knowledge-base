"""硅基流动 API 客户端：嵌入和重排序"""

import time
from typing import Any

import requests

from config import config
from logger import logger


class SiliconFlowError(Exception):
    """硅基流动 API 错误"""
    pass


class SiliconFlowClient:
    """硅基流动 API 客户端"""

    @property
    def api_key(self) -> str:
        return config.siliconflow_api_key

    @property
    def base_url(self) -> str:
        return config.siliconflow_base_url

    @property
    def embedding_model(self) -> str:
        return config.embedding_model

    @property
    def reranking_model(self) -> str:
        return config.reranking_model

    @property
    def batch_size(self) -> int:
        return config.embedding_batch_size

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _request_with_retry(
        self, url: str, payload: dict, max_retries: int = 3
    ) -> dict:
        """带重试的请求"""
        last_error = None
        for attempt in range(max_retries):
            try:
                resp = requests.post(
                    url, headers=self._get_headers(), json=payload, timeout=60
                )
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 429:
                    # 速率限制，等待后重试
                    wait_time = 2 ** (attempt + 1)
                    logger.warning(f"API 速率限制，等待 {wait_time} 秒后重试")
                    time.sleep(wait_time)
                    continue
                elif resp.status_code == 401:
                    raise SiliconFlowError("API Key 无效或已过期")
                elif resp.status_code == 400:
                    error_detail = resp.text
                    try:
                        error_json = resp.json()
                        error_detail = error_json.get("message", error_detail)
                    except:
                        pass
                    raise SiliconFlowError(f"请求参数错误: {error_detail}")
                else:
                    raise SiliconFlowError(f"API 错误: HTTP {resp.status_code}, {resp.text}")
            except requests.exceptions.Timeout:
                last_error = "请求超时"
                logger.warning(f"API 请求超时，尝试重试 ({attempt + 1}/{max_retries})")
                time.sleep(2 ** attempt)
            except requests.exceptions.ConnectionError as e:
                last_error = f"连接错误: {e}"
                logger.warning(f"API 连接错误，尝试重试 ({attempt + 1}/{max_retries})")
                time.sleep(2 ** attempt)
            except requests.exceptions.RequestException as e:
                last_error = str(e)
                time.sleep(2 ** attempt)

        raise SiliconFlowError(f"API 请求失败（已重试 {max_retries} 次）: {last_error}")

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        批量文本嵌入
        
        Args:
            texts: 待嵌入的文本列表
            
        Returns:
            嵌入向量列表
            
        Raises:
            SiliconFlowError: 嵌入失败时抛出
        """
        if not texts:
            return []

        url = f"{self.base_url}/embeddings"
        all_embeddings: list[list[float]] = []

        # 分批处理，防止超过 token 限制
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            payload = {
                "model": self.embedding_model,
                "input": batch,
                "encoding_format": "float",
            }

            logger.debug(f"嵌入批次 {i // self.batch_size + 1}: {len(batch)} 个文本")
            data = self._request_with_retry(url, payload)
            
            # 验证响应格式
            if "data" not in data:
                raise SiliconFlowError(f"嵌入响应格式错误: 缺少 'data' 字段")
            
            batch_embeddings = []
            for item in data["data"]:
                if "embedding" not in item:
                    raise SiliconFlowError(f"嵌入响应格式错误: 缺少 'embedding' 字段")
                batch_embeddings.append(item["embedding"])
            
            all_embeddings.extend(batch_embeddings)

        logger.info(f"嵌入完成: {len(all_embeddings)} 个向量")
        return all_embeddings

    def rerank(
        self, query: str, documents: list[str], top_k: int | None = None
    ) -> list[dict[str, Any]]:
        """
        文档重排序
        
        Args:
            query: 查询文本
            documents: 候选文档列表
            top_k: 返回前 k 个结果，默认使用配置值
            
        Returns:
            重排序结果列表，每项包含 index, relevance_score, document
            
        Raises:
            SiliconFlowError: 重排序失败时抛出
        """
        if not documents:
            return []

        if not query or not query.strip():
            raise SiliconFlowError("查询文本不能为空")

        if top_k is None:
            top_k = config.reranking_top_k

        url = f"{self.base_url}/rerank"
        payload = {
            "model": self.reranking_model,
            "query": query,
            "documents": documents,
            "top_n": min(top_k, len(documents)),
            "return_documents": True,
        }

        logger.debug(f"重排序: query='{query[:50]}...', documents={len(documents)}, top_k={top_k}")
        data = self._request_with_retry(url, payload)
        
        # 验证响应格式
        results = data.get("results", [])
        if not isinstance(results, list):
            raise SiliconFlowError(f"重排序响应格式错误: 'results' 不是列表")
        
        logger.info(f"重排序完成: 返回 {len(results)} 个结果")
        return results


# 全局客户端实例
siliconflow_client = SiliconFlowClient()
