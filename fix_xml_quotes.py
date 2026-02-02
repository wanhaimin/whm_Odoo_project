import re

file_path = 'custom_addons/diecut_custom/views/mold_views.xml'

# Read file
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace fancy quotes with standard quotes
content = content.replace(''', "'")
content = content.replace(''', "'")
content = content.replace('"', '"')
content = content.replace('"', '"')

# Write back
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed fancy quotes in mold_views.xml")
