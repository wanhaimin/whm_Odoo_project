
import os

root_dir = r"e:\workspace\my_odoo_project\custom_addons\diecut_custom"

def search_ondelete():
    print("Searching...")
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith(".py"):
                path = os.path.join(dirpath, filename)
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                        for i, line in enumerate(lines):
                            if "ondelete" in line:
                                print(f"{filename}:{i+1}: {line.strip()}")
                except Exception as e:
                    print(f"Error reading {path}: {e}")

if __name__ == "__main__":
    search_ondelete()
