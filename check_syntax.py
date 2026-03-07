import traceback, sys, ast
try:
    with open('custom_addons/diecut/wizard/catalog_activate_wizard.py', encoding='utf-8') as f:
        ast.parse(f.read())
    print("Syntax works!")
except Exception as e:
    traceback.print_exc()
