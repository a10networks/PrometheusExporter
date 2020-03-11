import os
import sys
import json
import requests
import urllib3
from random import randint
import Exp4


UNDERSCORE = "_"
SLASH = "/"
HYPHEN = "-"
PLUS = "+"

job = '''
  - job_name: 'name_replace'
    static_configs:
    - targets: ['localhost:7070']
    metrics_path: '/metrics'    
    params:
        host_ip: ["ip_replace"]
        api_endpoint: ["api_endpoint_replace"]
        api_name: ["api_names_replace"]
'''

yml = '''
global:
  scrape_interval:     15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
  - static_configs:
    - targets:
      # - alertmanager:9093

# Load rules once and periodically evaluate them according to the global 'evaluation_interval'.
rule_files:
  # - "first_rules.yml"
  # - "second_rules.yml"

# A scrape configuration containing exactly one endpoint to scrape:
# Here it's Prometheus itself.
scrape_configs:
  # The job name is added as a label `job=<job_name>` to any timeseries scraped from this config.
  '''


def getauth(ip):
    with open('config.json') as f:
        data = json.load(f)
        data = data["hosts"]
    if ip not in data:
        print("Host credentials not found in creds config")
        return ''
    else:
        uname = data[ip]['username']
        pwd = data[ip]['password']

        payload = {'Credentials': {'username': uname, 'password': pwd}}
        auth = json.loads(
        requests.post("https://{host}/axapi/v3/auth".format(host=ip), json=payload, verify=False).content.decode(
            'UTF-8'))
        return 'A10 ' + auth['authresponse']['signature']


def execute(ip):
    list = postdatatoapi(ip)
    createyml(ip, list)
    runexporter()


def runexporter():
    with open('config.json') as f:
        data = json.load(f)
        data = data["log"]
    try:
        Exp4.logger = Exp4.set_logger(data["log_file"], data["log_level"])
    except Exception as e:
        print("Config file is not correct")
        print(e)
        sys.exit()

    Exp4.logger.info("Starting exporter")
    Exp4.main()


def postdatatoapi(ip):
    list = getapilist(ip)
    count = len(list)
    for api in list:
        json = getformat(ip, api)

        for key in json:
            for value in json[key]['stats']:
                json[key]['stats'][value] = randint(1, 10)
        print(poststats(ip, api, json))
    return list


def createyml(ip, list):
    ct = 1
    data = yml
    for item in list:
        name = "prometheus_"
        api = item.split("/axapi/v3")[1].split("/stats")[0]
        replaced = job.replace("name_replace", name + "job_" + str(ct)).replace("ip_replace", ip).replace(
            "api_endpoint_replace", api)
        if HYPHEN in api:
            api = api.replace(HYPHEN, UNDERSCORE)
        if PLUS in api:
            api = api.replace(PLUS, UNDERSCORE)
        if SLASH in api:
            api = api.replace(SLASH, UNDERSCORE)
        replaced = replaced.replace("api_names_replace", api)
        ct = ct + 1
        data = data + replaced
    file1 = open('/home/sujeet/Prometheus/prometheus-2.15.1.linux-amd64/prometheus.yml', 'w')
    file1.write(data)
    file1.close()


def poststats(ip, api, json2):
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    token = getauth(ip)
    if token == '':
        print("Username, password does not match, token can not be empty, exiting")
        sys.exit()
    endpoint = "https://" + ip + ":443" + api
    headers = {'content-type': 'application/json', 'Authorization': token}

    return json.loads(
        requests.post(endpoint, json=json2, verify=False, headers=headers).content.decode('UTF-8'))


def getformat(ip, api):
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    token = getauth(ip)
    if token == '':
        print("Username, password does not match, token can not be empty, exiting")
        sys.exit()
    endpoint = "http://" + ip + api
    headers = {'content-type': 'application/json', 'Authorization': token}
    return json.loads(
        requests.get(endpoint, headers=headers, verify=False).content.decode('UTF-8'))


def getapilist(ip):
    file1 = open('apis.txt', 'r')
    Lines = file1.readlines()
    list = []
    for line in Lines:
        line = line.strip()
        list.append(line)
    return list


if __name__ == "__main__":
    execute(sys.argv[1])
