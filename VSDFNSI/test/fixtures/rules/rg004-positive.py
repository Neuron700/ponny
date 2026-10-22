import requests

response = requests.get("https://synthetic.invalid", verify=False)
ssl_verify = False
