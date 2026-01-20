import json
import sys

def process_element(element, index, stats):
    """Verarbeite ein einzelnes JSON-Element"""
    #print(f"\n--- Element {index} ---")
    #print(f"N: {element.get('N')}")
    #print(f"Hash: {element.get('hash')}")
    #print(f"Irr: {element.get('irr')}")
    
    canceled = element.get('update_canceled', 0)
    succeeded = element.get('update_succeeded', 0)
    
    #print(f"Update canceled: {canceled}")
    #print(f"Update succeeded: {succeeded}")
    if index % 10000 == 0:
        print(f"Element idx: {index}")
    
    # Summiere für Gesamtstatistik
    stats['total_canceled'] += canceled
    stats['total_succeeded'] += succeeded
    
    return stats

def stream_json_array(file_path):
    """Liest JSON-Array Element für Element"""
    stats = {'total_canceled': 0, 'total_succeeded': 0}
    
    with open(file_path, 'r', encoding='utf-8') as f:
        # Überspringe das öffnende '['

        f.read(1)
        
        buffer = ""
        bracket_count = 0
        index = 0
        
        while True:
            char = f.read(1)
            if not char:
                break
            
            if char == '{':
                bracket_count += 1
                buffer += char
            elif char == '}':
                buffer += char
                bracket_count -= 1
                
                if bracket_count == 0 and buffer.strip():
                    # Komplettes Objekt gefunden
                    try:
                        element = json.loads(buffer.strip())
                        stats = process_element(element, index, stats)
                        index += 1
                    except json.JSONDecodeError as e:
                        print(f"Fehler beim Parsen von Element {index}: {e}")
                    
                    buffer = ""
            elif bracket_count > 0:
                buffer += char
    
    return stats

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python evaluate_json.py <path_to_json_file>")
        sys.exit(1)
    
    json_file = sys.argv[1]
    
    try:
        stats = stream_json_array(json_file)
        
        print("\n" + "="*50)
        print("GESAMTSTATISTIK")
        print("="*50)
        print(f"Total canceled: {stats['total_canceled']}")
        print(f"Total succeeded: {stats['total_succeeded']}")
        
        total = stats['total_canceled'] + stats['total_succeeded']
        if total > 0:
            percent_canceled = (stats['total_canceled'] / total) * 100
            percent_succeeded = (stats['total_succeeded'] / total) * 100
            print(f"\n{percent_canceled:.2f}% failed")
            print(f"{percent_succeeded:.2f}% succeeded")
        else:
            print("\nKeine Updates gefunden")
        
        print("\n✓ Verarbeitung abgeschlossen")
    except FileNotFoundError:
        print(f"Fehler: Datei '{json_file}' nicht gefunden")
    except Exception as e:
        print(f"Fehler: {e}")