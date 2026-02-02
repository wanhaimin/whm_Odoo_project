
filename = 'upgrade_chatter_log.txt'
try:
    with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        if "AttributeError" in content or "Traceback" in content:
            print("FOUND ERROR")
            # print surrounding lines
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if "AttributeError" in line or "Traceback" in line:
                    print(line)
                    print('\n'.join(lines[max(0, i-5):min(len(lines), i+15)])) # Context
                    break # Just show first error
        else:
            print("NO ERROR FOUND")
            # print last few lines to confirm success
            print("\nLast 5 lines:")
            print('\n'.join(content.split('\n')[-5:]))

except Exception as e:
    print(f"Check failed: {e}")
