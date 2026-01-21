import json
import sys
import os
import time
from typing import Dict, Any, List, Tuple
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import Manager
import threading


def calculate_rough_boundaries(file_path: str, num_threads: int) -> List[int]:
    """
    Calculates rough chunk boundaries based on file size.
    
    Args:
        file_path: Path to JSON file
        num_threads: Number of threads/chunks
    
    Returns:
        List of rough byte positions
    """
    file_size: int = os.path.getsize(file_path)
    chunk_size: int = file_size // num_threads
    
    # First boundary is always 0, then rough subdivisions
    boundaries: List[int] = [0]
    
    for i in range(1, num_threads):
        rough_pos: int = i * chunk_size
        boundaries.append(rough_pos)
    
    return boundaries


def find_next_opening_brace(file_path: str, start_pos: int) -> int:
    """
    Searches for the next opening brace '{' from a given position.
    
    Args:
        file_path: Path to JSON file
        start_pos: Start position for search
    
    Returns:
        Byte position of next '{', or -1 if none found
    """
    with open(file_path, 'rb') as f:
        f.seek(start_pos)
        
        position: int = start_pos
        while True:
            byte: bytes = f.read(1)
            if not byte:
                # End of file reached
                return -1
            
            if byte == b'{':
                # Found position of '{'
                return position
            
            position += 1


def find_chunk_boundaries(file_path: str, num_threads: int) -> List[int]:
    """
    Finds exact chunk boundaries that align with '{' characters.
    
    Args:
        file_path: Path to JSON file
        num_threads: Number of threads/chunks
    
    Returns:
        List of exact byte positions for chunk starts
    """
    rough_boundaries: List[int] = calculate_rough_boundaries(file_path, num_threads)
    exact_boundaries: List[int] = [0]  # First boundary stays at 0
    
    # Find exact position for all rough boundaries (except the first)
    for rough_pos in rough_boundaries[1:]:
        exact_pos: int = find_next_opening_brace(file_path, rough_pos)
        
        if exact_pos != -1:
            exact_boundaries.append(exact_pos)
        else:
            # No more '{' found, we're at the end
            break
    
    return exact_boundaries


def process_element(element: Dict[str, Any], stats: Dict[str, int]) -> None:
    """Process a single JSON element and update statistics"""
    canceled: int = element.get('update_canceled', 0)
    succeeded: int = element.get('update_succeeded', 0)
    
    stats['total_canceled'] += canceled
    stats['total_succeeded'] += succeeded
    stats['total_processed'] += 1


def process_chunk(args: Tuple[str, int, int, int, Any]) -> Dict[str, int]:
    """
    Processes a chunk of the JSON file.
    
    Args:
        args: Tuple of (file_path, start_byte, end_byte, chunk_id, progress_dict)
    
    Returns:
        Dictionary with statistics for this chunk
    """
    file_path, start_byte, end_byte, chunk_id, progress_dict = args
    stats: Dict[str, int] = {
        'total_canceled': 0,
        'total_succeeded': 0,
        'total_processed': 0
    }
    
    max_bytes: int = end_byte - start_byte if end_byte != -1 else float('inf')
    
    with open(file_path, 'rb') as f:
        f.seek(start_byte)
        
        buffer: bytes = b""
        bracket_count: int = 0
        bytes_read: int = 0
        
        while bytes_read < max_bytes:
            byte: bytes = f.read(1)
            if not byte:
                break
            
            bytes_read += 1
            
            # Update progress every 100KB
            if bytes_read % 100000 == 0:
                progress_dict[chunk_id] = (bytes_read / max_bytes) * 100.0
            
            if byte == b'{':
                bracket_count += 1
                buffer += byte
            elif byte == b'}':
                buffer += byte
                bracket_count -= 1
                
                if bracket_count == 0 and buffer.strip():
                    # Complete object found
                    try:
                        element: Dict[str, Any] = json.loads(buffer.decode('utf-8').strip())
                        process_element(element, stats)
                    except (json.JSONDecodeError, UnicodeDecodeError) as e:
                        pass  # Silent error handling
                    
                    buffer = b""
            elif bracket_count > 0:
                buffer += byte
    
    # Final progress update
    progress_dict[chunk_id] = 100.0
    return stats


