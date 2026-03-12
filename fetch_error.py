import urllib.request
from urllib.error import HTTPError

try:
    response = urllib.request.urlopen('http://localhost:8070/odoo/apps?debug=1')
    print(response.read().decode('utf-8'))
except HTTPError as e:
    print("HTTP Error:", e.code)
    try:
        content = e.fp.read().decode('utf-8')
        print("Response body:")
        print(content)
    except Exception as ie:
        print("Error reading body:", ie)
except Exception as e:
    print("Other error:", e)
