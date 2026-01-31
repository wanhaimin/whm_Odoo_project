
import socket
import ssl
import sys

hostname = 'smtp.163.com'

def test_ssl_465():
    port = 465
    print(f"\n--- Testing Port {port} (SSL/TLS) ---")
    context = ssl.create_default_context()
    try:
        with socket.create_connection((hostname, port), timeout=5) as sock:
            print("TCP Connected.")
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                print("SSL Handshake Successful!")
                cert = ssock.getpeercert()
                subject = dict(x[0] for x in cert['subject'])
                issuer = dict(x[0] for x in cert['issuer'])
                print(f"Cert Subject: {subject.get('commonName')}")
                print(f"Cert Issuer: {issuer.get('commonName')}")
    except Exception as e:
        print(f"FAILED: {e}")

def test_starttls_25():
    port = 25
    print(f"\n--- Testing Port {port} (STARTTLS) ---")
    try:
        with socket.create_connection((hostname, port), timeout=5) as sock:
            print("TCP Connected.")
            # Read banner
            banner = sock.recv(1024)
            print(f"Banner: {banner.decode().strip()}")
            # Send EHLO
            sock.sendall(b'EHLO test\r\n')
            res = sock.recv(1024)
            # Send STARTTLS
            sock.sendall(b'STARTTLS\r\n')
            res = sock.recv(1024)
            print(f"STARTTLS Response: {res.decode().strip()}")
            
            if b'2.0.0' in res or b'220' in res:
                context = ssl.create_default_context()
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                     print("SSL Handshake after STARTTLS Successful!")
            else:
                print("Server did not accept STARTTLS")

    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    test_ssl_465()
    test_starttls_25()