def progress_monitor(progress_dict: Dict[int, float], num_chunks: int, stop_event: threading.Event) -> None:
    """
    Monitors progress and prints updates.
    
    Args:
        progress_dict: Shared dictionary with progress values per chunk
        num_chunks: Total number of chunks
        stop_event: Event to stop the monitor
    """
    while not stop_event.is_set():
        # Calculate total progress
        total_progress: float = sum(progress_dict.get(i, 0.0) for i in range(num_chunks))
        avg_progress: float = total_progress / num_chunks if num_chunks > 0 else 0.0
        
        # Output with carriage return (overwrites previous line)
        print(f"\rProgress: {avg_progress:.2f}%", end='', flush=True)
        
        time.sleep(1)
    
    # Final newline after completion
    print()


def parallel_stream_json(file_path: str, num_threads: int) -> Dict[str, int]:
    """
    Processes JSON file in parallel with multiple processes.
    
    Args:
        file_path: Path to JSON file
        num_threads: Number of parallel processes
    
    Returns:
        Aggregated statistics across all chunks
    """
    print(f"\nFinding chunk boundaries...")
    boundaries: List[int] = find_chunk_boundaries(file_path, num_threads)
    file_size: int = os.path.getsize(file_path)
    
    print(f"Found {len(boundaries)} chunks")
    
    # Shared progress dictionary
    manager = Manager()
    progress_dict = manager.dict()
    for i in range(len(boundaries)):
        progress_dict[i] = 0.0
    
    # Create chunk arguments: (file_path, start, end, chunk_id, progress_dict)
    chunk_args: List[Tuple[str, int, int, int, Any]] = []
    for i in range(len(boundaries)):
        start: int = boundaries[i]
        end: int = boundaries[i + 1] - 1 if i + 1 < len(boundaries) else file_size
        chunk_args.append((file_path, start, end, i, progress_dict))
    
    print(f"\nProcessing {len(chunk_args)} chunks in parallel...\n")
    start_time: float = time.time()
    
    # Start progress monitor thread
    stop_event = threading.Event()
    monitor_thread = threading.Thread(
        target=progress_monitor,
        args=(progress_dict, len(boundaries), stop_event)
    )
    monitor_thread.start()
    
    # Process in parallel
    with ProcessPoolExecutor(max_workers=num_threads) as executor:
        results: List[Dict[str, int]] = list(executor.map(process_chunk, chunk_args))
    
    # Stop progress monitor
    stop_event.set()
    monitor_thread.join()
    
    end_time: float = time.time()
    
    # Aggregate results
    total_stats: Dict[str, int] = {
        'total_canceled': sum(r['total_canceled'] for r in results),
        'total_succeeded': sum(r['total_succeeded'] for r in results),
        'total_processed': sum(r['total_processed'] for r in results)
    }
    
    print(f"Processing completed in {end_time - start_time:.2f} seconds")
    
    return total_stats


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python evaluate_lc_fast.py <path_to_json_file> [num_threads]")
        sys.exit(1)
    
    json_file: str = sys.argv[1]
    num_threads: int = int(sys.argv[2]) if len(sys.argv) > 2 else (os.cpu_count() or 4)
    
    print(f"CPU Cores available: {os.cpu_count()}")
    print(f"Using {num_threads} threads")
    print(f"Analyzing file: {json_file}")
    
    try:
        stats: Dict[str, int] = parallel_stream_json(json_file, num_threads)
        
        print("\n" + "="*50)
        print("OVERALL STATISTICS")
        print("="*50)
        print(f"Total processed: {stats['total_processed']}")
        print(f"Total canceled: {stats['total_canceled']}")
        print(f"Total succeeded: {stats['total_succeeded']}")
        
        total: int = stats['total_canceled'] + stats['total_succeeded']
        if total > 0:
            percent_canceled: float = (stats['total_canceled'] / total) * 100
            percent_succeeded: float = (stats['total_succeeded'] / total) * 100
            print(f"\n{percent_canceled:.2f}% failed")
            print(f"{percent_succeeded:.2f}% succeeded")
        else:
            print("\nNo updates found")
        
        print("\n✓ Processing completed")
    except FileNotFoundError:
        print(f"Error: File '{json_file}' not found")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
