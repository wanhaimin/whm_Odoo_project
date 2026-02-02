import re

file_path = 'custom_addons/diecut_custom/views/mold_views.xml'

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
    
# Check lines around line 36
for i in range(34, min(45, len(lines))):
    line = lines[i]
    # Check for fancy quotes
    if ''' in line or ''' in line or '"' in line or '"' in line:
        print(f"Line {i+1} has fancy quotes:")
        print(repr(line))
    # Check line 36 specifically
    if i == 35:
        print(f"\nLine 36 content:")
        print(repr(line))
        print(f"Bytes: {line.encode('utf-8')}")
