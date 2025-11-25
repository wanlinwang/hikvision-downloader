#!/usr/bin/python3

"""
Download media from all channels of a Hikvision NVR/DVR.
Automatically detects all available channels and downloads videos from each.
"""

import os
import sys
import argparse
import threading
from datetime import timedelta
from queue import Queue

# Import from the main script
from media_download import (
    user_name, user_password, ContentType,
    MAX_NUMBER_OF_FILES_IN_ONE_REQUEST,
    DELAY_BETWEEN_DOWNLOADING_FILES_SECONDS,
    DELAY_AFTER_TIMEOUT_SECONDS,
    CAMERA_REBOOT_TIME_SECONDS,
    DELAY_BEFORE_CHECKING_AVAILABILITY_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    write_logs,
    base_path_to_log_file,
    MAX_BYTES_LOG_FILE_SIZE,
    MAX_LOG_FILES_COUNT,
    path_to_media_archive
)

from src.camera_sdk import CameraSdk, AuthType
from src.logger import Logger
from src.time_interval import TimeInterval
from src.log_wrapper import logging_wrapper
from src.log_printer import LogPrinter
from src.utils import *
from src.track import Track

# ====== Multi-channel Parameters ======
MAX_CONCURRENT_DOWNLOADS = 3  # Maximum number of channels to download from simultaneously
MAX_CHANNEL_TO_SCAN = 32  # Maximum channel number to scan (most NVRs have 4, 8, 16, or 32 channels)
# ======================================


def get_path_to_video_archive(nvr_ip: str, channel_num: int = None):
    """Get the path for video archive, optionally including channel subdirectory."""
    base_path = path_to_media_archive + nvr_ip
    if channel_num is not None:
        return base_path + f'/channel_{channel_num:02d}/'
    return base_path + '/'


def get_available_channels(auth_handler, nvr_ip, utc_time_interval, content_type, max_channel=MAX_CHANNEL_TO_SCAN):
    """
    Scan NVR to find all channels that have recorded media.
    
    Args:
        auth_handler: Authentication handler
        nvr_ip: IP address of the NVR
        utc_time_interval: Time interval to check for recordings
        content_type: Type of content (VIDEO or PHOTO)
        max_channel: Maximum channel number to scan
    
    Returns:
        List of channel numbers that have recordings
    """
    available_channels = []
    
    print(f"\nScanning NVR {nvr_ip} for available channels...")
    print(f"(This may take a moment, checking channels 1-{max_channel})")
    
    # Determine track ID base (101 for video, 103 for photo)
    if content_type == ContentType.VIDEO:
        track_id_base = 101
    else:
        track_id_base = 103
    
    for channel_num in range(1, max_channel + 1):
        # Calculate track ID: channel 1 = 101, channel 2 = 201, etc.
        track_id = (channel_num * 100) + (track_id_base % 100)
        
        try:
            # Try to get tracks for this channel
            answer = CameraSdk.get_tracks_info(
                auth_handler, 
                nvr_ip, 
                utc_time_interval, 
                1,  # Only need to check if any tracks exist
                track_id
            )
            
            if answer and answer.ok:
                # Parse response to check if there are any tracks
                local_time_offset = utc_time_interval.local_time_offset
                tracks = CameraSdk.create_tracks_from_info(answer, local_time_offset)
                
                if len(tracks) > 0:
                    available_channels.append(channel_num)
                    print(f"  ✓ Channel {channel_num:02d} has recordings")
            
        except Exception as e:
            # Channel likely doesn't exist or has no recordings
            pass
    
    print(f"\nFound {len(available_channels)} channel(s) with recordings: {available_channels}\n")
    return available_channels


