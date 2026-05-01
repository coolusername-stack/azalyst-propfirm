import os
import json
import argparse
import glob

def merge_results(input_dir, output_file):
    all_signals = []
    
    # Find all chunk result files
    # The workflow downloads artifacts into subdirectories, so we search recursively
    pattern = os.path.join(input_dir, "**", "chunk_result_*.json")
    files = glob.glob(pattern, recursive=True)
    
    print(f"Found {len(files)} chunk files to merge.")
    
    for file_path in files:
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                # Handle both list of signals or full result dict
                if isinstance(data, list):
                    all_signals.extend(data)
                elif isinstance(data, dict) and 'signals' in data:
                    all_signals.extend(data['signals'])
                else:
                    print(f"Warning: Unexpected format in {file_path}")
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            
    # Save merged results
    with open(output_file, 'w') as f:
        json.dump(all_signals, f, indent=2)
        
    print(f"Merged {len(all_signals)} total signals into {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-dir', required=True)
    parser.add_argument('--output-file', default='final_scan_results.json')
    args = parser.parse_args()
    
    merge_results(args.input_dir, args.output_file)
