#!/usr/bin/env python3
"""
Database models and management for Facebook Video Downloader
"""

import sqlite3
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path="facebook_downloader.db"):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Get database connection with proper settings"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        return conn
    
    def init_database(self):
        """Initialize database with required tables"""
        conn = self.get_connection()
        try:
            # Create tables
            self.create_tables(conn)
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
        finally:
            conn.close()
    
    def create_tables(self, conn):
        """Create all required database tables"""
        
        # Scheduled Posts table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS scheduled_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_file_path TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                scheduled_time INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                facebook_video_id TEXT,
                facebook_url TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER DEFAULT (strftime('%s', 'now')),
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                user_id TEXT,
                metadata TEXT
            )
        ''')
        
        # Downloaded Files table  
        conn.execute('''
            CREATE TABLE IF NOT EXISTS downloaded_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL UNIQUE,
                original_url TEXT NOT NULL,
                title TEXT,
                description TEXT,
                file_size INTEGER,
                duration INTEGER,
                thumbnail_path TEXT,
                download_date INTEGER DEFAULT (strftime('%s', 'now')),
                upload_status TEXT DEFAULT 'not_uploaded',
                facebook_video_id TEXT,
                facebook_url TEXT,
                tags TEXT,
                category TEXT,
                metadata TEXT
            )
        ''')
        
        # Upload History table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS upload_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER,
                upload_type TEXT,
                status TEXT,
                started_at INTEGER DEFAULT (strftime('%s', 'now')),
                completed_at INTEGER,
                error_message TEXT,
                facebook_video_id TEXT,
                facebook_url TEXT,
                FOREIGN KEY (file_id) REFERENCES downloaded_files (id)
            )
        ''')
        
        # App Settings table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        ''')
        
        # Analytics Events table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS analytics_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                event_data TEXT,
                timestamp INTEGER DEFAULT (strftime('%s', 'now')),
                session_id TEXT
            )
        ''')
        
        conn.commit()
    
    # Scheduled Posts Methods
    def create_scheduled_post(self, video_file_path, title, description, scheduled_time, user_id=None, metadata=None):
        """Create a new scheduled post"""
        conn = self.get_connection()
        try:
            cursor = conn.execute('''
                INSERT INTO scheduled_posts 
                (video_file_path, title, description, scheduled_time, user_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (video_file_path, title, description, scheduled_time, user_id, json.dumps(metadata) if metadata else None))
            
            post_id = cursor.lastrowid
            conn.commit()
            logger.info(f"Created scheduled post {post_id}")
            return post_id
        except Exception as e:
            logger.error(f"Error creating scheduled post: {e}")
            return None
        finally:
            conn.close()
    
    def get_scheduled_posts(self, status=None, start_date=None, end_date=None):
        """Get scheduled posts with optional filtering"""
        conn = self.get_connection()
        try:
            query = "SELECT * FROM scheduled_posts WHERE 1=1"
            params = []
            
            if status:
                query += " AND status = ?"
                params.append(status)
            
            if start_date:
                query += " AND scheduled_time >= ?"
                params.append(start_date)
            
            if end_date:
                query += " AND scheduled_time <= ?"
                params.append(end_date)
            
            query += " ORDER BY scheduled_time ASC"
            
            cursor = conn.execute(query, params)
            posts = []
            for row in cursor.fetchall():
                post = dict(row)
                if post['metadata']:
                    post['metadata'] = json.loads(post['metadata'])
                posts.append(post)
            
            return posts
        except Exception as e:
            logger.error(f"Error getting scheduled posts: {e}")
            return []
        finally:
            conn.close()
    
    def update_scheduled_post(self, post_id, **kwargs):
        """Update scheduled post fields"""
        conn = self.get_connection()
        try:
            # Build dynamic update query
            fields = []
            values = []
            
            for key, value in kwargs.items():
                if key in ['title', 'description', 'scheduled_time', 'status', 'facebook_video_id', 
                          'facebook_url', 'error_message', 'retry_count', 'user_id']:
                    fields.append(f"{key} = ?")
                    values.append(value)
                elif key == 'metadata':
                    fields.append("metadata = ?")
                    values.append(json.dumps(value) if value else None)
            
            if not fields:
                return False
            
            fields.append("updated_at = ?")
            values.append(int(datetime.now().timestamp()))
            values.append(post_id)
            
            query = f"UPDATE scheduled_posts SET {', '.join(fields)} WHERE id = ?"
            conn.execute(query, values)
            conn.commit()
            
            return conn.total_changes > 0
        except Exception as e:
            logger.error(f"Error updating scheduled post {post_id}: {e}")
            return False
        finally:
            conn.close()
    
    def delete_scheduled_post(self, post_id):
        """Delete scheduled post"""
        conn = self.get_connection()
        try:
            conn.execute("DELETE FROM scheduled_posts WHERE id = ?", (post_id,))
            conn.commit()
            return conn.total_changes > 0
        except Exception as e:
            logger.error(f"Error deleting scheduled post {post_id}: {e}")
            return False
        finally:
            conn.close()
    
    # Downloaded Files Methods
    def create_downloaded_file(self, file_path, original_url, title=None, description=None, 
                              file_size=None, duration=None, thumbnail_path=None, metadata=None):
        """Record a downloaded file"""
        conn = self.get_connection()
        try:
            cursor = conn.execute('''
                INSERT OR REPLACE INTO downloaded_files 
                (file_path, original_url, title, description, file_size, duration, thumbnail_path, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (file_path, original_url, title, description, file_size, duration, 
                  thumbnail_path, json.dumps(metadata) if metadata else None))
            
            file_id = cursor.lastrowid
            conn.commit()
            logger.info(f"Recorded downloaded file {file_id}: {file_path}")
            return file_id
        except Exception as e:
            logger.error(f"Error recording downloaded file: {e}")
            return None
        finally:
            conn.close()
    
    def get_downloaded_files(self, limit=None, offset=0, search=None, category=None, status=None):
        """Get downloaded files with pagination and filtering"""
        conn = self.get_connection()
        try:
            query = "SELECT * FROM downloaded_files WHERE 1=1"
            params = []
            
            if search:
                query += " AND (title LIKE ? OR description LIKE ?)"
                search_term = f"%{search}%"
                params.extend([search_term, search_term])
            
            if category:
                query += " AND category = ?"
                params.append(category)
            
            if status:
                query += " AND upload_status = ?"
                params.append(status)
            
            query += " ORDER BY download_date DESC"
            
            if limit:
                query += " LIMIT ? OFFSET ?"
                params.extend([limit, offset])
            
            cursor = conn.execute(query, params)
            files = []
            for row in cursor.fetchall():
                file_record = dict(row)
                if file_record['metadata']:
                    file_record['metadata'] = json.loads(file_record['metadata'])
                files.append(file_record)
            
            return files
        except Exception as e:
            logger.error(f"Error getting downloaded files: {e}")
            return []
        finally:
            conn.close()
    
    def update_file_upload_status(self, file_path, status, facebook_video_id=None, facebook_url=None):
        """Update file upload status"""
        conn = self.get_connection()
        try:
            conn.execute('''
                UPDATE downloaded_files 
                SET upload_status = ?, facebook_video_id = ?, facebook_url = ?
                WHERE file_path = ?
            ''', (status, facebook_video_id, facebook_url, file_path))
            conn.commit()
            return conn.total_changes > 0
        except Exception as e:
            logger.error(f"Error updating file upload status: {e}")
            return False
        finally:
            conn.close()
    
    # Analytics Methods
    def log_event(self, event_type, event_data=None, session_id=None):
        """Log analytics event"""
        conn = self.get_connection()
        try:
            conn.execute('''
                INSERT INTO analytics_events (event_type, event_data, session_id)
                VALUES (?, ?, ?)
            ''', (event_type, json.dumps(event_data) if event_data else None, session_id))
            conn.commit()
        except Exception as e:
            logger.error(f"Error logging event: {e}")
        finally:
            conn.close()
    
    def get_analytics_summary(self, days=30):
        """Get analytics summary for dashboard"""
        conn = self.get_connection()
        try:
            cutoff_time = int((datetime.now() - timedelta(days=days)).timestamp())
            
            # Get event counts by type
            cursor = conn.execute('''
                SELECT event_type, COUNT(*) as count
                FROM analytics_events 
                WHERE timestamp >= ?
                GROUP BY event_type
            ''', (cutoff_time,))
            
            events = dict(cursor.fetchall())
            
            # Get download/upload stats
            cursor = conn.execute('''
                SELECT 
                    COUNT(*) as total_downloads,
                    SUM(CASE WHEN upload_status = 'uploaded' THEN 1 ELSE 0 END) as successful_uploads,
                    SUM(file_size) as total_size
                FROM downloaded_files 
                WHERE download_date >= ?
            ''', (cutoff_time,))
            
            stats = dict(cursor.fetchone())
            
            return {**events, **stats}
        except Exception as e:
            logger.error(f"Error getting analytics summary: {e}")
            return {}
        finally:
            conn.close()
    
    # Settings Methods
    def set_setting(self, key, value):
        """Set application setting"""
        conn = self.get_connection()
        try:
            conn.execute('''
                INSERT OR REPLACE INTO app_settings (key, value, updated_at)
                VALUES (?, ?, ?)
            ''', (key, json.dumps(value), int(datetime.now().timestamp())))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error setting {key}: {e}")
            return False
        finally:
            conn.close()
    
    def get_setting(self, key, default=None):
        """Get application setting"""
        conn = self.get_connection()
        try:
            cursor = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                return json.loads(row['value'])
            return default
        except Exception as e:
            logger.error(f"Error getting setting {key}: {e}")
            return default
        finally:
            conn.close()

# Global database instance
db = DatabaseManager()