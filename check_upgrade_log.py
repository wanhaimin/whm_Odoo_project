
filename = 'upgrade_location_log.txt'
try:
    with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        if "Traceback" in content or "ERROR" in content or "Error" in content:
            print("FOUND ERROR in log:")
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if "Traceback" in line or "ERROR" in line or ("Error" in line and "error_correction" not in line):
                    # Print context: 10 lines before and 20 after
                    start = max(0, i-10)
                    end = min(len(lines), i+20)
                    print('\n'.join(lines[start:end]))
                    break
        else:
            print("NO CRITICAL ERROR FOUND")
            print("\nLast 10 lines:")
            print('\n'.join(content.split('\n')[-10:]))

except Exception as e:
    print(f"Check failed: {e}")
