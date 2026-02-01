
import sys

filename = 'upgrade_retry_log.txt'

try:
    with open(filename, 'r', encoding='utf-8', errors='replace') as f:
        print(f.read())
except Exception as e:
    print(f"Error reading {filename}: {e}")
