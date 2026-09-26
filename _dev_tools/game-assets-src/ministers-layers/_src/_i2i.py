import base64
import json
import urllib.request

KEY = "sk-8Rzd2yCbFzOi1vxojseH8C5D8w3u4aMdNWsPNzxk0G7339Cz"
EPS = ["https://apihub.agnes-ai.com/v1/images/generations",
       "https://apihub.agnes-ai.cn/v1/images/generations"]


def gen_i2i(prompt, base_path, save_path):
    b64 = base64.b64encode(open(base_path, "rb").read()).decode()
    body = json.dumps({
        "model": "agnes-image-2.1-flash",
        "prompt": prompt,
        "size": "1K",
        "ratio": "3:4",
        "extra_body": {"image": ["data:image/png;base64," + b64],
                       "response_format": "url"},
    }).encode()
    for ep in EPS:
        try:
            req = urllib.request.Request(ep, data=body, headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + KEY})
            with urllib.request.urlopen(req, timeout=300) as r:
                d = json.loads(r.read())
            urllib.request.urlretrieve(d["data"][0]["url"], save_path)
            print("OK", save_path, flush=True)
            return True
        except Exception as e:
            print("err:", repr(e)[:90], flush=True)
    return False
