#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask web server for Facebook video downloader
"""

import os
import sys
import json
import threading
import traceback
import logging
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory

# Set UTF-8 encoding for Windows console
if sys.platform.startswith('win'):
    import codecs
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("SUCCESS: Environment variables loaded from .env file")
except ImportError:
    print("WARNING: python-dotenv not installed, environment variables from system only")

# Configure logging with better formatting and console output
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console handler
        logging.FileHandler('facebook_downloader.log')  # File handler
    ]
)
logger = logging.getLogger(__name__)

# Ensure Flask logs are also visible
logging.getLogger('werkzeug').setLevel(logging.INFO)

try:
    from facebook_downloader import FacebookDownloader
    from config import DOWNLOAD_CONFIG
    from handbrake_simple import SimpleHandBrake
    logger.info("Successfully imported downloader modules")
except ImportError as e:
    logger.error(f"Failed to import modules: {e}")
    raise

app = Flask(__name__)
app.secret_key = 'facebook-video-downloader-secret-key'

# Global variables for tracking downloads
download_status = {}
download_counter = 0

def get_download_id():
    """Generate unique download ID"""
    global download_counter
    download_counter += 1
    return f"download_{download_counter}"

def download_worker(download_id, url, use_cookies, cookies_content, facebook_upload=None):
    """Background worker for video downloads"""
    global download_status
    
    try:
        logger.info(f"DEBUG: DOWNLOAD WORKER STARTED - ID: {download_id}")
        logger.info(f"Starting download {download_id} for URL: {url}")
        download_status[download_id] = {
            'status': 'downloading',
            'message': 'Initializing download...',
            'progress': 0
        }
        
        # Test yt-dlp availability first
        try:
            import subprocess
            result = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                raise Exception("yt-dlp is not working properly")
            logger.info(f"yt-dlp version: {result.stdout.strip()}")
        except FileNotFoundError:
            raise Exception("yt-dlp is not installed. Please install it with: pip install yt-dlp")
        except subprocess.TimeoutExpired:
            raise Exception("yt-dlp is not responding")
        except Exception as e:
            raise Exception(f"yt-dlp check failed: {str(e)}")
        
        download_status[download_id]['message'] = 'Creating downloader...'
        downloader = FacebookDownloader()
        
        # Handle cookies if provided
        if use_cookies and cookies_content:
            logger.info("Using cookie authentication")
            cookies_path = Path(f"temp_cookies_{download_id}.txt")
            try:
                with open(cookies_path, 'w', encoding='utf-8') as f:
                    f.write(cookies_content)
                
                download_status[download_id]['message'] = 'Downloading with authentication...'
                success = downloader.download_with_cookies(url, str(cookies_path))
            finally:
                # Clean up temp cookies file
                if cookies_path.exists():
                    cookies_path.unlink()
        else:
            logger.info("Downloading public video")
            download_status[download_id]['message'] = 'Downloading public video...'
            success = downloader.download_video(url)
        
        if success:
            logger.info(f"Download {download_id} completed successfully")
            # Process video with HandBrake after successful download
            print("HANDBRAKE: Starting HandBrake processing section")
            handbrake_success = False
            handbrake_result = None
            try:
                download_status[download_id]['message'] = 'Processing video with HandBrake...'
                
                # Find the downloaded video file
                downloads_dir = Path(DOWNLOAD_CONFIG['output_dir'])
                video_files = list(downloads_dir.glob('*.mp4')) + list(downloads_dir.glob('*.mkv')) + list(downloads_dir.glob('*.webm'))
                print(f"HANDBRAKE: Found {len(video_files)} video files in {downloads_dir}")
                
                if video_files:
                    # Get the most recently modified video file
                    latest_video = max(video_files, key=lambda x: x.stat().st_mtime)
                    print(f"HANDBRAKE: Processing video: {latest_video}")
                    
                    # Use simple HandBrake integration
                    handbrake = SimpleHandBrake()
                    if handbrake.is_available():
                        print("HANDBRAKE: HandBrake CLI is available")
                        
                        # Process with HandBrake
                        handbrake_success, handbrake_result = handbrake.process_video(str(latest_video))
                        
                        if handbrake_success:
                            print(f"HANDBRAKE: SUCCESS - {handbrake_result}")
                            download_status[download_id]['handbrake_status'] = 'completed'
                            download_status[download_id]['handbrake_result'] = handbrake_result
                        else:
                            print(f"HANDBRAKE: FAILED - {handbrake_result}")
                            download_status[download_id]['handbrake_status'] = 'failed'
                            download_status[download_id]['handbrake_error'] = handbrake_result
                    else:
                        print("HANDBRAKE: HandBrake CLI not available")
                        download_status[download_id]['handbrake_status'] = 'unavailable'
                        download_status[download_id]['handbrake_error'] = 'HandBrake CLI not found'
                else:
                    print("HANDBRAKE: No video files found")
                    download_status[download_id]['handbrake_status'] = 'skipped'
                    
            except Exception as handbrake_error:
                print(f"HANDBRAKE: Exception - {handbrake_error}")
                download_status[download_id]['handbrake_status'] = 'error'
                download_status[download_id]['handbrake_error'] = str(handbrake_error)
            
            # Record the downloaded file in database
            try:
                from database import db
                downloads_dir = Path(DOWNLOAD_CONFIG['output_dir'])
                video_files = list(downloads_dir.glob('*.mp4')) + list(downloads_dir.glob('*.mkv')) + list(downloads_dir.glob('*.webm'))
                if video_files:
                    latest_video = max(video_files, key=lambda x: x.stat().st_mtime)
                    
                    # Extract title from metadata
                    video_title = downloader.extract_video_title_from_metadata(str(latest_video))
                    video_description = downloader.extract_video_description_from_metadata(str(latest_video))
                    
                    # Record in database
                    db.create_downloaded_file(
                        file_path=str(latest_video),
                        original_url=url,
                        title=video_title,
                        description=video_description,
                        file_size=latest_video.stat().st_size,
                        metadata={'download_id': download_id}
                    )
                    
                    # Log analytics event
                    db.log_event('video_downloaded', {
                        'url': url, 
                        'title': video_title,
                        'file_size': latest_video.stat().st_size
                    })
            except Exception as e:
                logger.error(f"Error recording download in database: {e}")
            
            # Handle Facebook upload if enabled
            facebook_result = None
            if facebook_upload and facebook_upload.get('enabled', False):
                logger.info(f"FACEBOOK: Facebook upload is enabled for single video")
                try:
                    # Find the downloaded video file
                    downloads_dir = Path(DOWNLOAD_CONFIG['output_dir'])
                    video_files = list(downloads_dir.glob('*.mp4')) + list(downloads_dir.glob('*.mkv')) + list(downloads_dir.glob('*.webm'))
                    if video_files:
                        # Get the most recently modified video file
                        latest_video = max(video_files, key=lambda x: x.stat().st_mtime)
                        logger.info(f"FACEBOOK: Found downloaded video file: {latest_video}")
                        
                        # Generate Facebook upload preview
                        download_status[download_id]['message'] = 'Generating Facebook preview...'
                        
                        # Generate preview instead of immediate upload
                        preview_success, preview_result = downloader.generate_facebook_preview(
                            video_path=str(latest_video),
                            user_title_prefix=facebook_upload.get('title_prefix', ''),
                            user_description=facebook_upload.get('description', '')
                        )
                        
                        if preview_success:
                            download_status[download_id]['message'] = 'Ready for Facebook upload - Review your preview'
                            download_status[download_id]['facebook_status'] = 'preview_ready'
                            download_status[download_id]['facebook_preview'] = preview_result
                            logger.info(f"FACEBOOK: Facebook preview generated: {preview_result['final_title'][:50]}...")
                            
                            facebook_result = {
                                'success': True,
                                'preview_ready': True,
                                'preview': preview_result
                            }
                        else:
                            download_status[download_id]['message'] = f'Preview generation failed: {preview_result}'
                            download_status[download_id]['facebook_status'] = 'preview_failed'
                            
                            facebook_result = {
                                'success': False,
                                'preview_ready': False,
                                'error': preview_result
                            }
                        
                        if preview_success:
                            logger.info(f"FACEBOOK: Facebook preview generated successfully!")
                        else:
                            logger.error(f"FACEBOOK: Facebook preview generation failed: {preview_result}")
                            
                    else:
                        logger.error(f"FACEBOOK: No video file found for Facebook preview")
                        facebook_result = {'success': False, 'preview_ready': False, 'error': 'No video file found'}
                        
                except Exception as fb_error:
                    logger.error(f"FACEBOOK: Exception during Facebook preview generation: {fb_error}")
                    facebook_result = {'success': False, 'preview_ready': False, 'error': str(fb_error)}
            else:
                logger.info(f"FACEBOOK: Facebook auto-upload disabled for single video")
            
            # Final status update - include HandBrake status
            final_message = 'Download completed successfully!'
            
            # Check HandBrake processing status
            handbrake_status = download_status[download_id].get('handbrake_status')
            if handbrake_status == 'completed':
                final_message = 'Download and HandBrake processing completed successfully! Video is ready for re-upload.'
            elif handbrake_status == 'failed':
                handbrake_error = download_status[download_id].get('handbrake_error', 'Unknown error')
                final_message = f'Download completed, but HandBrake processing failed: {handbrake_error}'
            elif handbrake_status == 'error':
                handbrake_error = download_status[download_id].get('handbrake_error', 'Unknown error')
                final_message = f'Download completed, but HandBrake processing error: {handbrake_error}'
            elif handbrake_status == 'unavailable':
                final_message = 'Download completed, but HandBrake CLI is not available for video processing.'
            elif handbrake_status == 'skipped':
                final_message = 'Download completed, but no video file found for HandBrake processing.'
            
            # Override with Facebook status if needed
            if facebook_result:
                if facebook_result.get('preview_ready'):
                    if handbrake_status == 'completed':
                        final_message = 'Download and HandBrake processing completed - Facebook preview ready!'
                    else:
                        final_message = 'Download completed - Facebook preview ready!'
                elif facebook_result.get('success') == False:
                    facebook_error = facebook_result.get("error", "Unknown error")
                    if handbrake_status == 'completed':
                        final_message = f'Download and HandBrake processing completed, but Facebook preview failed: {facebook_error}'
                    else:
                        final_message = f'Download completed, but Facebook preview failed: {facebook_error}'
            
            download_status[download_id] = {
                'status': 'completed',
                'message': final_message,
                'progress': 100,
                'facebook_upload': facebook_result
            }
        else:
            logger.error(f"Download {download_id} failed")
            download_status[download_id] = {
                'status': 'error',
                'message': 'Download failed. The video might be private, deleted, or the URL is incorrect.',
                'progress': 0
            }
            
    except Exception as e:
        error_msg = str(e)
        error_trace = traceback.format_exc()
        logger.error(f"Download {download_id} error: {error_msg}")
        logger.error(f"Full traceback: {error_trace}")
        
        download_status[download_id] = {
            'status': 'error',
            'message': f'Error: {error_msg}',
            'progress': 0,
            'details': error_trace if logger.level <= logging.DEBUG else None
        }

def batch_download_worker(download_id, video_urls, use_cookies, cookies_content, facebook_upload=None):
    """Background worker for batch video downloads from individual URLs"""
    global download_status
    
    try:
        logger.info(f"BATCH: BATCH DOWNLOAD STARTED - ID: {download_id}")
        logger.info(f"BATCH: Parameters:")
        logger.info(f"BATCH:    - Video URLs count: {len(video_urls)}")
        logger.info(f"BATCH:    - Video URLs: {video_urls}")
        logger.info(f"BATCH:    - Use cookies: {use_cookies}")
        logger.info(f"BATCH:    - Cookies length: {len(cookies_content) if cookies_content else 0} chars")
        logger.info(f"BATCH:    - Facebook upload: {facebook_upload}")
        
        download_status[download_id] = {
            'status': 'downloading',
            'message': 'Initializing batch download...',
            'progress': 0,
            'batch_info': {
                'total_videos': 0,
                'completed': 0,
                'failed': 0,
                'current_video': 'Initializing...'
            }
        }
        
        logger.info(f"BATCH: Creating FacebookDownloader instance...")
        downloader = FacebookDownloader()
        logger.info(f"BATCH: FacebookDownloader created successfully")
        
        # Handle cookies if provided
        cookies_path = None
        if use_cookies and cookies_content:
            logger.info(f"BATCH: Setting up authentication cookies...")
            cookies_path = Path(f"temp_cookies_{download_id}.txt")
            try:
                with open(cookies_path, 'w', encoding='utf-8') as f:
                    f.write(cookies_content)
                logger.info(f"BATCH: Cookies file created: {cookies_path}")
            except Exception as e:
                logger.error(f"BATCH: Failed to create cookies file: {e}")
                raise e
        else:
            logger.info(f"BATCH: No authentication - downloading public content only")
        
        # Update status
        download_status[download_id]['message'] = 'Fetching video list...'
        logger.info(f"BATCH: Starting video list extraction...")
        
        # Progress callback function
        def progress_callback(current_index, total, current_title):
            progress = int((current_index / total) * 100) if total > 0 else 0
            logger.info(f"BATCH: Progress: {current_index + 1}/{total} ({progress}%) - {current_title[:30]}...")
            download_status[download_id].update({
                'status': 'downloading',
                'message': f'Downloading video {current_index + 1} of {total}',
                'progress': progress,
                'batch_info': {
                    'total_videos': total,
                    'completed': current_index,
                    'failed': download_status[download_id]['batch_info'].get('failed', 0),
                    'current_video': current_title[:50] + '...' if len(current_title) > 50 else current_title
                }
            })
        
        # Start batch download of individual URLs
        logger.info(f"BATCH: Starting individual video downloads...")
        
        total_videos = len(video_urls)
        successful_downloads = []
        failed_downloads = []
        
        for i, video_url in enumerate(video_urls):
            logger.info(f"BATCH: Downloading video {i+1}/{total_videos}: {video_url}")
            
            # Update progress
            progress = int((i / total_videos) * 100) if total_videos > 0 else 0
            download_status[download_id].update({
                'status': 'downloading',
                'message': f'Downloading video {i + 1} of {total_videos}',
                'progress': progress,
                'batch_info': {
                    'total_videos': total_videos,
                    'completed': i,
                    'failed': len(failed_downloads),
                    'current_video': f'Video {i+1}: {video_url[:50]}...'
                }
            })
            
            try:
                if cookies_path:
                    success = downloader.download_with_cookies(video_url, str(cookies_path))
                else:
                    success = downloader.download_video(video_url)
                
                if success:
                    logger.info(f"BATCH: Successfully downloaded: {video_url}")
                    
                    # Process video with HandBrake after successful download
                    print(f"HANDBRAKE: Processing batch video {i+1}")
                    handbrake_success = False
                    handbrake_result = None
                    try:
                        # Update status for HandBrake processing
                        download_status[download_id]['batch_info']['current_video'] = f'Processing with HandBrake: Video {i+1}'
                        
                        # Find the downloaded video file
                        downloads_dir = Path(DOWNLOAD_CONFIG['output_dir'])
                        video_files = list(downloads_dir.glob('*.mp4')) + list(downloads_dir.glob('*.mkv')) + list(downloads_dir.glob('*.webm'))
                        if video_files:
                            latest_video = max(video_files, key=lambda x: x.stat().st_mtime)
                            print(f"HANDBRAKE: Processing video: {latest_video}")
                            
                            # Use simple HandBrake integration
                            handbrake = SimpleHandBrake()
                            handbrake_success, handbrake_result = handbrake.process_video(str(latest_video))
                            
                            if handbrake_success:
                                print(f"HANDBRAKE: SUCCESS for video {i+1}")
                            else:
                                print(f"HANDBRAKE: FAILED for video {i+1} - {handbrake_result}")
                        else:
                            print(f"HANDBRAKE: No video files found for video {i+1}")
                            
                    except Exception as handbrake_error:
                        print(f"HANDBRAKE: Exception for video {i+1}: {handbrake_error}")
                    
                    # Try to find the downloaded video file for Facebook upload
                    try:
                        downloads_dir = Path(DOWNLOAD_CONFIG['output_dir'])
                        # Look for recently created video files
                        video_files = list(downloads_dir.glob('*.mp4')) + list(downloads_dir.glob('*.mkv')) + list(downloads_dir.glob('*.webm'))
                        if video_files:
                            # Get the most recently modified video file
                            latest_video = max(video_files, key=lambda x: x.stat().st_mtime)
                            logger.info(f"BATCH: Found downloaded video file: {latest_video}")
                            
                            # Extract original video title from metadata
                            video_title = downloader.extract_video_title_from_metadata(str(latest_video))
                            successful_downloads.append({
                                'url': video_url, 
                                'title': video_title,
                                'handbrake_processed': handbrake_success,
                                'handbrake_result': handbrake_result if handbrake_success else None
                            })
                            
                            # Check if Facebook upload is enabled (from form or config)
                            from config import FACEBOOK_CONFIG
                            fb_upload_enabled = (facebook_upload and facebook_upload.get('enabled', False)) or FACEBOOK_CONFIG.get('auto_upload_enabled', False)
                            
                            if fb_upload_enabled:
                                logger.info(f"BATCH: Facebook upload is enabled, starting upload...")
                                
                                # Prepare title with prefix if provided
                                upload_title = video_title
                                if facebook_upload and facebook_upload.get('title_prefix'):
                                    upload_title = f"{facebook_upload['title_prefix']}{video_title}"
                                
                                # Prepare description from form or config
                                upload_description = ""
                                if facebook_upload and facebook_upload.get('description'):
                                    upload_description = facebook_upload['description']
                                elif FACEBOOK_CONFIG.get('default_description'):
                                    upload_description = FACEBOOK_CONFIG['default_description']
                                
                                logger.info(f"BATCH: Upload details: title='{upload_title}', description='{upload_description}'")
                                
                                # Update status to show Facebook upload
                                download_status[download_id]['batch_info']['current_video'] = f'Uploading to Facebook: {upload_title}'
                                
                                # Temporarily update config for this upload
                                original_config = FACEBOOK_CONFIG.copy()
                                if facebook_upload:
                                    if facebook_upload.get('title_prefix'):
                                        FACEBOOK_CONFIG['default_title_prefix'] = facebook_upload['title_prefix']
                                    if facebook_upload.get('description'):
                                        FACEBOOK_CONFIG['default_description'] = facebook_upload['description']
                                
                                try:
                                    upload_success, upload_result = downloader.post_download_actions(
                                        video_path=str(latest_video),
                                        video_title=upload_title,
                                        video_description=upload_description,
                                        auto_upload=True
                                    )
                                finally:
                                    # Restore original config
                                    FACEBOOK_CONFIG.update(original_config)
                                
                                if upload_success:
                                    logger.info(f"BATCH: Facebook upload successful for: {video_url}")
                                    successful_downloads[-1]['facebook_upload'] = 'success'
                                    successful_downloads[-1]['facebook_result'] = upload_result
                                else:
                                    logger.error(f"BATCH: Facebook upload failed for: {video_url} - {upload_result}")
                                    successful_downloads[-1]['facebook_upload'] = 'failed'
                                    successful_downloads[-1]['facebook_error'] = upload_result
                            else:
                                logger.info(f"BATCH: Facebook auto-upload disabled")
                                successful_downloads[-1]['facebook_upload'] = 'disabled'
                        else:
                            # No video files found - use fallback title
                            video_title = f'Video {i+1}'
                            successful_downloads.append({'url': video_url, 'title': video_title})
                            logger.warning(f"BATCH: No video files found after download: {video_url}")
                    except Exception as upload_error:
                        logger.error(f"BATCH: Exception during Facebook upload: {upload_error}")
                        if successful_downloads:
                            successful_downloads[-1]['facebook_upload'] = 'error'
                            successful_downloads[-1]['facebook_error'] = str(upload_error)
                else:
                    failed_downloads.append({'url': video_url, 'title': f'Video {i+1}'})
                    logger.error(f"BATCH: Failed to download: {video_url}")
                    
            except Exception as e:
                failed_downloads.append({'url': video_url, 'title': f'Video {i+1}'})
                logger.error(f"BATCH: Exception downloading {video_url}: {e}")
        
        # Final results
        success = len(successful_downloads) > 0
        results = {
            'successful': successful_downloads,
            'failed': failed_downloads,
            'total': total_videos
        }
        
        logger.info(f"BATCH: Batch download completed: success={success}, results type={type(results)}")
        
        # Clean up temp cookies file
        if cookies_path and cookies_path.exists():
            logger.info(f"BATCH: Cleaning up cookies file: {cookies_path}")
            cookies_path.unlink()
        
        if success:
            logger.info(f"BATCH: BATCH DOWNLOAD SUCCESS!")
            logger.info(f"BATCH: Results summary:")
            logger.info(f"BATCH:    - Total videos: {results['total']}")
            logger.info(f"BATCH:    - Successful: {len(results['successful'])}")
            logger.info(f"BATCH:    - Failed: {len(results['failed'])}")
            
            download_status[download_id] = {
                'status': 'completed',
                'message': f'Batch download completed! {len(results["successful"])} successful, {len(results["failed"])} failed.',
                'progress': 100,
                'batch_info': {
                    'total_videos': results['total'],
                    'completed': len(results['successful']),
                    'failed': len(results['failed']),
                    'current_video': 'Complete'
                },
                'results': results
            }
        else:
            logger.error(f"BATCH: BATCH DOWNLOAD FAILED!")
            logger.error(f"BATCH: Results: {results}")
            
            download_status[download_id] = {
                'status': 'error',
                'message': 'Batch download failed. No videos could be downloaded.',
                'progress': 0,
                'batch_info': {
                    'total_videos': 0,
                    'completed': 0,
                    'failed': 0,
                    'current_video': 'Failed'
                }
            }
            
    except Exception as e:
        error_msg = str(e)
        error_trace = traceback.format_exc()
        logger.error(f"BATCH: BATCH DOWNLOAD EXCEPTION - ID: {download_id}")
        logger.error(f"BATCH: Error: {error_msg}")
        logger.error(f"BATCH: Full traceback:")
        for line in error_trace.split('\n'):
            if line.strip():
                logger.error(f"BATCH:    {line}")
        
        # Clean up temp cookies file if it exists
        if 'cookies_path' in locals() and cookies_path and cookies_path.exists():
            logger.info(f"BATCH: Cleaning up cookies file after error: {cookies_path}")
            cookies_path.unlink()
        
        download_status[download_id] = {
            'status': 'error',
            'message': f'Batch download error: {error_msg}',
            'progress': 0,
            'batch_info': {
                'total_videos': 0,
                'completed': 0,
                'failed': 0,
                'current_video': 'Error'
            },
            'details': error_trace if logger.level <= logging.DEBUG else None
        }

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download_video():
    """Start video download"""
    try:
        logger.info("Received download request")
        data = request.get_json()
        
        if not data:
            logger.error("No JSON data received")
            return jsonify({'error': 'Invalid request format'}), 400
            
        url = data.get('url', '').strip()
        use_cookies = data.get('use_cookies', False)
        cookies_content = data.get('cookies_content', '').strip()
        facebook_upload = data.get('facebook_upload', {})
        
        logger.info(f"DOWNLOAD: SERVER DEBUG - Download request received")
        logger.info(f"DOWNLOAD: Raw URL from request: '{url}'")
        logger.info(f"DOWNLOAD: URL length: {len(url)}")
        logger.info(f"DOWNLOAD: Request timestamp: {__import__('datetime').datetime.now().isoformat()}")
        logger.info(f"DOWNLOAD: Use cookies: {use_cookies}")
        logger.info(f"DOWNLOAD: Facebook upload settings: {facebook_upload}")
        
        if not url:
            return jsonify({'error': 'Please provide a video URL'}), 400
        
        # Support Facebook and YouTube URLs
        supported_platforms = [
            'https://www.facebook.com/', 'https://facebook.com/', 'https://m.facebook.com/',
            'https://www.youtube.com/', 'https://youtube.com/', 'https://youtu.be/', 'https://m.youtube.com/'
        ]
        
        if not any(url.startswith(platform) for platform in supported_platforms):
            return jsonify({'error': 'Please provide a valid Facebook or YouTube video URL'}), 400
        
        # Generate download ID
        download_id = get_download_id()
        logger.info(f"Generated download ID: {download_id}")
        
        # Start download in background thread
        thread = threading.Thread(
            target=download_worker, 
            args=(download_id, url, use_cookies, cookies_content, facebook_upload)
        )
        thread.daemon = True
        thread.start()
        
        logger.info(f"Started background download thread for {download_id}")
        return jsonify({'download_id': download_id})
        
    except Exception as e:
        logger.error(f"Download endpoint error: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/batch-download', methods=['POST'])
def batch_download():
    """Start batch video download from individual Facebook video URLs"""
    try:
        logger.info("Received batch download request")
        data = request.get_json()
        
        if not data:
            logger.error("No JSON data received")
            return jsonify({'error': 'Invalid request format'}), 400
            
        video_urls = data.get('video_urls', [])
        use_cookies = data.get('use_cookies', False)
        cookies_content = data.get('cookies_content', '').strip()
        facebook_upload = data.get('facebook_upload', {})
        
        logger.info(f"Batch download request - Video URLs count: {len(video_urls)}, use_cookies: {use_cookies}")
        logger.info(f"Facebook upload settings: {facebook_upload}")
        
        if not video_urls or len(video_urls) == 0:
            return jsonify({'error': 'Please provide at least one Facebook video URL'}), 400
        
        if len(video_urls) > 20:
            return jsonify({'error': 'Maximum 20 videos per batch'}), 400
        
        # Validate all URLs
        invalid_urls = []
        # Support Facebook and YouTube URLs
        supported_platforms = [
            'https://www.facebook.com/', 'https://facebook.com/', 'https://m.facebook.com/',
            'https://www.youtube.com/', 'https://youtube.com/', 'https://youtu.be/', 'https://m.youtube.com/'
        ]
        
        for url in video_urls:
            if not url.strip():
                continue
            if not any(url.startswith(platform) for platform in supported_platforms):
                invalid_urls.append(url)
        
        if invalid_urls:
            return jsonify({'error': f'Invalid URLs (must be Facebook or YouTube): {invalid_urls[:3]}...'}), 400
        
        # Generate download ID
        download_id = get_download_id()
        logger.info(f"Generated batch download ID: {download_id}")
        
        # Start batch download in background thread
        thread = threading.Thread(
            target=batch_download_worker, 
            args=(download_id, video_urls, use_cookies, cookies_content, facebook_upload)
        )
        thread.daemon = True
        thread.start()
        
        logger.info(f"Started background batch download thread for {download_id}")
        return jsonify({'download_id': download_id, 'type': 'batch'})
        
    except Exception as e:
        logger.error(f"Batch download endpoint error: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/status/<download_id>')
def get_status(download_id):
    """Get download status"""
    status = download_status.get(download_id, {
        'status': 'not_found',
        'message': 'Download not found',
        'progress': 0
    })
    return jsonify(status)

@app.route('/preview-facebook-upload', methods=['POST'])
def preview_facebook_upload():
    """Generate Facebook upload preview"""
    try:
        data = request.get_json()
        video_path = data.get('video_path', '')
        user_title_prefix = data.get('title_prefix', '')
        user_description = data.get('description', '')
        
        if not video_path:
            return jsonify({'error': 'Video path is required'}), 400
        
        # Create downloader instance
        from facebook_downloader import FacebookDownloader
        downloader = FacebookDownloader()
        
        # Generate preview
        success, result = downloader.generate_facebook_preview(
            video_path=video_path,
            user_title_prefix=user_title_prefix,
            user_description=user_description
        )
        
        if success:
            return jsonify({
                'success': True,
                'preview': result
            })
        else:
            return jsonify({
                'success': False,
                'error': result
            }), 400
            
    except Exception as e:
        logger.error(f"Error generating Facebook preview: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/confirm-facebook-upload', methods=['POST'])
def confirm_facebook_upload():
    """Confirm and execute Facebook upload"""
    try:
        data = request.get_json()
        download_id = data.get('download_id', '')
        video_path = data.get('video_path', '')
        final_title = data.get('final_title', '')
        final_description = data.get('final_description', '')
        scheduling = data.get('scheduling', {})
        
        if not download_id or not video_path:
            return jsonify({'error': 'Download ID and video path are required'}), 400
        
        # Update download status with proper message based on scheduling
        is_scheduled = scheduling.get('publishType') == 'scheduled'
        if download_id in download_status:
            status_message = 'Scheduling Facebook post...' if is_scheduled else 'Uploading to Facebook...'
            download_status[download_id]['message'] = status_message
            download_status[download_id]['facebook_status'] = 'uploading'
        
        # Create downloader instance
        from facebook_downloader import FacebookDownloader
        downloader = FacebookDownloader()
        
        # Extract scheduled time if provided
        scheduled_time = scheduling.get('scheduledTime') if is_scheduled else None
        
        if is_scheduled and scheduled_time:
            # Create scheduled post on Facebook AND store locally
            try:
                from database import db
                from config import FACEBOOK_CONFIG
                
                # Convert scheduled time to timestamp
                from datetime import datetime
                
                # Handle different formats of scheduled_time
                if isinstance(scheduled_time, str):
                    # ISO string format - convert to timestamp
                    scheduled_timestamp = int(datetime.fromisoformat(scheduled_time.replace('Z', '+00:00')).timestamp())
                elif isinstance(scheduled_time, (int, float)):
                    # Already a timestamp
                    scheduled_timestamp = int(scheduled_time)
                else:
                    raise ValueError(f"Invalid scheduled_time format: {type(scheduled_time)} - {scheduled_time}")
                
                # First, upload to Facebook with scheduling
                upload_success, upload_result = downloader.post_download_actions(
                    video_path=video_path,
                    video_title=final_title,
                    video_description=final_description,
                    auto_upload=True,
                    scheduled_publish_time=scheduled_timestamp
                )
                
                if upload_success:
                    # Also store in local database for tracking
                    local_post_id = db.create_scheduled_post(
                        video_file_path=video_path,
                        title=final_title,
                        description=final_description,
                        scheduled_time=scheduled_timestamp,
                        user_id=FACEBOOK_CONFIG.get('user_id'),
                        metadata={
                            'download_id': download_id,
                            'facebook_result': upload_result
                        }
                    )
                    
                    # Log analytics event
                    db.log_event('post_scheduled', {
                        'local_post_id': local_post_id,
                        'title': final_title,
                        'scheduled_time': scheduled_timestamp,
                        'facebook_result': upload_result
                    })
                    
                    # Update result with local tracking info
                    if isinstance(upload_result, dict):
                        upload_result['local_post_id'] = local_post_id
                    else:
                        upload_result = {
                            'success': True,
                            'local_post_id': local_post_id,
                            'facebook_result': upload_result,
                            'message': f'Post scheduled for {datetime.fromtimestamp(scheduled_timestamp).strftime("%Y-%m-%d %H:%M")}'
                        }
                else:
                    # Facebook upload failed - don't create local record
                    pass
                    
            except Exception as e:
                logger.error(f"Error creating scheduled post: {e}")
                upload_success = False
                upload_result = f'Scheduling error: {str(e)}'
        else:
            # Perform immediate upload
            upload_success, upload_result = downloader.post_download_actions(
                video_path=video_path,
                video_title=final_title,
                video_description=final_description,
                auto_upload=True,
                scheduled_publish_time=None
            )
        
        # Update download status with results
        if download_id in download_status:
            download_status[download_id]['facebook_upload'] = {
                'success': upload_success,
                'result': upload_result
            }
            if upload_success:
                download_status[download_id]['facebook_status'] = 'completed'
                success_message = 'Facebook post scheduled successfully!' if is_scheduled else 'Facebook upload completed!'
                download_status[download_id]['message'] = success_message
            else:
                download_status[download_id]['facebook_status'] = 'failed'
                download_status[download_id]['message'] = f'Facebook upload failed: {upload_result}'
        
        return jsonify({
            'success': upload_success,
            'result': upload_result
        })
        
    except Exception as e:
        logger.error(f"Error confirming Facebook upload: {e}")
        if download_id in download_status:
            download_status[download_id]['facebook_status'] = 'error'
            download_status[download_id]['message'] = f'Upload error: {str(e)}'
        return jsonify({'error': str(e)}), 500

@app.route('/downloads')
def downloads():
    """List downloaded files"""
    downloads_dir = Path(DOWNLOAD_CONFIG['output_dir'])
    if not downloads_dir.exists():
        return jsonify({'files': []})
    
    files = []
    for file_path in downloads_dir.iterdir():
        if file_path.is_file() and not file_path.name.endswith('.json'):
            files.append({
                'name': file_path.name,
                'size': file_path.stat().st_size,
                'modified': file_path.stat().st_mtime
            })
    
    # Sort by modification time (newest first)
    files.sort(key=lambda x: x['modified'], reverse=True)
    return jsonify({'files': files})

@app.route('/download-file/<filename>')
def download_file(filename):
    """Download a file"""
    downloads_dir = Path(DOWNLOAD_CONFIG['output_dir'])
    return send_from_directory(downloads_dir, filename, as_attachment=True)

@app.route('/config')
def get_config():
    """Get current configuration"""
    return jsonify(DOWNLOAD_CONFIG)

@app.route('/settings')
def get_settings():
    """Get current Facebook settings"""
    from config import FACEBOOK_CONFIG
    return jsonify({
        'access_token': FACEBOOK_CONFIG.get('access_token', ''),
        'user_id': FACEBOOK_CONFIG.get('user_id', '')
    })

@app.route('/save-settings', methods=['POST'])
def save_settings():
    """Save Facebook settings"""
    try:
        data = request.get_json()
        access_token = data.get('access_token', '').strip()
        user_id = data.get('user_id', '').strip()
        
        if not access_token or not user_id:
            return jsonify({'success': False, 'error': 'Access token and user ID are required'}), 400
        
        # Update the configuration
        from config import FACEBOOK_CONFIG
        FACEBOOK_CONFIG['access_token'] = access_token
        FACEBOOK_CONFIG['user_id'] = user_id
        
        # Also set environment variables for this session
        os.environ['FACEBOOK_ACCESS_TOKEN'] = access_token
        os.environ['FACEBOOK_USER_ID'] = user_id
        
        logger.info(f"Settings updated - User ID: {user_id}, Token: {access_token[:10]}...")
        
        return jsonify({'success': True, 'message': 'Settings saved successfully'})
        
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/test-facebook-connection', methods=['POST'])
def test_facebook_connection():
    """Test Facebook API connection"""
    try:
        data = request.get_json()
        access_token = data.get('access_token', '').strip()
        user_id = data.get('user_id', '').strip()
        
        if not access_token or not user_id:
            return jsonify({'success': False, 'error': 'Access token and user ID are required'}), 400
        
        # Test the connection using FacebookUploader
        from facebook_uploader import FacebookUploader
        uploader = FacebookUploader(access_token=access_token, user_id=user_id)
        
        success, result = uploader.test_connection()
        
        if success:
            return jsonify({
                'success': True,
                'user_info': result,
                'message': 'Connection successful'
            })
        else:
            return jsonify({
                'success': False,
                'error': result
            })
        
    except Exception as e:
        logger.error(f"Error testing Facebook connection: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/scheduled-videos')
def get_scheduled_videos():
    """Get scheduled videos for the frontend scheduled videos tab"""
    try:
        # Import required modules
        from facebook_uploader import FacebookUploader
        from config import FACEBOOK_CONFIG
        
        # Get Facebook config
        access_token = FACEBOOK_CONFIG.get('access_token', '')
        user_id = FACEBOOK_CONFIG.get('user_id', '')
        
        if not access_token or not user_id:
            return jsonify({
                'success': False,
                'error': 'Facebook credentials not configured. Please check your settings.',
                'videos': []
            })
        
        # Create uploader instance
        uploader = FacebookUploader(access_token=access_token, user_id=user_id)
        
        # Get scheduled posts from Facebook Graph API
        success, result = uploader.get_scheduled_posts()
        
        if success:
            # Transform Facebook API response to match frontend expectations
            videos = []
            
            # Get current timestamp for validation
            import time
            current_timestamp = int(time.time())
            
            for post in result.get('data', []):
                # Extract video information from scheduled post
                video_info = {
                    'id': post.get('id', ''),
                    'title': post.get('message', 'Untitled Video')[:100],  # Truncate long titles
                    'description': post.get('message', 'No description'),
                    'scheduled_publish_time': post.get('scheduled_publish_time', 0),
                    'status': post.get('status', 'SCHEDULED'),
                    'thumbnail': post.get('full_picture') or post.get('picture'),  # Video thumbnail if available
                    'created_time': post.get('created_time', ''),
                    'updated_time': post.get('updated_time', '')
                }
                
                # Convert ISO date string to timestamp if needed and validate
                scheduled_timestamp = 0
                if isinstance(video_info['scheduled_publish_time'], str):
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(video_info['scheduled_publish_time'].replace('Z', '+00:00'))
                        scheduled_timestamp = int(dt.timestamp())
                    except:
                        scheduled_timestamp = 0
                elif isinstance(video_info['scheduled_publish_time'], (int, float)):
                    scheduled_timestamp = int(video_info['scheduled_publish_time'])
                
                # Only include posts with valid future timestamps (not 1969 or past dates)
                if scheduled_timestamp > current_timestamp:
                    video_info['scheduled_publish_time'] = scheduled_timestamp
                    videos.append(video_info)
                else:
                    # Skip this post - it has invalid or past scheduled time
                    logger.info(f"Skipping post {video_info['id']} - invalid scheduled time: {video_info['scheduled_publish_time']}")
                    continue
            
            # Also get local scheduled posts from database
            try:
                from database import db
                local_posts = db.get_scheduled_posts(status='pending')
                
                for post in local_posts:
                    # Validate scheduled time for local posts too
                    scheduled_time = post.get('scheduled_time', 0)
                    if scheduled_time and scheduled_time > current_timestamp:
                        video_info = {
                            'id': f"local_{post['id']}",
                            'title': post.get('title', 'Untitled Video'),
                            'description': post.get('description', 'No description'),
                            'scheduled_publish_time': scheduled_time,
                            'status': 'SCHEDULED',
                            'thumbnail': None,  # Local posts don't have thumbnails yet
                            'created_time': post.get('created_at', ''),
                            'updated_time': post.get('updated_at', ''),
                            'local': True  # Flag to indicate this is a local post
                        }
                        videos.append(video_info)
                    else:
                        logger.info(f"Skipping local post {post['id']} - invalid scheduled time: {scheduled_time}")
                    
            except Exception as db_error:
                logger.warning(f"Could not fetch local scheduled posts: {db_error}")
            
            # Sort by scheduled time (earliest first)
            videos.sort(key=lambda x: x.get('scheduled_publish_time', 0))
            
            return jsonify({
                'success': True,
                'videos': videos,
                'message': f'Found {len(videos)} scheduled videos'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to fetch scheduled videos: {result}',
                'videos': []
            })
        
    except ImportError as e:
        logger.error(f"Missing required modules for scheduled videos: {e}")
        return jsonify({
            'success': False,
            'error': 'Facebook integration not properly configured',
            'videos': []
        })
    except Exception as e:
        logger.error(f"Error getting scheduled videos: {e}")
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}',
            'videos': []
        })

@app.route('/cancel-scheduled-video', methods=['POST'])
def cancel_scheduled_video():
    """Cancel a scheduled video post"""
    try:
        data = request.get_json()
        video_id = data.get('video_id', '').strip()
        
        if not video_id:
            return jsonify({'success': False, 'error': 'Video ID is required'}), 400
        
        # Import required modules
        from facebook_uploader import FacebookUploader
        from config import FACEBOOK_CONFIG
        
        # Get Facebook config
        access_token = FACEBOOK_CONFIG.get('access_token', '')
        user_id = FACEBOOK_CONFIG.get('user_id', '')
        
        if not access_token or not user_id:
            return jsonify({
                'success': False,
                'error': 'Facebook credentials not configured. Please check your settings.'
            }), 400
        
        # Check if this is a local post (prefixed with "local_")
        if video_id.startswith('local_'):
            # Handle local database post
            try:
                from database import db
                local_id = int(video_id.replace('local_', ''))
                
                # Update status to cancelled in database
                success = db.update_scheduled_post(local_id, status='cancelled')
                
                if success:
                    # Log analytics event
                    db.log_event('scheduled_post_cancelled', {'post_id': local_id})
                    
                    return jsonify({
                        'success': True,
                        'message': 'Local scheduled post cancelled successfully'
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': 'Failed to cancel local scheduled post'
                    })
                    
            except Exception as db_error:
                logger.error(f"Error cancelling local scheduled post: {db_error}")
                return jsonify({
                    'success': False,
                    'error': f'Database error: {str(db_error)}'
                })
        else:
            # Handle Facebook scheduled post
            uploader = FacebookUploader(access_token=access_token, user_id=user_id)
            
            # Cancel the scheduled post using Facebook Graph API
            success, result = uploader.cancel_scheduled_post(video_id)
            
            if success:
                # Also try to remove from local database if it exists
                try:
                    from database import db
                    # Find and update any matching local posts
                    posts = db.get_scheduled_posts()
                    for post in posts:
                        metadata = post.get('metadata') or {}
                        if metadata.get('facebook_post_id') == video_id:
                            db.update_scheduled_post(post['id'], status='cancelled')
                            break
                except Exception as db_error:
                    logger.warning(f"Could not update local database: {db_error}")
                
                return jsonify({
                    'success': True,
                    'message': 'Scheduled video cancelled successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Failed to cancel scheduled video: {result}'
                })
        
    except ImportError as e:
        logger.error(f"Missing required modules for cancelling scheduled videos: {e}")
        return jsonify({
            'success': False,
            'error': 'Facebook integration not properly configured'
        }), 500
    except Exception as e:
        logger.error(f"Error cancelling scheduled video: {e}")
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

# Enhanced API Endpoints for new features

@app.route('/api/scheduled-posts')
def get_scheduled_posts():
    """Get scheduled posts for calendar"""
    try:
        from database import db
        
        # Get filter parameters
        status = request.args.get('status')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Convert date strings to timestamps if provided
        start_timestamp = None
        end_timestamp = None
        
        if start_date:
            from datetime import datetime
            start_timestamp = int(datetime.fromisoformat(start_date).timestamp())
        
        if end_date:
            from datetime import datetime
            end_timestamp = int(datetime.fromisoformat(end_date).timestamp())
        
        posts = db.get_scheduled_posts(status=status, start_date=start_timestamp, end_date=end_timestamp)
        
        return jsonify(posts)
        
    except Exception as e:
        logger.error(f"Error getting scheduled posts: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/scheduled-posts', methods=['POST'])
def create_scheduled_post():
    """Create a new scheduled post"""
    try:
        from database import db
        data = request.get_json()
        
        video_file_path = data.get('video_file_path')
        title = data.get('title')
        description = data.get('description', '')
        scheduled_time = data.get('scheduled_time')
        user_id = data.get('user_id')
        
        if not all([video_file_path, title, scheduled_time]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Validate scheduled time is in future
        from datetime import datetime
        if scheduled_time <= int(datetime.now().timestamp()):
            return jsonify({'error': 'Scheduled time must be in the future'}), 400
        
        post_id = db.create_scheduled_post(
            video_file_path=video_file_path,
            title=title,
            description=description,
            scheduled_time=scheduled_time,
            user_id=user_id,
            metadata=data.get('metadata')
        )
        
        if post_id:
            # Log analytics event
            db.log_event('scheduled_post_created', {'post_id': post_id, 'title': title})
            return jsonify({'success': True, 'post_id': post_id})
        else:
            return jsonify({'error': 'Failed to create scheduled post'}), 500
            
    except Exception as e:
        logger.error(f"Error creating scheduled post: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/scheduled-posts/<int:post_id>', methods=['PUT'])
def update_scheduled_post(post_id):
    """Update a scheduled post"""
    try:
        from database import db
        data = request.get_json()
        
        success = db.update_scheduled_post(post_id, **data)
        
        if success:
            # Log analytics event
            db.log_event('scheduled_post_updated', {'post_id': post_id})
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Post not found or update failed'}), 404
            
    except Exception as e:
        logger.error(f"Error updating scheduled post {post_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/scheduled-posts/<int:post_id>', methods=['DELETE'])
def delete_scheduled_post(post_id):
    """Delete a scheduled post"""
    try:
        from database import db
        success = db.delete_scheduled_post(post_id)
        
        if success:
            # Log analytics event
            db.log_event('scheduled_post_deleted', {'post_id': post_id})
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Post not found'}), 404
            
    except Exception as e:
        logger.error(f"Error deleting scheduled post {post_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/files')
def get_files():
    """Get files with pagination and filtering for file manager"""
    try:
        from database import db
        
        # Get query parameters
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        search = request.args.get('search', '')
        status = request.args.get('status', '')
        sort = request.args.get('sort', 'date_desc')
        
        offset = (page - 1) * limit
        
        # Get files from database
        files = db.get_downloaded_files(
            limit=limit,
            offset=offset,
            search=search if search else None,
            status=status if status else None
        )
        
        # Get total count for pagination (simplified for now)
        total_files = len(db.get_downloaded_files())
        total_pages = (total_files + limit - 1) // limit
        
        # Add file existence check and additional metadata
        for file in files:
            file_path = Path(file['file_path'])
            file['exists'] = file_path.exists()
            if file['exists']:
                file['file_size'] = file_path.stat().st_size
            
        return jsonify({
            'files': files,
            'pagination': {
                'current_page': page,
                'total_pages': total_pages,
                'total_files': total_files,
                'limit': limit
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting files: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/<int:file_id>', methods=['DELETE'])
def delete_file(file_id):
    """Delete a file"""
    try:
        from database import db
        
        # Get file info first
        files = db.get_downloaded_files()
        file_record = next((f for f in files if f['id'] == file_id), None)
        
        if not file_record:
            return jsonify({'error': 'File not found'}), 404
        
        # Delete physical file
        file_path = Path(file_record['file_path'])
        if file_path.exists():
            file_path.unlink()
        
        # Delete from database (would need to implement this method in database.py)
        # For now, just update status
        db.update_file_upload_status(file_record['file_path'], 'deleted')
        
        # Log analytics event
        db.log_event('file_deleted', {'file_id': file_id, 'file_path': file_record['file_path']})
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Error deleting file {file_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics')
def get_analytics():
    """Get analytics data for dashboard"""
    try:
        from database import db
        from datetime import datetime, timedelta
        
        # Get analytics summary
        summary = db.get_analytics_summary()
        
        # Get additional metrics
        pending_posts = len(db.get_scheduled_posts(status='pending'))
        summary['pending_posts'] = pending_posts
        
        # Mock chart data (would implement proper time-series data)
        charts = {
            'download_activity': {
                'labels': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                'data': [12, 19, 3, 5, 2, 3, 20]
            },
            'upload_success_rate': {
                'labels': ['Successful', 'Failed'],
                'data': [summary.get('successful_uploads', 0), summary.get('total_downloads', 0) - summary.get('successful_uploads', 0)]
            }
        }
        
        # Mock recent activity
        activity = [
            {'type': 'download', 'message': 'Downloaded video: Sample Video', 'timestamp': datetime.now().isoformat()},
            {'type': 'upload', 'message': 'Uploaded to Facebook: Another Video', 'timestamp': (datetime.now() - timedelta(hours=1)).isoformat()},
            {'type': 'schedule', 'message': 'Scheduled post for tomorrow', 'timestamp': (datetime.now() - timedelta(hours=2)).isoformat()},
        ]
        
        return jsonify({
            'summary': summary,
            'charts': charts,
            'activity': activity
        })
        
    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/scheduler/status')
def get_scheduler_status():
    """Get scheduler status and upcoming posts"""
    try:
        from scheduler import scheduler
        status = scheduler.get_scheduler_status()
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/scheduler/start', methods=['POST'])
def start_scheduler():
    """Start the post scheduler"""
    try:
        from scheduler import scheduler
        scheduler.start()
        return jsonify({'success': True, 'message': 'Scheduler started'})
        
    except Exception as e:
        logger.error(f"Error starting scheduler: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/scheduler/stop', methods=['POST'])
def stop_scheduler():
    """Stop the post scheduler"""
    try:
        from scheduler import scheduler
        scheduler.stop()
        return jsonify({'success': True, 'message': 'Scheduler stopped'})
        
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Create downloads directory
    Path(DOWNLOAD_CONFIG['output_dir']).mkdir(exist_ok=True)
    
    # Initialize database
    try:
        from database import db
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
    
    # Start the scheduler
    try:
        from scheduler import scheduler
        scheduler.start()
        logger.info("Post scheduler started")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
    
    # Run the Flask app
    print("Starting Facebook Video Downloader Web Interface...")
    print("Access the interface at: http://localhost:5000")
    print("Features: Download videos, Schedule posts, File management, Analytics")
    logger.info("Starting Flask application on http://localhost:5000")
    
    try:
        # Enable debug mode for better error visibility
        app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
    except KeyboardInterrupt:
        print("\nShutting down...")
        logger.info("Application shutdown initiated by user")
        try:
            from scheduler import scheduler
            scheduler.stop()
            logger.info("Scheduler stopped")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")
    except Exception as e:
        logger.error(f"Fatal error running Flask app: {e}")
        print(f"Fatal error: {e}")
        raise