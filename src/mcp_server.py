"""MCP StreamHTTP Server - 仅提供查询功能"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastmcp import FastMCP

from config import config, ConfigError
from logger import logger
from siliconflow_client import siliconflow_client, SiliconFlowError
from vectorstore import vectorstore, VectorStoreError


def main():
    """MCP HTTP Server 主入口"""
    try:
        config.load()
        logger.info(f"MCP Server 名称: {config.mcp_name}")
        
        # 初始化 FAISS 向量存储
        vectorstore.initialize()
        
        # 创建 MCP Server
        mcp = FastMCP(config.mcp_name)
        
        @mcp.tool(name="retrieve", description="从知识库检索相关文档")
        def retrieve(query: str) -> str:
            """
            根据查询语义检索知识库中的相关文档
            
            使用 BAAI/bge-m3 进行语义嵌入，BAAI/bge-reranker-v2-m3 进行重排序
            
            Args:
                query: 查询问题或关键词
                
            Returns:
                检索到的相关文档内容（按相关性排序）
            """
            try:
                if not query or not query.strip():
                    return "查询内容不能为空"
                
                # 嵌入查询
                query_embedding = siliconflow_client.embed_texts([query])[0]
                
                # 向量检索
                results = vectorstore.query(query_embedding)
                
                documents = results["documents"]
                metadatas = results["metadatas"]
                
                if not documents:
                    return "知识库中没有找到相关文档"
                
                # 重排序
                rerank_results = siliconflow_client.rerank(query, documents)
                
                # 检查相似度阈值
                similarity_threshold = config.retrieval_similarity_threshold
                if rerank_results:
                    max_score = max(item["relevance_score"] for item in rerank_results)
                    if max_score < similarity_threshold:
                        logger.info(f"检索结果最高得分 {max_score:.4f} 低于阈值 {similarity_threshold}")
                        return "当前知识库并未有相关知识文档"
                
                # 格式化输出（只输出高于阈值的结果）
                output_parts = []
                for item in rerank_results:
                    idx = item["index"]
                    score = item["relevance_score"]
                    
                    # 跳过低于阈值的结果
                    if score < similarity_threshold:
                        continue
                    
                    doc_text = documents[idx]
                    meta = metadatas[idx]
                    
                    chunk_id = f"{meta.get('doc_id', 'unknown')}_{meta.get('chunk_index', '?')}"
                    file_name = meta.get("file_name", "unknown")
                    
                    output_parts.append(
                        f"[{chunk_id}] (来源: {file_name}, 相关度: {score:.4f})\n{doc_text}"
                    )
                
                logger.info(f"检索完成: query='{query[:50]}...', 结果数={len(output_parts)}")
                return "\n\n---\n\n".join(output_parts)
                
            except SiliconFlowError as e:
                logger.error(f"检索失败: {e}")
                return f"检索失败: {str(e)}"
            except VectorStoreError as e:
                logger.error(f"检索失败: {e}")
                return f"检索失败: {str(e)}"
            except Exception as e:
                logger.error(f"检索失败: {e}")
                return f"检索失败: {str(e)}"


        @mcp.tool(name="get_stats", description="获取知识库统计信息")
        def get_stats() -> dict:
            """
            获取知识库当前状态统计
            
            Returns:
                统计信息，包含文档块总数等
            """
            try:
                return vectorstore.get_stats()
            except VectorStoreError as e:
                logger.error(f"获取统计信息失败: {e}")
                return {"total_chunks": 0, "error": str(e)}


        @mcp.tool(name="list_documents", description="列出知识库中所有已导入的文档")
        def list_documents() -> dict:
            """
            获取知识库中所有已导入的文档列表
            
            Returns:
                文档列表，包含文件名、文档ID、块数量、导入时间等信息
            """
            try:
                docs = vectorstore.list_documents()
                return {
                    "status": "ok",
                    "total_documents": len(docs),
                    "documents": docs,
                }
            except VectorStoreError as e:
                logger.error(f"获取文档列表失败: {e}")
                return {"status": "error", "message": f"获取文档列表失败: {str(e)}"}


        # 启动 MCP HTTP Server
        logger.info(f"MCP HTTP Server 启动中... {config.mcp_host}:{config.mcp_port}")
        mcp.run(transport="http", host=config.mcp_host, port=config.mcp_port)
        
    except ConfigError as e:
        logger.error(f"配置错误: {e}")
        sys.exit(1)
    except VectorStoreError as e:
        logger.error(f"向量存储初始化失败: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
