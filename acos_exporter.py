import json
import sys
from threading import Lock

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

global_api_collection = dict()
global_stats = dict()

app = Flask(__name__)

_INF = float("inf")

lock1 = Lock()
tokens = dict()


def get_valid_token(host_ip, to_call=False):
    global tokens
    lock1.acquire()
    try:
        if host_ip in tokens and not to_call:
            return tokens[host_ip]
        else:
            if host_ip not in tokens or to_call:
                tokens[host_ip] = getauth(host_ip)
        return tokens[host_ip]
    finally:
        lock1.release()


def set_logger(log_file, log_level):
    log_levels = {
                'DEBUG': logging.DEBUG,
                'INFO': logging.INFO,
                'WARN': logging.WARN,
                'ERROR': logging.ERROR,
                'CRITICAL': logging.CRITICAL,
            }
    if log_level.upper() not in log_levels:
        print(log_level.upper()+" is invalid log level, setting 'DEBUG' as default.")
        log_level = "DEBUG"
    try:
        logging.basicConfig(
            filename=log_file,
            format='%(asctime)s %(levelname)-8s %(message)s',
            datefmt='%FT%T%z',
            level=log_levels[log_level.upper()])  # log levels are in order, DEBUG includes logging at each level
    except Exception as e:
        raise Exception('Error while setting logger config.')

    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logger = logging.getLogger('a10_prometheus_exporter_logger')
    return logger


def getauth(host):
    with open('config.json') as f:
        hosts_data = json.load(f)["hosts"]
    if host not in hosts_data:
        logger.error("Host credentials not found in creds config")
        return ''
    else:
        uname = hosts_data[host].get('username','')
        pwd = hosts_data[host].get('password','')
        if not uname:
            logger.error("username not provided.")
        if not pwd:
            logger.error("password not provided.")

        payload = {'Credentials': {'username': uname, 'password': pwd}}
        auth = json.loads(
            requests.post("https://{host}/axapi/v3/auth".format(host=host), json=payload, verify=False).content.decode(
                'UTF-8'))
        if 'authresponse' not in auth:
            logger.error("Host credentials are not correct")
            return ''
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
    token = get_valid_token(host_ip)

    logger.info("Host = " + host_ip + "\t" +
                "API = " + api_name + "\t\t" +
                "Endpoint = " + api_endpoint)

    endpoint = "http://{host_ip}/axapi/v3".format(host_ip=host_ip)
    headers = {'content-type': 'application/json', 'Authorization': token}
    logger.info("Uri - " + endpoint + api_endpoint + "/stats")

    response = json.loads(
        requests.get(endpoint + api_endpoint + "/stats", headers=headers, verify=False).content.decode('UTF-8'))

    if 'response' in response and 'err' in response['response']:
        msg = response['response']['err']['msg']
        if str(msg).lower().__contains__("uri not found"):
            logger.error("Request for api failed -" + api_endpoint + ", response - " + msg)

        elif str(msg).lower().__contains__("unauthorized"):
            token = get_valid_token(host_ip, True)
            headers = {'content-type': 'application/json', 'Authorization': token}
            logger.info("Re-executing an api -" + endpoint + api_endpoint + "with the new token")
            response = json.loads(
                requests.get(endpoint + api_endpoint + "/stats", headers=headers, verify=False).content.decode('UTF-8'))

    try:
        key = list(response.keys())[0]
        event = response.get(key)
        stats = event.get("stats", {})
    except Exception as ex:
        logger.exception(ex)
        return api_endpoint + " have something missing."

    api = str(api_name)
    if api.startswith("_"):
        api = api[1:]

    logger.info("name = " + api_name)

    current_api_stats = dict()
    if api in global_api_collection:
        current_api_stats = global_api_collection[api]

     # This section maintains local dictionary  of stats fields against Gauge objects.
     # Code handles the duplication of key_name in time series database
     # by referring the global dictionary of key_name and Gauge objects.

    for key in stats:
        org_key = key
        if HYPHEN in key:
            key = key.replace(HYPHEN, UNDERSCORE)
        if key not in global_stats:
            current_api_stats[key] = Gauge(key, "api-" + api + "key-" + key, labelnames=(["data"]), )
            current_api_stats[key].labels(api).set(stats[org_key])
            global_stats[key] = current_api_stats[key]
        elif key in global_stats:
            global_stats[key].labels(api).set(stats[org_key])

    global_api_collection[api] = current_api_stats
    res = []
    for name in global_api_collection[api]:
        res.append(prometheus_client.generate_latest(global_api_collection[api][name]))
    return Response(res, mimetype="text/plain")


def main():
    app.run(debug=True, port=7070, host='0.0.0.0')


if __name__ == '__main__':
    try:
        with open('config.json') as f:
            log_data = json.load(f).get("log", {})
            logger = set_logger(log_data.get("log_file","logs.log"), log_data.get("log_level","DEBUG"))
            logger.info("Starting exporter")
            main()
    except Exception as e:
        print(e)
        sys.exit()
