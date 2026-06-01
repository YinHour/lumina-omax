import json
import urllib.request

req = urllib.request.Request("http://localhost:5055/api/v1/sources")
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        for s in data["results"]:
            print(f"{s['title']}: kg_extracted={s.get('kg_extracted')}")
except Exception as e:
    print("Error:", e)
