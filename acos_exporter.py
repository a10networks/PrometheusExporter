import json
import sys
from threading import Lock

import prometheus_client
import requests
import urllib3
from flask import Response, Flask, request
from prometheus_client import Gauge
import logging
from logging.handlers import RotatingFileHandler

UNDERSCORE = "_"
SLASH = "/"
HYPHEN = "-"
PLUS = "+"

LOG_FILE_SIZE = 5*1024*1024
API_TIMEOUT = 5

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
            token = ""
            if host_ip not in tokens or to_call:
                token = getauth(host_ip)
            if not token:
                logger.error("Token not received.")
                return ""
            tokens[host_ip] = token
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
        print(log_level.upper()+" is invalid log level, setting 'INFO' as default.")
        log_level = "INFO"
    try:
        log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s')
        log_handler = RotatingFileHandler(log_file, maxBytes=LOG_FILE_SIZE, backupCount=2, encoding=None,
                                          delay=True)
        log_handler.setFormatter(log_formatter)
        log_handler.setLevel(log_levels[log_level.upper()]) # log levels are in order, DEBUG includes logging at each level
    except Exception as e:
        raise Exception('Error while setting logger config.')

    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logger = logging.getLogger('a10_prometheus_exporter_logger')
    logger.setLevel(log_levels[log_level.upper()])
    logger.addHandler(log_handler)
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
        try:
            auth = json.loads(requests.post("https://{host}/axapi/v3/auth".format(host=host), json=payload,
                                            verify=False, timeout=API_TIMEOUT).content.decode('UTF-8'))
        except requests.exceptions.Timeout:
            logger.error("Connection to {host} timed out. (connect timeout={timeout} secs)".format(host=host,
                                                                                                   timeout=API_TIMEOUT))
            return ''

        if 'authresponse' not in auth:
            logger.error("Host credentials are not correct")
            return ''
        return 'A10 ' + auth['authresponse']['signature']


def get_stats(api_endpoints, endpoint, host_ip, headers):
    try:
        body = {
            "batch-get-list": list()
        }
        for api_endpoint in api_endpoints:
            body["batch-get-list"].append({"uri": "/axapi/v3" + api_endpoint + "/stats"})
        batch_endpoint = "/batch-get"
        logger.info("Uri - " + endpoint + batch_endpoint)
        response = json.loads(
            requests.post(endpoint+batch_endpoint, data=json.dumps(body), headers=headers, verify=False).content.decode('UTF-8'))
        logger.debug("AXAPI batch response - " + str(response))

        if 'response' in response and 'err' in response['response']:
            msg = response['response']['err']['msg']
            if str(msg).lower().__contains__("uri not found"):
                logger.error("Request for api failed - batch-get"  + ", response - " + msg)

            elif str(msg).lower().__contains__("unauthorized"):
                token = get_valid_token(host_ip, True)
                if token:
                    logger.info("Re-executing an api -", endpoint+"/batch-get", " with the new token")
                    headers = {'content-type': 'application/json', 'Authorization': token}
                    response = json.loads(
                        requests.post(endpoint+"/batch-get", data=json.dumps(body), headers=headers, verify=False).content.decode('UTF-8'))
            else:
                logger.error("Unknown error message - ", msg)
    except Exception as e:
        logger.error("Exception caught - ", e)
        response = ""
    return response


def get_partition(endpoint, headers):
    partition_endpoint = "/active-partition"
    response = json.loads(requests.get(endpoint + partition_endpoint, headers=headers, verify=False).content.decode('UTF-8'))
    return "partition - "+str(response)


def change_partition(partition, endpoint, headers):
    partition_endpoint = "/active-partition/"+ str(partition)
    logger.info("Uri - " + endpoint + partition_endpoint)
    requests.post(endpoint + partition_endpoint, headers=headers, verify=False)
    logger.info("Partition changed to " + partition)

@app.route("/")
def default():
    return "Please provide /metrics?query-params!"


@app.route("/metrics")
def generic_exporter():
    logger.debug("---------------------------------------------------------------------------------------------------")
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    host_ip = request.args.get("host_ip","")
    api_endpoints = request.args.getlist("api_endpoint")
    api_names = request.args.getlist("api_name")
    partition = request.args.get("partition", "shared")
    res = []

    # Basic validation for query params.
    if not api_endpoints:
        logger.error("api_endpoint is required.")
        return Response(res, mimetype="text/plain")
    if not host_ip:
        logger.error("host_ip is required. Exiting API endpoint - ", api_endpoints)
        return Response(res, mimetype="text/plain")
    if not api_names:
        logger.error("api_name is required.")
        return Response(res, mimetype="text/plain")
    if len(api_names) != len(api_endpoints):
        logger.error("No of API names provided does not match with no of API endpoints.")
        return Response(res, mimetype="text/plain")

    logger.info("Host = " + host_ip + "\t" +
                "API = " + str(api_names))
    logger.info("Endpoint = " + str(api_endpoints))

    # Building request URL and header.
    token = get_valid_token(host_ip)
    endpoint = "https://{host_ip}/axapi/v3".format(host_ip=host_ip)
    headers = {'content-type': 'application/json', 'Authorization': token}

    # Changing Partition if provided.
    logger.debug(get_partition(endpoint, headers))
    if "shared" not in partition:
        change_partition(partition, endpoint, headers)
        response = get_stats(api_endpoints, endpoint, host_ip, headers)
    else:
        response = get_stats(api_endpoints, endpoint, host_ip, headers)

    api_counter = 0
    batch_list = response.get("batch-get-list", [])
    for response in batch_list:
        api_endpoint = api_endpoints[api_counter]
        api_name = api_names[api_counter]
        logger.info("name = " + api_name)
        api_response = response.get("resp", {})
        logger.debug("API \"{}\" Response - {}".format(api_name, str(api_response)))
        api_counter += 1
        try:
            key = list(api_response.keys())[0]
            event = api_response.get(key, {})
            if type(event) == dict and "stats" in event:
                stats = event.get("stats", {})
            else:
                raise Exception("Stats not found in API response.")
        except Exception as ex:
            logger.exception(ex.args[0])
            return api_endpoint + " has something missing."

        api = str(api_name)
        if api.startswith("_"):
            api = api[1:]

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

        for name in global_api_collection[api]:
            res.append(prometheus_client.generate_latest(global_api_collection[api][name]))
    logger.debug("Final Response - " + str(res))
    return Response(res, mimetype="text/plain")


def main():
    app.run(debug=True, port=7070, host='0.0.0.0')


if __name__ == '__main__':
    try:
        with open('config.json') as f:
            log_data = json.load(f).get("log", {})
            logger = set_logger(log_data.get("log_file","exporter.log"), log_data.get("log_level","INFO"))
            logger.info("Starting exporter")
            main()
    except Exception as e:
        print(e)
        sys.exit()
