# -*- coding: utf-8 -*-
"""
ChromaDB 异步任务队列
用于后台同步 SQLite 句段到 ChromaDB 向量库
"""

import threading
import queue
import time
from typing import List, Optional, Callable


class ChromaWorker:
    """ChromaDB 后台同步工作器"""
    
    def __init__(self, tm_db, max_workers: int = 1):
        """
        初始化工作器
        
        Args:
            tm_db: TMDatabase 实例
            max_workers: 后台工作线程数（默认1个，避免资源竞争）
        """
        self.tm_db = tm_db
        self.task_queue = queue.Queue()
        self.workers = []
        self.running = False
        self.max_workers = max_workers
        self._lock = threading.Lock()
        self._stats = {
            "queued": 0,
            "processed": 0,
            "failed": 0,
            "last_task_time": None
        }
    
    def start(self):
        """启动后台工作线程"""
        if self.running:
            return
        
        self.running = True
        for i in range(self.max_workers):
            t = threading.Thread(
                target=self._worker_loop,
                name=f"ChromaWorker-{i}",
                daemon=True
            )
            t.start()
            self.workers.append(t)
        
        print(f"[ChromaWorker] 启动 {self.max_workers} 个后台工作线程")
    
    def stop(self):
        """停止后台工作线程"""
        self.running = False
        # 发送空任务唤醒等待的线程
        for _ in self.workers:
            self.task_queue.put(None)
        
        for t in self.workers:
            t.join(timeout=5)
        
        self.workers.clear()
        print("[ChromaWorker] 已停止")
    
    def submit(self, segment_ids: List[int], callback: Optional[Callable] = None):
        """
        提交同步任务到队列
        
        Args:
            segment_ids: 需要同步到 ChromaDB 的句段 ID 列表
            callback: 完成后的回调函数 (synced_count) -> None
        """
        if not segment_ids:
            return
        
        with self._lock:
            self._stats["queued"] += len(segment_ids)
        
        self.task_queue.put({
            "segment_ids": segment_ids,
            "callback": callback
        })
        
        print(f"[ChromaWorker] 提交任务: {len(segment_ids)} 个句段待同步")
    
    def _worker_loop(self):
        """工作线程主循环"""
        while self.running:
            try:
                task = self.task_queue.get(timeout=1)
                if task is None:
                    break
                
                self._process_task(task)
                self.task_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[ChromaWorker] 工作线程异常: {e}")
    
    def _process_task(self, task: dict):
        """处理单个同步任务"""
        segment_ids = task["segment_ids"]
        callback = task.get("callback")
        
        try:
            print(f"[ChromaWorker] 开始同步 {len(segment_ids)} 个句段到 ChromaDB...")
            start_time = time.time()
            
            synced = self.tm_db.sync_to_chroma(segment_ids)
            elapsed = time.time() - start_time
            
            with self._lock:
                self._stats["processed"] += synced
                self._stats["last_task_time"] = elapsed
            
            print(f"[ChromaWorker] 同步完成: {synced}/{len(segment_ids)} 个句段, 耗时 {elapsed:.2f}s")
            
            if callback:
                try:
                    callback(synced)
                except Exception as e:
                    print(f"[ChromaWorker] 回调执行失败: {e}")
                    
        except Exception as e:
            print(f"[ChromaWorker] 同步任务失败: {e}")
            with self._lock:
                self._stats["failed"] += len(segment_ids)
    
    def get_stats(self) -> dict:
        """获取队列统计信息"""
        with self._lock:
            return {
                "queued_total": self._stats["queued"],
                "processed": self._stats["processed"],
                "failed": self._stats["failed"],
                "pending": self.task_queue.qsize(),
                "last_task_time": self._stats["last_task_time"]
            }


# 全局工作器实例（单例模式）
_chroma_worker: Optional[ChromaWorker] = None


def get_chroma_worker(tm_db=None) -> Optional[ChromaWorker]:
    """
    获取全局 ChromaWorker 实例
    
    Args:
        tm_db: TMDatabase 实例（首次调用时需要）
        
    Returns:
        ChromaWorker 实例或 None
    """
    global _chroma_worker
    
    if _chroma_worker is None and tm_db is not None:
        _chroma_worker = ChromaWorker(tm_db)
        _chroma_worker.start()
    
    return _chroma_worker


def shutdown_chroma_worker():
    """关闭全局工作器"""
    global _chroma_worker
    if _chroma_worker:
        _chroma_worker.stop()
        _chroma_worker = None
