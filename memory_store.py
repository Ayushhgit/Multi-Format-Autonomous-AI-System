"""
Memory Store - Shared memory system using SQLite with Redis fallback
Stores logs, traces, and processing results
"""

import os
import json
import sqlite3
import redis
from datetime import datetime
from typing import Dict, Any, List, Optional
from contextlib import contextmanager

class MemoryStore:
    def __init__(self):
        self.use_redis = os.getenv("USE_REDIS", "false").lower() == "true"
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        
        if self.use_redis:
            try:
                self.redis_client = redis.from_url(self.redis_url)
                self.redis_client.ping()
                print("Connected to Redis")
            except Exception as e:
                print(f"Redis connection failed: {e}. Falling back to SQLite.")
                self.use_redis = False
        
        if not self.use_redis:
            self._init_sqlite()
    
    def _init_sqlite(self):
        """Initialize SQLite database"""
        self.db_path = "memory_store.db"
        
        with self._get_db_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS traces (
                    trace_id TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    format TEXT,
                    status TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trace_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    data TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (trace_id) REFERENCES traces (trace_id)
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_logs_trace_id ON logs(trace_id)
            """)
            
            conn.commit()
    
    @contextmanager
    def _get_db_connection(self):
        """Context manager for SQLite connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def store_log(self, trace_id: str, data: Dict[str, Any]):
        """Store a log entry for a trace"""
        if self.use_redis:
            self._store_log_redis(trace_id, data)
        else:
            self._store_log_sqlite(trace_id, data)
    
    def _store_log_redis(self, trace_id: str, data: Dict[str, Any]):
        """Store log in Redis"""
        try:
            # Store in a Redis list for the trace
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                **data
            }
            self.redis_client.lpush(f"trace:{trace_id}", json.dumps(log_entry))
            
            # Set expiration (7 days)
            self.redis_client.expire(f"trace:{trace_id}", 604800)
            
            # Add to trace list
            self.redis_client.sadd("traces", trace_id)
            
        except Exception as e:
            print(f"Redis store error: {e}")
            # Fallback to SQLite
            self.use_redis = False
            self._init_sqlite()
            self._store_log_sqlite(trace_id, data)
    
    def _store_log_sqlite(self, trace_id: str, data: Dict[str, Any]):
        """Store log in SQLite"""
        with self._get_db_connection() as conn:
            # Ensure trace exists
            conn.execute(
                "INSERT OR IGNORE INTO traces (trace_id) VALUES (?)",
                (trace_id,)
            )
            
            # Store log entry
            conn.execute(
                """INSERT INTO logs (trace_id, stage, data) 
                   VALUES (?, ?, ?)""",
                (trace_id, data.get("stage", "unknown"), json.dumps(data))
            )
            
            # Update trace timestamp, format, and status if it's a completion log
            if data.get("stage") == "completion":
                result_data = data.get("result", {})
                conn.execute(
                    "UPDATE traces SET updated_at = CURRENT_TIMESTAMP, format = ?, status = ? WHERE trace_id = ?",
                    (result_data.get("format"), result_data.get("status"), trace_id)
                )
            else:
                 # Update trace timestamp
                conn.execute(
                    "UPDATE traces SET updated_at = CURRENT_TIMESTAMP WHERE trace_id = ?",
                    (trace_id,)
                )
            
            conn.commit()
    
    def get_trace(self, trace_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get complete trace for a trace_id"""
        if self.use_redis:
            return self._get_trace_redis(trace_id)
        else:
            return self._get_trace_sqlite(trace_id)
    
    def _get_trace_redis(self, trace_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get trace from Redis"""
        try:
            logs = self.redis_client.lrange(f"trace:{trace_id}", 0, -1)
            if not logs:
                return None
            
            # Reverse to get chronological order and find completion log
            for log in reversed(logs):
                log_entry = json.loads(log.decode('utf-8'))
                if log_entry.get("stage") == "completion":
                    return log_entry.get("result")
                    
            return None # No completion log found
            
        except Exception as e:
            print(f"Redis get error: {e}")
            return None
    
    def _get_trace_sqlite(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Get trace from SQLite - return final result"""
        with self._get_db_connection() as conn:
            cursor = conn.execute(
                """SELECT data FROM logs 
                   WHERE trace_id = ? AND stage = 'completion'""",
                (trace_id,)
            )
            
            row = cursor.fetchone()
            if not row:
                return None
            
            # Return the result data from the completion log
            completion_data = json.loads(row['data'])
            return completion_data.get('result')
    
    def list_traces(self, limit: int = 100) -> List[str]:
        """List all available traces"""
        if self.use_redis:
            return self._list_traces_redis(limit)
        else:
            return self._list_traces_sqlite(limit)
    
    def _list_traces_redis(self, limit: int) -> List[str]:
        """List traces from Redis"""
        try:
            traces = self.redis_client.smembers("traces")
            return [trace.decode('utf-8') for trace in traces][:limit]
        except Exception as e:
            print(f"Redis list error: {e}")
            return []
    
    def _list_traces_sqlite(self, limit: int) -> List[Dict[str, Any]]:
        """List traces from SQLite"""
        with self._get_db_connection() as conn:
            cursor = conn.execute(
                "SELECT trace_id, format, status, updated_at FROM traces ORDER BY updated_at DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        if self.use_redis:
            return self._get_stats_redis()
        else:
            return self._get_stats_sqlite()
    
    def _get_stats_redis(self) -> Dict[str, Any]:
        """Get stats from Redis"""
        try:
            trace_count = self.redis_client.scard("traces")
            return {
                "storage_type": "redis",
                "total_traces": trace_count,
                "redis_info": self.redis_client.info()
            }
        except Exception as e:
            return {"storage_type": "redis", "error": str(e)}
    
    def _get_stats_sqlite(self) -> Dict[str, Any]:
        """Get stats from SQLite"""
        with self._get_db_connection() as conn:
            trace_count = conn.execute("SELECT COUNT(*) FROM traces").fetchone()[0]
            log_count = conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
            
            return {
                "storage_type": "sqlite",
                "total_traces": trace_count,
                "total_logs": log_count,
                "db_path": self.db_path
            }
    
    def clear_old_traces(self, days: int = 7):
        """Clear traces older than specified days"""
        if self.use_redis:
            # Redis handles expiration automatically
            pass
        else:
            with self._get_db_connection() as conn:
                conn.execute(
                    """DELETE FROM logs WHERE trace_id IN (
                        SELECT trace_id FROM traces 
                        WHERE updated_at < datetime('now', '-{} days')
                    )""".format(days)
                )
                
                conn.execute(
                    "DELETE FROM traces WHERE updated_at < datetime('now', '-{} days')".format(days)
                )
                
                conn.commit()