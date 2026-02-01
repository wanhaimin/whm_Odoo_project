
try:
    with open('upgrade_log.txt', 'r', encoding='utf-16-le') as f:
        print(f.read())
except:
    try:
        with open('upgrade_log.txt', 'r', encoding='utf-8') as f:
            print(f.read())
    except Exception as e:
        print(f"Error reading file: {e}")
