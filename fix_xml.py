import os

path = r'custom_addons\diecut\views\website_templates.xml'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace typical HTML entities that XML/LXML might complain about
content = content.replace('&times;', '&#215;')
content = content.replace('×', '&#215;')
# Also check for &nbsp;
content = content.replace('&nbsp;', '&#160;')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed XML entities in website_templates.xml")
