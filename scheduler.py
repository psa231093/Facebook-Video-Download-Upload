#!/usr/bin/env python3
"""
Background scheduler for managing Facebook post scheduling
"""

import threading
import time
from datetime import datetime, timezone
import logging
from database import db
from facebook_uploader import FacebookUploader
import os

logger = logging.getLogger(__name__)

class PostScheduler:
    def __init__(self):
        self.running = False
        self.thread = None
        self.check_interval = 60  # Check every minute
        
    def start(self):
        """Start the scheduler background thread"""
        if self.running:
            logger.warning("Scheduler already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.thread.start()
        logger.info("Post scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        self.running = False
        if self.thread:
            self.thread.join()
        logger.info("Post scheduler stopped")
    
    def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.running:
            try:
                self._process_pending_posts()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(self.check_interval)
    
    def _process_pending_posts(self):
        """Process posts that are ready to be published"""
        current_time = int(datetime.now().timestamp())
        
        # Get posts that are ready to publish
        pending_posts = db.get_scheduled_posts(status='pending')
        
        for post in pending_posts:
            if post['scheduled_time'] <= current_time:
                logger.info(f"Processing scheduled post {post['id']}: {post['title'][:50]}...")
                self._publish_scheduled_post(post)
    
    def _publish_scheduled_post(self, post):
        """Publish a scheduled post"""
        try:
            # Update status to processing
            db.update_scheduled_post(post['id'], status='processing')
            
            # Get Facebook credentials
            from config import FACEBOOK_CONFIG
            access_token = os.getenv('FACEBOOK_ACCESS_TOKEN') or FACEBOOK_CONFIG.get('access_token')
            user_id = post['user_id'] or FACEBOOK_CONFIG.get('user_id')
            
            if not access_token or not user_id:
                error_msg = "Missing Facebook credentials"
                logger.error(f"Post {post['id']}: {error_msg}")
                db.update_scheduled_post(post['id'], status='failed', error_message=error_msg)
                return
            
            # Check if video file still exists
            from pathlib import Path
            video_file = Path(post['video_file_path'])
            if not video_file.exists():
                error_msg = f"Video file not found: {post['video_file_path']}"
                logger.error(f"Post {post['id']}: {error_msg}")
                db.update_scheduled_post(post['id'], status='failed', error_message=error_msg)
                return
            
            # Initialize Facebook uploader
            uploader = FacebookUploader(access_token=access_token, user_id=user_id)
            
            # Upload the video (without scheduling since we're doing it now)
            success, result = uploader.upload_video(
                video_path=str(video_file),
                title=post['title'],
                description=post['description'] or ""
            )
            
            if success:
                # Update post status to published
                db.update_scheduled_post(
                    post['id'],
                    status='published',
                    facebook_video_id=result.get('video_id'),
                    facebook_url=result.get('facebook_url')
                )
                
                # Update file record if exists
                db.update_file_upload_status(
                    post['video_file_path'],
                    'uploaded',
                    result.get('video_id'),
                    result.get('facebook_url')
                )
                
                # Log analytics event
                db.log_event('scheduled_post_published', {
                    'post_id': post['id'],
                    'video_id': result.get('video_id'),
                    'title': post['title']
                })
                
                logger.info(f"Successfully published scheduled post {post['id']}")
                
            else:
                # Handle failure
                retry_count = post['retry_count'] + 1
                max_retries = 3
                
                if retry_count >= max_retries:
                    # Mark as failed after max retries
                    db.update_scheduled_post(
                        post['id'],
                        status='failed',
                        error_message=str(result),
                        retry_count=retry_count
                    )
                    logger.error(f"Post {post['id']} failed after {max_retries} attempts: {result}")
                else:
                    # Schedule for retry (back to pending with incremented retry count)
                    db.update_scheduled_post(
                        post['id'],
                        status='pending',
                        error_message=f"Attempt {retry_count}: {result}",
                        retry_count=retry_count
                    )
                    logger.warning(f"Post {post['id']} failed, will retry (attempt {retry_count}): {result}")
                
                # Log analytics event
                db.log_event('scheduled_post_failed', {
                    'post_id': post['id'],
                    'error': str(result),
                    'retry_count': retry_count
                })
        
        except Exception as e:
            logger.error(f"Error publishing scheduled post {post['id']}: {e}")
            db.update_scheduled_post(
                post['id'],
                status='failed',
                error_message=f"System error: {str(e)}"
            )
    
    def get_next_scheduled_posts(self, limit=5):
        """Get next posts to be published"""
        current_time = int(datetime.now().timestamp())
        all_pending = db.get_scheduled_posts(status='pending')
        
        # Filter and sort by scheduled time
        upcoming = [p for p in all_pending if p['scheduled_time'] > current_time]
        upcoming.sort(key=lambda x: x['scheduled_time'])
        
        return upcoming[:limit]
    
    def get_scheduler_status(self):
        """Get scheduler status information"""
        return {
            'running': self.running,
            'check_interval': self.check_interval,
            'next_posts': self.get_next_scheduled_posts(),
            'pending_count': len(db.get_scheduled_posts(status='pending')),
            'processing_count': len(db.get_scheduled_posts(status='processing')),
        }

# Global scheduler instance
scheduler = PostScheduler()