def download_channel_media(auth_handler, nvr_ip, channel_num, utc_time_interval, content_type):
    """
    Download media from a specific channel.
    
    Args:
        auth_handler: Authentication handler
        nvr_ip: IP address of the NVR
        channel_num: Channel number (1-32)
        utc_time_interval: Time interval to download
        content_type: Type of content (VIDEO or PHOTO)
    
    Returns:
        Number of files downloaded
    """
    logger = Logger.get_logger()
    
    # Calculate track ID
    if content_type == ContentType.VIDEO:
        track_id = (channel_num * 100) + 1
    else:
        track_id = (channel_num * 100) + 3
    
    logger.info(f'Channel {channel_num:02d}: Getting track list...')
    
    # Get all tracks for this channel
    tracks = []
    search_interval = TimeInterval(
        utc_time_interval.start_time,
        utc_time_interval.end_time,
        utc_time_interval.local_time_offset
    )
    
    while True:
        try:
            answer = CameraSdk.get_tracks_info(
                auth_handler,
                nvr_ip,
                search_interval,
                MAX_NUMBER_OF_FILES_IN_ONE_REQUEST,
                track_id
            )
            
            if answer and answer.ok:
                local_time_offset = search_interval.local_time_offset
                new_tracks = CameraSdk.create_tracks_from_info(answer, local_time_offset)
                tracks += new_tracks
                
                if len(new_tracks) < MAX_NUMBER_OF_FILES_IN_ONE_REQUEST:
                    break
                
                # Move to next batch
                last_track = tracks[-1]
                search_interval.start_time = last_track.get_time_interval().end_time
            else:
                break
                
        except Exception as e:
            logger.error(f'Channel {channel_num:02d}: Error getting tracks: {e}')
            break
    
    logger.info(f'Channel {channel_num:02d}: Found {len(tracks)} files')
    
    # Download all tracks
    downloaded_count = 0
    for track in tracks:
        while True:
            if download_file_with_retry(auth_handler, nvr_ip, channel_num, track, content_type):
                downloaded_count += 1
                break
            else:
                import time
                time.sleep(DELAY_AFTER_TIMEOUT_SECONDS)
        
        import time
        time.sleep(DELAY_BETWEEN_DOWNLOADING_FILES_SECONDS)
    
    return downloaded_count


def download_file_with_retry(auth_handler, nvr_ip, channel_num, track, content_type):
    """Download a single file with retry logic."""
    logger = Logger.get_logger()
    
    start_time_text = track.get_time_interval().to_local_time().to_filename_text()
    sanitized_time_text = sanitize_filename(start_time_text)
    file_name = get_path_to_video_archive(nvr_ip, channel_num) + sanitized_time_text + '.' + content_type
    url_to_download = track.url_to_download()
    
    # Validate the file path
    base_archive_path = os.path.abspath(path_to_media_archive)
    if not validate_path(file_name, base_archive_path):
        logger.error(f'Channel {channel_num:02d}: Invalid file path detected: {file_name}')
        return False
    
    create_directory_for(file_name)
    
    logger.info(f'Channel {channel_num:02d}: Downloading {os.path.basename(file_name)}')
    
    status = CameraSdk.download_file(auth_handler, nvr_ip, url_to_download, file_name)
    
    if status.result_type == CameraSdk.FileDownloadingResult.OK:
        return True
    else:
        if status.result_type == CameraSdk.FileDownloadingResult.TIMEOUT:
            logger.error(f"Channel {channel_num:02d}: Timeout during file downloading")
        elif status.result_type == CameraSdk.FileDownloadingResult.DEVICE_ERROR:
            logger.error(f"Channel {channel_num:02d}: Device error - {status.text}")
            # Note: We don't reboot for multi-channel downloads as it would affect all channels
        else:
            logger.error(f"Channel {channel_num:02d}: {status.text}")
        return False


def download_from_channel_worker(auth_handler, nvr_ip, channel_num, utc_time_interval, content_type, results_queue):
    """Worker function for downloading from a single channel in a thread."""
    try:
        # Initialize logger for this channel
        log_file_name = base_path_to_log_file + f'{nvr_ip}_channel_{channel_num:02d}.log'
        create_directory_for(log_file_name)
        
        count = download_channel_media(auth_handler, nvr_ip, channel_num, utc_time_interval, content_type)
        results_queue.put((channel_num, True, count, None))
        print(f"✓ Channel {channel_num:02d}: Successfully downloaded {count} files")
    except Exception as e:
        results_queue.put((channel_num, False, 0, str(e)))
        print(f"✗ Channel {channel_num:02d}: Failed - {e}")


