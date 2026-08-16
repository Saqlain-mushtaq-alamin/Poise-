import urllib.request
import urllib.error
import json

req = urllib.request.Request(
    'http://127.0.0.1:8000/ielts/sessions',
    method='POST',
    headers={'Content-Type': 'application/json'},
    data=json.dumps({'target_band': 6.5}).encode('utf-8')
)
try:
    print(urllib.request.urlopen(req).read().decode())
except urllib.error.HTTPError as e:
    print(e.read().decode())
