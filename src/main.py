"""RAG 知识库 MCP Server 主入口"""

import sys
from pathlib import Path

# 将 src 目录添加到路径
sys.path.insert(0, str(Path(__file__).parent))

from fastmcp import FastMCP

from config import config, ConfigError
from logger import logger
from siliconflow_client import siliconflow_client, SiliconFlowError
from vectorstore import vectorstore, VectorStoreError
from text_splitter import split_text, TextSplitterError
from parsers import parse_file, get_supported_extensions, ParserError


def main():
    """主入口函数"""
    try:
        # 加载配置
        config.load()
        logger.info(f"MCP Server 名称: {config.mcp_name}")
        
        # 初始化 FAISS 向量存储
        vectorstore.initialize()
        
        # 创建 MCP Server
        mcp = FastMCP(config.mcp_name)
        
        @mcp.tool(name="ingest", description="导入本地文档到知识库")
        def ingest(file_path: str) -> dict:
            """
            将本地文档导入知识库
            
            支持的文件格式: .txt, .md, .pdf, .docx, .html, .csv, .json, .xlsx
            
            Args:
                file_path: 本地文件的绝对路径或相对路径
                
            Returns:
                导入结果，包含状态和插入的文档块数量
            """
            try:
                if not file_path or not file_path.strip():
                    return {"status": "error", "message": "文件路径不能为空"}
                
                # 解析文件
                text = parse_file(file_path)
                
                if not text or not text.strip():
                    return {"status": "error", "message": "文件内容为空"}
                
                # 分块
                chunks = split_text(text)
                
                if not chunks:
                    return {"status": "error", "message": "文本分块失败：无法生成有效的文本块"}
                
                # 嵌入
                embeddings = siliconflow_client.embed_texts(chunks)
                
                if len(embeddings) != len(chunks):
                    return {"status": "error", "message": f"嵌入向量数量不匹配：期望 {len(chunks)}，实际 {len(embeddings)}"}
                
                # 存储
                count = vectorstore.add_documents(chunks, embeddings, file_path)
                
                logger.info(f"文档导入成功: {file_path}, {count} 个块")
                return {
                    "status": "ok",
                    "file": file_path,
                    "chunks_inserted": count,
                    "message": f"成功导入 {count} 个文档块",
                }
                
            except FileNotFoundError as e:
                logger.error(f"文件不存在: {file_path}")
                return {"status": "error", "message": f"文件不存在: {file_path}"}
            except ParserError as e:
                logger.error(f"文件解析失败: {e}")
                return {"status": "error", "message": str(e)}
            except TextSplitterError as e:
                logger.error(f"文本分块失败: {e}")
                return {"status": "error", "message": str(e)}
            except SiliconFlowError as e:
                logger.error(f"API 调用失败: {e}")
                return {"status": "error", "message": str(e)}
            except VectorStoreError as e:
                logger.error(f"向量存储失败: {e}")
                return {"status": "error", "message": str(e)}
            except Exception as e:
                logger.error(f"导入失败: {e}")
                return {"status": "error", "message": f"导入失败: {str(e)}"}


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


        @mcp.tool(name="get_supported_formats", description="获取支持的文件格式列表")
        def get_supported_formats() -> dict:
            """
            获取知识库支持导入的文件格式
            
            Returns:
                支持的文件扩展名列表
            """
            return {
                "supported_formats": get_supported_extensions(),
                "description": "使用 ingest 工具导入这些格式的文件",
            }


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


        @mcp.tool(name="delete_document", description="从知识库中删除指定文档")
        def delete_document(file_path: str) -> dict:
            """
            根据文件路径删除知识库中的文档
            
            Args:
                file_path: 要删除的文档路径（与导入时使用的路径一致）
                
            Returns:
                删除结果，包含删除的文档块数量
            """
            try:
                if not file_path or not file_path.strip():
                    return {"status": "error", "message": "文件路径不能为空"}
                
                count = vectorstore.delete_by_file_path(file_path)
                if count > 0:
                    logger.info(f"文档删除成功: {file_path}, {count} 个块")
                    return {
                        "status": "ok",
                        "file": file_path,
                        "chunks_deleted": count,
                        "message": f"成功删除 {count} 个文档块",
                    }
                else:
                    return {
                        "status": "warning",
                        "file": file_path,
                        "message": "未找到该文档，可能已被删除或从未导入",
                    }
            except VectorStoreError as e:
                logger.error(f"删除文档失败: {e}")
                return {"status": "error", "message": f"删除失败: {str(e)}"}


        @mcp.tool(name="clear_knowledge_base", description="清空整个知识库（危险操作）")
        def clear_knowledge_base(confirm: bool = False) -> dict:
            """
            清空知识库中的所有文档（此操作不可恢复）
            
            Args:
                confirm: 确认清空，必须设置为 true 才会执行
                
            Returns:
                操作结果
            """
            if not confirm:
                return {
                    "status": "error",
                    "message": "危险操作！请设置 confirm=true 确认清空知识库",
                }
            
            try:
                stats_before = vectorstore.get_stats()
                total_chunks = stats_before.get("total_chunks", 0)
                
                vectorstore.clear()
                logger.warning(f"知识库已清空，共删除 {total_chunks} 个文档块")
                
                return {
                    "status": "ok",
                    "message": f"知识库已清空，共删除 {total_chunks} 个文档块",
                }
            except VectorStoreError as e:
                logger.error(f"清空知识库失败: {e}")
                return {"status": "error", "message": f"清空失败: {str(e)}"}


        @mcp.tool(name="update_document", description="更新知识库中的文档（删除旧版本并重新导入）")
        def update_document(file_path: str) -> dict:
            """
            更新知识库中的文档。如果文档已存在则先删除旧版本，然后重新导入。
            
            Args:
                file_path: 要更新的文档路径
                
            Returns:
                更新结果
            """
            try:
                if not file_path or not file_path.strip():
                    return {"status": "error", "message": "文件路径不能为空"}
                
                # 先删除旧版本
                deleted_count = vectorstore.delete_by_file_path(file_path)
                
                # 重新导入
                text = parse_file(file_path)
                
                if not text or not text.strip():
                    return {"status": "error", "message": "文件内容为空"}
                
                chunks = split_text(text)
                
                if not chunks:
                    return {"status": "error", "message": "文本分块失败：无法生成有效的文本块"}
                
                embeddings = siliconflow_client.embed_texts(chunks)
                count = vectorstore.add_documents(chunks, embeddings, file_path)
                
                if deleted_count > 0:
                    message = f"成功更新文档，删除旧版本 {deleted_count} 个块，导入新版本 {count} 个块"
                else:
                    message = f"成功导入新文档，共 {count} 个文档块"
                
                logger.info(f"文档更新成功: {file_path}")
                return {
                    "status": "ok",
                    "file": file_path,
                    "chunks_inserted": count,
                    "chunks_deleted": deleted_count,
                    "message": message,
                }
                
            except FileNotFoundError:
                logger.error(f"文件不存在: {file_path}")
                return {"status": "error", "message": f"文件不存在: {file_path}"}
            except ParserError as e:
                logger.error(f"文件解析失败: {e}")
                return {"status": "error", "message": str(e)}
            except TextSplitterError as e:
                logger.error(f"文本分块失败: {e}")
                return {"status": "error", "message": str(e)}
            except SiliconFlowError as e:
                logger.error(f"API 调用失败: {e}")
                return {"status": "error", "message": str(e)}
            except VectorStoreError as e:
                logger.error(f"向量存储失败: {e}")
                return {"status": "error", "message": str(e)}
            except Exception as e:
                logger.error(f"更新失败: {e}")
                return {"status": "error", "message": f"更新失败: {str(e)}"}


        # 启动 MCP Server
        logger.info("MCP Server 启动中...")
        mcp.run()
        
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