def download_from_all_channels(nvr_ip, start_datetime_str, end_datetime_str, use_utc_time, content_type, 
                                max_concurrent, max_channel, specific_channels=None):
    """
    Download media from all available channels of an NVR.
    
    Args:
        nvr_ip: IP address of the NVR
        start_datetime_str: Start datetime string
        end_datetime_str: End datetime string
        use_utc_time: Whether to use UTC time
        content_type: Type of content (VIDEO or PHOTO)
        max_concurrent: Maximum number of concurrent downloads
        max_channel: Maximum channel number to scan
        specific_channels: List of specific channel numbers to download (None = auto-detect)
    """
    logger = Logger.get_logger()
    
    try:
        logger.info(f'Connecting to NVR {nvr_ip}...')
        
        # Authenticate
        auth_type = CameraSdk.get_auth_type(nvr_ip, user_name, user_password)
        if auth_type == AuthType.UNAUTHORISED:
            raise RuntimeError('Unauthorised! Check login and password')
        
        auth_handler = CameraSdk.get_auth(auth_type, user_name, user_password)
        
        # Get time offset
        if use_utc_time:
            local_time_offset = timedelta()
        else:
            local_time_offset = CameraSdk.get_time_offset(auth_handler, nvr_ip)
        
        utc_time_interval = TimeInterval.from_string(start_datetime_str, end_datetime_str, local_time_offset).to_utc()
        
        # Determine which channels to download
        if specific_channels:
            channels = specific_channels
            print(f"\nDownloading from specified channels: {channels}")
        else:
            channels = get_available_channels(auth_handler, nvr_ip, utc_time_interval, content_type, max_channel)
        
        if not channels:
            print("No channels found with recordings in the specified time range.")
            return {}
        
        print(f"\nStarting download from {len(channels)} channel(s)...")
        print(f"Time range: {start_datetime_str} to {end_datetime_str}")
        print(f"Content type: {'Photos' if content_type == ContentType.PHOTO else 'Videos'}")
        print(f"Max concurrent downloads: {max_concurrent}\n")
        
        # Download from all channels with threading
        results_queue = Queue()
        threads = []
        active_threads = []
        
        # Create threads for all channels
        for channel_num in channels:
            thread = threading.Thread(
                target=download_from_channel_worker,
                args=(auth_handler, nvr_ip, channel_num, utc_time_interval, content_type, results_queue)
            )
            threads.append((channel_num, thread))
        
        # Start threads with concurrency limit
        thread_index = 0
        while thread_index < len(threads) or active_threads:
            # Start new threads if under the limit
            while len(active_threads) < max_concurrent and thread_index < len(threads):
                channel_num, thread = threads[thread_index]
                print(f"Starting download from channel {channel_num:02d}...")
                thread.start()
                active_threads.append((channel_num, thread))
                thread_index += 1
            
            # Remove completed threads
            for channel_num, thread in active_threads[:]:
                if not thread.is_alive():
                    thread.join()
                    active_threads.remove((channel_num, thread))
            
            # Brief sleep to avoid busy waiting
            if active_threads:
                import time
                time.sleep(0.1)
        
        # Collect results
        results = {}
        while not results_queue.empty():
            channel_num, success, count, error = results_queue.get()
            results[channel_num] = {'success': success, 'count': count, 'error': error}
        
        return results
        
    except Exception as e:
        logger.exception(e)
        raise


def print_summary(nvr_ip, results):
    """Print a summary of download results."""
    print("\n" + "="*70)
    print(f"DOWNLOAD SUMMARY FOR NVR: {nvr_ip}")
    print("="*70)
    
    successful = [ch for ch, result in results.items() if result['success']]
    failed = [ch for ch, result in results.items() if not result['success']]
    total_files = sum(result['count'] for result in results.values() if result['success'])
    
    print(f"\nTotal channels processed: {len(results)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")
    print(f"Total files downloaded: {total_files}")
    
    if successful:
        print("\n✓ Successful channels:")
        for ch in sorted(successful):
            count = results[ch]['count']
            print(f"  - Channel {ch:02d}: {count} files")
    
    if failed:
        print("\n✗ Failed channels:")
        for ch in sorted(failed):
            error = results[ch]['error']
            print(f"  - Channel {ch:02d}: {error}")
    
    print("="*70 + "\n")


def parse_channels(channels_str):
    """
    Parse channel numbers from string.
    Supports: "1,2,3" or "1-4" or "1,3-5,7"
    """
    if not channels_str:
        return None
    
    channels = []
    parts = channels_str.split(',')
    
    for part in parts:
        part = part.strip()
        if '-' in part:
            # Range like "1-4"
            start, end = part.split('-')
            channels.extend(range(int(start), int(end) + 1))
        else:
            # Single channel
            channels.append(int(part))
    
    return sorted(list(set(channels)))  # Remove duplicates and sort


