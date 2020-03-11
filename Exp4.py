import json
import sys
import prometheus_client
import requests
import urllib3
from flask import Response, Flask, request
from prometheus_client import Gauge
import logging

UNDERSCORE = "_"
SLASH = "/"
HYPHEN = "-"
PLUS = "+"

endpoint_labels = dict()
dictmetrics = dict()

app = Flask(__name__)

_INF = float("inf")


def set_logger(log_file, log_level):
    try:
        logging.basicConfig(
            filename=log_file,
            format='%(asctime)s %(levelname)-8s %(message)s',
            datefmt='%FT%T%z',
            level={
                'DEBUG': logging.DEBUG,
                'INFO': logging.INFO,
                'WARN': logging.WARN,
                'ERROR': logging.ERROR,
                'CRITICAL': logging.CRITICAL,
            }[log_level.upper()])
    except Exception as e:
        print('Error while setting logger config::%s', e)

    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logger = logging.getLogger('a10_prometheus_exporter_logger')
    return logger


def getauth(host):
    with open('config.json') as f:
        data = json.load(f)["hosts"]
    if host not in data:
        logger.error("Host credentials not found in creds config")
        return ''
    else:
        uname = data[host]['username']
        pwd = data[host]['password']

        payload = {'Credentials': {'username': uname, 'password': pwd}}
        auth = json.loads(
            requests.post("https://{host}/axapi/v3/auth".format(host=host), json=payload, verify=False).content.decode(
                'UTF-8'))
        return 'A10 ' + auth['authresponse']['signature']


@app.route("/")
def default():
    return "Please provide /metrics/service-name!"


@app.route("/metrics")
def generic_exporter():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    host_ip = request.args["host_ip"]
    api_endpoint = request.args["api_endpoint"]
    api_name = request.args["api_name"]
    token = getauth(host_ip)
    logger.info("Host - " + host_ip + "\n" +
                "Api - " + api_name + "\t" + "endpoint - " + api_endpoint + "\n")
    if token == '':
        logger.error("Username, password does not match, token can not be empty, exiting")
        sys.exit()

    endpoint = "http://{host_ip}/axapi/v3".format(host_ip=host_ip)
    headers = {'content-type': 'application/json', 'Authorization': token}
    logger.info("Uri - "+endpoint + api_endpoint + "/stats")
    response = json.loads(
        requests.get(endpoint + api_endpoint + "/stats", headers=headers, verify=False).content.decode('UTF-8'))
    try:
        key = list(response.keys())[0]
        event = response.get(key)
        stats = event.get("stats", {})
    except Exception as e:
        logger.exception(e)
        return api_endpoint + " have something missing."

    logger.info("name = " + api_name)

    for key in stats:
        org_key = key
        if HYPHEN in key:
            key = key.replace(HYPHEN, UNDERSCORE)
        if api_name + UNDERSCORE + key not in dictmetrics:
            dictmetrics[api_name + UNDERSCORE + key] = Gauge(api_name + UNDERSCORE + key,
                                                             "api-" + api_name + "key-" + key,
                                                             labelnames=(["data"]), )
            # Gauge will be created with unique identifier as combination of ("api_name_key_name")
        data = {api_name: key}
        dictmetrics[api_name + UNDERSCORE + key].labels(data).set(stats[org_key])
        endpoint_labels[api_name] = dictmetrics

    res = []
    for name in endpoint_labels[api_name]:
        res.append(prometheus_client.generate_latest(endpoint_labels[api_name][name]))
    return Response(res, mimetype="text/plain")


def main():

    app.run(debug=True, port=7070)


if __name__ == '__main__':
    with open('config.json') as f:
        data = json.load(f)
        data = data["log"]
    try:
        logger = set_logger(data["log_file"], data["log_level"])
    except Exception as e:
        print("Config file is not correct")
        print(e)
        sys.exit()

    logger.info("Starting exporter")
    main()
