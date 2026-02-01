
import subprocess

def get_logs():
    try:
        # Try to get logs from the likely container name
        # We saw 'devcontainer-web-1' in the start output
        containers = ["devcontainer-web-1", "devcontainer_web_1"]
        
        for container in containers:
            try:
                result = subprocess.run(
                    ["docker", "logs", "--tail", "50", container], 
                    capture_output=True, 
                    text=True, 
                    encoding='utf-8'
                )
                if result.returncode == 0:
                    print(f"--- Logs for {container} ---")
                    print(result.stdout)
                    print(result.stderr) # Docker logs often go to stderr
                    return
            except Exception:
                continue
                
        print("Could not retrieve logs for known container names.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_logs()
