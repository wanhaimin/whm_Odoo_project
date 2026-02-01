
filename = 'upgrade_retry_log.txt'
try:
    with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        if "AttributeError" in content:
            print("FOUND ERROR")
            # print surrounding lines
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if "AttributeError" in line:
                    print(line)
                    print(lines[i-5:i+5]) # Context
        else:
            print("NO ERROR FOUND")
except Exception as e:
    print(f"Check failed: {e}")
