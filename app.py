#!/usr/bin/env python3
"""
Flask web server for Facebook video downloader
"""

import os
import json
import threading
import traceback
import logging
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Environment variables loaded from .env file")
except ImportError:
    print("⚠️  python-dotenv not installed, environment variables from system only")

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

try:
    from facebook_downloader import FacebookDownloader
    from config import DOWNLOAD_CONFIG
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
            
            # Handle Facebook upload if enabled
            facebook_result = None
            if facebook_upload and facebook_upload.get('enabled', False):
                logger.info(f"📤 Facebook upload is enabled for single video")
                try:
                    # Find the downloaded video file
                    downloads_dir = Path(DOWNLOAD_CONFIG['output_dir'])
                    video_files = list(downloads_dir.glob('*.mp4')) + list(downloads_dir.glob('*.mkv')) + list(downloads_dir.glob('*.webm'))
                    if video_files:
                        # Get the most recently modified video file
                        latest_video = max(video_files, key=lambda x: x.stat().st_mtime)
                        logger.info(f"📹 Found downloaded video file: {latest_video}")
                        
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
                            logger.info(f"📝 Facebook preview generated: {preview_result['final_title'][:50]}...")
                            
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
                            logger.info(f"✅ Facebook preview generated successfully!")
                        else:
                            logger.error(f"❌ Facebook preview generation failed: {preview_result}")
                            
                    else:
                        logger.error(f"❌ No video file found for Facebook preview")
                        facebook_result = {'success': False, 'preview_ready': False, 'error': 'No video file found'}
                        
                except Exception as fb_error:
                    logger.error(f"💥 Exception during Facebook preview generation: {fb_error}")
                    facebook_result = {'success': False, 'preview_ready': False, 'error': str(fb_error)}
            else:
                logger.info(f"⏸️  Facebook auto-upload disabled for single video")
            
            # Final status update
            final_message = 'Download completed successfully!'
            if facebook_result:
                if facebook_result.get('preview_ready'):
                    final_message = 'Download completed - Facebook preview ready!'
                elif facebook_result.get('success') == False:
                    final_message = f'Download completed, but Facebook preview failed: {facebook_result.get("error", "Unknown error")}'
            
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
        logger.info(f"🚀 BATCH DOWNLOAD STARTED - ID: {download_id}")
        logger.info(f"📝 Parameters:")
        logger.info(f"   - Video URLs count: {len(video_urls)}")
        logger.info(f"   - Video URLs: {video_urls}")
        logger.info(f"   - Use cookies: {use_cookies}")
        logger.info(f"   - Cookies length: {len(cookies_content) if cookies_content else 0} chars")
        logger.info(f"   - Facebook upload: {facebook_upload}")
        
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
        
        logger.info(f"🔧 Creating FacebookDownloader instance...")
        downloader = FacebookDownloader()
        logger.info(f"✅ FacebookDownloader created successfully")
        
        # Handle cookies if provided
        cookies_path = None
        if use_cookies and cookies_content:
            logger.info(f"🍪 Setting up authentication cookies...")
            cookies_path = Path(f"temp_cookies_{download_id}.txt")
            try:
                with open(cookies_path, 'w', encoding='utf-8') as f:
                    f.write(cookies_content)
                logger.info(f"✅ Cookies file created: {cookies_path}")
            except Exception as e:
                logger.error(f"❌ Failed to create cookies file: {e}")
                raise e
        else:
            logger.info(f"🔓 No authentication - downloading public content only")
        
        # Update status
        download_status[download_id]['message'] = 'Fetching video list...'
        logger.info(f"📋 Starting video list extraction...")
        
        # Progress callback function
        def progress_callback(current_index, total, current_title):
            progress = int((current_index / total) * 100) if total > 0 else 0
            logger.info(f"📊 Progress: {current_index + 1}/{total} ({progress}%) - {current_title[:30]}...")
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
        logger.info(f"🎬 Starting individual video downloads...")
        
        total_videos = len(video_urls)
        successful_downloads = []
        failed_downloads = []
        
        for i, video_url in enumerate(video_urls):
            logger.info(f"📹 Downloading video {i+1}/{total_videos}: {video_url}")
            
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
                    logger.info(f"✅ Successfully downloaded: {video_url}")
                    
                    # Try to find the downloaded video file for Facebook upload
                    try:
                        downloads_dir = Path(DOWNLOAD_CONFIG['output_dir'])
                        # Look for recently created video files
                        video_files = list(downloads_dir.glob('*.mp4')) + list(downloads_dir.glob('*.mkv')) + list(downloads_dir.glob('*.webm'))
                        if video_files:
                            # Get the most recently modified video file
                            latest_video = max(video_files, key=lambda x: x.stat().st_mtime)
                            logger.info(f"📹 Found downloaded video file: {latest_video}")
                            
                            # Extract original video title from metadata
                            video_title = downloader.extract_video_title_from_metadata(str(latest_video))
                            successful_downloads.append({'url': video_url, 'title': video_title})
                            
                            # Check if Facebook upload is enabled (from form or config)
                            from config import FACEBOOK_CONFIG
                            fb_upload_enabled = (facebook_upload and facebook_upload.get('enabled', False)) or FACEBOOK_CONFIG.get('auto_upload_enabled', False)
                            
                            if fb_upload_enabled:
                                logger.info(f"📤 Facebook upload is enabled, starting upload...")
                                
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
                                
                                logger.info(f"📝 Upload details: title='{upload_title}', description='{upload_description}'")
                                
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
                                    logger.info(f"✅ Facebook upload successful for: {video_url}")
                                    successful_downloads[-1]['facebook_upload'] = 'success'
                                    successful_downloads[-1]['facebook_result'] = upload_result
                                else:
                                    logger.error(f"❌ Facebook upload failed for: {video_url} - {upload_result}")
                                    successful_downloads[-1]['facebook_upload'] = 'failed'
                                    successful_downloads[-1]['facebook_error'] = upload_result
                            else:
                                logger.info(f"⏸️  Facebook auto-upload disabled")
                                successful_downloads[-1]['facebook_upload'] = 'disabled'
                        else:
                            # No video files found - use fallback title
                            video_title = f'Video {i+1}'
                            successful_downloads.append({'url': video_url, 'title': video_title})
                            logger.warning(f"⚠️ No video files found after download: {video_url}")
                    except Exception as upload_error:
                        logger.error(f"💥 Exception during Facebook upload: {upload_error}")
                        if successful_downloads:
                            successful_downloads[-1]['facebook_upload'] = 'error'
                            successful_downloads[-1]['facebook_error'] = str(upload_error)
                else:
                    failed_downloads.append({'url': video_url, 'title': f'Video {i+1}'})
                    logger.error(f"❌ Failed to download: {video_url}")
                    
            except Exception as e:
                failed_downloads.append({'url': video_url, 'title': f'Video {i+1}'})
                logger.error(f"💥 Exception downloading {video_url}: {e}")
        
        # Final results
        success = len(successful_downloads) > 0
        results = {
            'successful': successful_downloads,
            'failed': failed_downloads,
            'total': total_videos
        }
        
        logger.info(f"📊 Batch download completed: success={success}, results type={type(results)}")
        
        # Clean up temp cookies file
        if cookies_path and cookies_path.exists():
            logger.info(f"🧹 Cleaning up cookies file: {cookies_path}")
            cookies_path.unlink()
        
        if success:
            logger.info(f"✅ BATCH DOWNLOAD SUCCESS!")
            logger.info(f"📊 Results summary:")
            logger.info(f"   - Total videos: {results['total']}")
            logger.info(f"   - Successful: {len(results['successful'])}")
            logger.info(f"   - Failed: {len(results['failed'])}")
            
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
            logger.error(f"❌ BATCH DOWNLOAD FAILED!")
            logger.error(f"📊 Results: {results}")
            
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
        logger.error(f"💥 BATCH DOWNLOAD EXCEPTION - ID: {download_id}")
        logger.error(f"❌ Error: {error_msg}")
        logger.error(f"📋 Full traceback:")
        for line in error_trace.split('\n'):
            if line.strip():
                logger.error(f"   {line}")
        
        # Clean up temp cookies file if it exists
        if 'cookies_path' in locals() and cookies_path and cookies_path.exists():
            logger.info(f"🧹 Cleaning up cookies file after error: {cookies_path}")
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
        
        logger.info(f"Download request - URL: {url}, use_cookies: {use_cookies}")
        logger.info(f"Facebook upload settings: {facebook_upload}")
        
        if not url:
            return jsonify({'error': 'Please provide a video URL'}), 400
        
        if not (url.startswith('https://www.facebook.com/') or url.startswith('https://facebook.com/') or url.startswith('https://m.facebook.com/')):
            return jsonify({'error': 'Please provide a valid Facebook video URL'}), 400
        
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
        for url in video_urls:
            if not url.strip():
                continue
            if not (url.startswith('https://www.facebook.com/') or 
                    url.startswith('https://facebook.com/') or 
                    url.startswith('https://m.facebook.com/')):
                invalid_urls.append(url)
        
        if invalid_urls:
            return jsonify({'error': f'Invalid Facebook URLs: {invalid_urls[:3]}...'}), 400
        
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
        
        if not download_id or not video_path:
            return jsonify({'error': 'Download ID and video path are required'}), 400
        
        # Update download status
        if download_id in download_status:
            download_status[download_id]['message'] = 'Uploading to Facebook...'
            download_status[download_id]['facebook_status'] = 'uploading'
        
        # Create downloader instance
        from facebook_downloader import FacebookDownloader
        downloader = FacebookDownloader()
        
        # Perform actual upload
        upload_success, upload_result = downloader.post_download_actions(
            video_path=video_path,
            video_title=final_title,
            video_description=final_description,
            auto_upload=True
        )
        
        # Update download status with results
        if download_id in download_status:
            download_status[download_id]['facebook_upload'] = {
                'success': upload_success,
                'result': upload_result
            }
            if upload_success:
                download_status[download_id]['facebook_status'] = 'completed'
                download_status[download_id]['message'] = 'Facebook upload completed!'
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

if __name__ == '__main__':
    # Create downloads directory
    Path(DOWNLOAD_CONFIG['output_dir']).mkdir(exist_ok=True)
    
    # Run the Flask app
    print("Starting Facebook Video Downloader Web Interface...")
    print("Access the interface at: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)