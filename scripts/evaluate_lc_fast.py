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
    Berechnet grobe Chunk-Grenzen basierend auf Dateigröße.
    
    Args:
        file_path: Pfad zur JSON-Datei
        num_threads: Anzahl der Threads/Chunks
    
    Returns:
        Liste von groben Byte-Positionen
    """
    file_size: int = os.path.getsize(file_path)
    chunk_size: int = file_size // num_threads
    
    # Erste Boundary ist immer 0, danach grobe Unterteilungen
    boundaries: List[int] = [0]
    
    for i in range(1, num_threads):
        rough_pos: int = i * chunk_size
        boundaries.append(rough_pos)
    
    return boundaries


def find_next_opening_brace(file_path: str, start_pos: int) -> int:
    """
    Sucht ab einer gegebenen Position die nächste öffnende geschweifte Klammer '{'.
    
    Args:
        file_path: Pfad zur JSON-Datei
        start_pos: Startposition für die Suche
    
    Returns:
        Byte-Position der nächsten '{', oder -1 wenn keine gefunden
    """
    with open(file_path, 'rb') as f:
        f.seek(start_pos)
        
        position: int = start_pos
        while True:
            byte: bytes = f.read(1)
            if not byte:
                # Ende der Datei erreicht
                return -1
            
            if byte == b'{':
                # Position der '{' gefunden
                return position
            
            position += 1


def find_chunk_boundaries(file_path: str, num_threads: int) -> List[int]:
    """
    Findet exakte Chunk-Grenzen, die auf '{' Zeichen liegen.
    
    Args:
        file_path: Pfad zur JSON-Datei
        num_threads: Anzahl der Threads/Chunks
    
    Returns:
        Liste von exakten Byte-Positionen für Chunk-Starts
    """
    rough_boundaries: List[int] = calculate_rough_boundaries(file_path, num_threads)
    exact_boundaries: List[int] = [0]  # Erste Boundary bleibt bei 0
    
    # Für alle groben Boundaries (außer der ersten) die exakte Position finden
    for rough_pos in rough_boundaries[1:]:
        exact_pos: int = find_next_opening_brace(file_path, rough_pos)
        
        if exact_pos != -1:
            exact_boundaries.append(exact_pos)
        else:
            # Keine weitere '{' gefunden, wir sind am Ende
            break
    
    return exact_boundaries


def process_element(element: Dict[str, Any], stats: Dict[str, int]) -> None:
    """Verarbeite ein einzelnes JSON-Element und aktualisiere Statistiken"""
    canceled: int = element.get('update_canceled', 0)
    succeeded: int = element.get('update_succeeded', 0)
    
    stats['total_canceled'] += canceled
    stats['total_succeeded'] += succeeded
    stats['total_processed'] += 1


def process_chunk(args: Tuple[str, int, int, int, Any]) -> Dict[str, int]:
    """
    Verarbeitet einen Chunk der JSON-Datei.
    
    Args:
        args: Tuple von (file_path, start_byte, end_byte, chunk_id, progress_dict)
    
    Returns:
        Dictionary mit Statistiken für diesen Chunk
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
            
            # Update progress alle 100KB
            if bytes_read % 100000 == 0:
                progress_dict[chunk_id] = (bytes_read / max_bytes) * 100.0
            
            if byte == b'{':
                bracket_count += 1
                buffer += byte
            elif byte == b'}':
                buffer += byte
                bracket_count -= 1
                
                if bracket_count == 0 and buffer.strip():
                    # Komplettes Objekt gefunden
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
    Überwacht den Fortschritt und gibt Updates aus.
    
    Args:
        progress_dict: Shared dictionary mit Progress-Werten pro Chunk
        num_chunks: Gesamtzahl der Chunks
        stop_event: Event zum Beenden des Monitors
    """
    while not stop_event.is_set():
        # Berechne Gesamt-Progress
        total_progress: float = sum(progress_dict.get(i, 0.0) for i in range(num_chunks))
        avg_progress: float = total_progress / num_chunks if num_chunks > 0 else 0.0
        
        # Ausgabe mit Carriage Return (überschreibt vorherige Zeile)
        print(f"\rProgress: {avg_progress:.2f}%", end='', flush=True)
        
        time.sleep(1)
    
    # Final newline nach Completion
    print()


def parallel_stream_json(file_path: str, num_threads: int) -> Dict[str, int]:
    """
    Verarbeitet JSON-Datei parallel mit mehreren Prozessen.
    
    Args:
        file_path: Pfad zur JSON-Datei
        num_threads: Anzahl der parallelen Prozesse
    
    Returns:
        Aggregierte Statistiken über alle Chunks
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
    
    # Erstelle Chunk-Argumente: (file_path, start, end, chunk_id, progress_dict)
    chunk_args: List[Tuple[str, int, int, int, Any]] = []
    for i in range(len(boundaries)):
        start: int = boundaries[i]
        end: int = boundaries[i + 1] - 1 if i + 1 < len(boundaries) else file_size
        chunk_args.append((file_path, start, end, i, progress_dict))
    
    print(f"\nProcessing {len(chunk_args)} chunks in parallel...\n")
    start_time: float = time.time()
    
    # Starte Progress Monitor Thread
    stop_event = threading.Event()
    monitor_thread = threading.Thread(
        target=progress_monitor,
        args=(progress_dict, len(boundaries), stop_event)
    )
    monitor_thread.start()
    
    # Parallel verarbeiten
    with ProcessPoolExecutor(max_workers=num_threads) as executor:
        results: List[Dict[str, int]] = list(executor.map(process_chunk, chunk_args))
    
    # Stoppe Progress Monitor
    stop_event.set()
    monitor_thread.join()
    
    end_time: float = time.time()
    
    # Aggregiere Ergebnisse
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
        print("GESAMTSTATISTIK")
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
            print("\nKeine Updates gefunden")
        
        print("\n✓ Verarbeitung abgeschlossen")
    except FileNotFoundError:
        print(f"Fehler: Datei '{json_file}' nicht gefunden")
    except Exception as e:
        print(f"Fehler: {e}")
        import traceback
        traceback.print_exc()