def parse_parameters():
    usage = """
  %(prog)s [-u] [-p] [-c MAX_CONCURRENT] [-m MAX_CHANNEL] [--channels CHANNELS] NVR_IP START_DATE START_TIME END_DATE END_TIME"""

    epilog = """
Examples:
  # Auto-detect and download all channels
  %(prog)s 10.19.2.2 2024-11-25 08:00:00 2024-11-25 18:00:00
  
  # Download specific channels only
  %(prog)s --channels 1,2,3 10.19.2.2 2024-11-25 08:00:00 2024-11-25 18:00:00
  
  # Download channel range
  %(prog)s --channels 1-8 10.19.2.2 2024-11-25 08:00:00 2024-11-25 18:00:00
  
  # Scan up to 64 channels with 5 concurrent downloads
  %(prog)s -m 64 -c 5 10.19.2.2 2024-11-25 08:00:00 2024-11-25 18:00:00
  
  # Download photos instead of videos
  %(prog)s -p 10.19.2.2 2024-11-25 08:00:00 2024-11-25 18:00:00

Environment Variables:
  HIK_USERNAME: Camera username (required)
  HIK_PASSWORD: Camera password (required)
        """

    parser = argparse.ArgumentParser(
        usage=usage,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Download media from all channels of a Hikvision NVR/DVR"
    )
    parser.add_argument("NVR_IP", help="NVR/DVR IP address")
    parser.add_argument("START_DATE", help="start date of interval (YYYY-MM-DD)")
    parser.add_argument("START_TIME", help="start time of interval (HH:MM:SS)")
    parser.add_argument("END_DATE", help="end date of interval (YYYY-MM-DD)")
    parser.add_argument("END_TIME", help="end time of interval (HH:MM:SS)")
    parser.add_argument("-u", "--utc", help="use parameters as UTC time", action="store_true")
    parser.add_argument("-p", "--photo", help="download photos instead of videos", action="store_true")
    parser.add_argument("-c", "--concurrent", type=int, default=MAX_CONCURRENT_DOWNLOADS,
                       help=f"maximum number of concurrent channel downloads (default: {MAX_CONCURRENT_DOWNLOADS})")
    parser.add_argument("-m", "--max-channel", type=int, default=MAX_CHANNEL_TO_SCAN,
                       help=f"maximum channel number to scan (default: {MAX_CHANNEL_TO_SCAN})")
    parser.add_argument("--channels", type=str,
                       help="specific channels to download (e.g., '1,2,3' or '1-8'). If not specified, auto-detect all channels")

    if len(sys.argv) == 1:
        parser.print_help()
        return None
    else:
        args = parser.parse_args()
        return args


def init(nvr_ip):
    """Initialize logger and directories."""
    log_file_name = base_path_to_log_file + f'{nvr_ip}_main.log'
    
    create_directory_for(log_file_name)
    create_directory_for(get_path_to_video_archive(nvr_ip))
    
    Logger.init_logger(write_logs, log_file_name, MAX_BYTES_LOG_FILE_SIZE, MAX_LOG_FILES_COUNT)
    CameraSdk.init(DEFAULT_TIMEOUT_SECONDS)


def main():
    parameters = parse_parameters()
    if parameters:
        try:
            # Validate credentials
            if not user_name or not user_password:
                print("Error: Camera credentials not provided.")
                print("Please set HIK_USERNAME and HIK_PASSWORD environment variables.")
                print("Example (PowerShell): $env:HIK_USERNAME='admin'; $env:HIK_PASSWORD='yourpassword'")
                return
            
            nvr_ip = parameters.NVR_IP
            init(nvr_ip)
            
            start_datetime_str = parameters.START_DATE + ' ' + parameters.START_TIME
            end_datetime_str = parameters.END_DATE + ' ' + parameters.END_TIME
            
            content_type = ContentType.PHOTO if parameters.photo else ContentType.VIDEO
            
            # Parse specific channels if provided
            specific_channels = parse_channels(parameters.channels) if parameters.channels else None
            
            # Download from all channels
            results = download_from_all_channels(
                nvr_ip,
                start_datetime_str,
                end_datetime_str,
                parameters.utc,
                content_type,
                parameters.concurrent,
                parameters.max_channel,
                specific_channels
            )
            
            # Print summary
            print_summary(nvr_ip, results)
            
        except KeyboardInterrupt:
            print('\n\nDownload interrupted by user.')
            sys.exit(1)
        
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == '__main__':
    main()
