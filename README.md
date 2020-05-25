## ACOS Prometheus Exporter
The ACOS Prometheus Exporter module collects the ACOS device statistics (stats) and displays the results as metrics.

To analyze the ACOS stats, configure any visualization client, such as, Grafana, to query the stats from the Prometheus server, plot them, set thresholds, configure alerts, create heat maps, generate table, and perform similar functions, as needed.

The Prometheus server works on a pull-based model and periodically queries the Exporter based on the intervals specified.  It runs by default on port 9090.

Users and systems can:
- Create and view dashboards by communicating with the Prometheus server using a Visualization and Analytics tool, like Grafana.
- Configure the Exporter to communicate with multiple ACOS devices in a multi-cloud environment. 
- Query any API stats configured in the Prometheus server’s YAML file. 

  The Exporter creates gauge metrics for each stats field and exposes them on port 9734.

More information on the configuration and the server YAML file will follow soon.

## Architecture of the Prometheus setup

![picture](img/prometheus.png)

## Components of the solution

#### 1) Exporter
- Custom exporter is a python script/container which:
- Invokes ACOS axAPIs to fetch the stats fields.
- Exposes the queried stats in the form of Prometheus metrics.
- It follows the principle of URL intercepting. The URLs need to be specified in the Prometheus server’s configuration file. The specified axAPI is invoked as per the url name.
- Exporter creates a Gauge metrics for each stats field and exposes the same on the port 9734

Sample config.yml snippet:
```
---
hosts:
  <host_ip goes here>:
    username: <uname goes here>
    password: <pwd goes here>
log:
  log_file: logs.log
  log_level: INFO
```
 - host_ip: ACOS instance IP which is to be monitored
 - log_level: Set log_level to DEBUG for debugging purpose. Default log_level is INFO.
 

#### 2) Prometheus Server
Prometheus server is responsible for monitoring and continuous polling the stats filed that are exposed by the exporter.
It refers to the prometheus.yml configuration file for polling.
Prometheus server runs on port 9090 by default.
It can also send out the alerts to ITSM systems such as PagerDuty, ServiceNow, Slack etc.
   
Sample prometheus.yml config snippet: 

```   
global:
  scrape_interval:     15s
  evaluation_interval: 15s
 
  - job_name: 'acos-scraper-job'
    static_configs:
    - targets: ['localhost:9734']
    metrics_path: '/metrics'    
    params:
        host_ip: ["10.43.12.122"]
        api_endpoint: ["/slb/dns", "/slb/virtual-server/10.10.10.2/port/80+tcp", "/slb/fix"]
        api_name: ["_slb_dns", "_slb_virtual_server_10.10.10.2_port_80_tcp", "_slb_fix"]
	partition: ["P1"]
	
```       
   
- scrape_interval: time interval for querying stats fields
- target: hostname and port that exporter is running on
- api_endpoint: URI endpoint that exporter will intercept and invoke the appropriate axAPI. A comma seperated list of APIs can be provided here for a single host.
- api_name: API name any name used to indentify the API endpoint. Comma seperated list of api_name should be in synch with api_endpoint list
- partition: Name of the partition. This is optional parameter. If not specified, shared partition will be used. 

In this scenario, once Prometheus server is started, it invokes a custom exporter after each 15sec, as specified in the scraping interval.
api_endpoint and api_name (unique identifier for a job) are passed to the exporter as parameters.
Exporter invokes axAPI for port and fetches the stats fields, creates gauge metrics for each stats field and exposes the metrics to Prometheus server.

Sample prometheus.yml config snippet for automatic service descovery in Kubernetes:
```
global:
  scrape_interval:     15s
  evaluation_interval: 15s
  - job_name: 'acos-scraper-job'
    kubernetes_sd_configs:
    - role: endpoints
      namespaces:
        names:
        - default
    relabel_configs:
    - source_labels: [__meta_kubernetes_service_name]
      action: keep
      regex: prometheus-exporter-svc
    - source_labels: [__meta_kubernetes_pod_host_ip]
      target_label: __address__
      replacement: ${1}:30101
    metrics_path: '/metrics'
    params:
      host_ip: ["10.43.12.122"]
      api_endpoint: ["/slb/dns"]
      api_name: ["_slb_dns"]
```

#### 3) Visualization tool:
- Prometheus UI runs on port 9090 by default.
 - It has an in-built visualization functionality that displays the metrics information exposed by the exporter.
- User can select the targets and get the all metrics for an end-point or can search for a specific metric by querying using Prometheus query language expression.
- Same metrics can be visualized ina graphical form by using visualization tools like Grafana.
- A data source needs to be added as Prometheus in order to display metrics in the graphical form in Grafana.
- A metrics can be queried by entering the stats field name in the query box (either in prometheus query page or graphana). eg: "curr_proxy", "total_fwd_bytes" etc.
- Refer [Prometheus Querying](https://prometheus.io/docs/prometheus/latest/querying/basics/) for more information.


## Installation/ setup instructions:

The exporter can be run as a standalone python script, built into a container. 

#### Running as a standalone script 
```
pip install -r requirements.txt
python acos_exporter.py
```

#### Running as a container

In order to use the exporter as a container, an image from docker hub can be used directly.

Run the exporter using the below command. Replace the placeholder <local_path_to_config.yml> with local path to config.yml
 
 ```
docker run -d -p 9734:9734 -v <local_path_to_config.yml>:/app/config.yml a10networks/acos-prometheus-exporter:latest
```

To inspect the logs please follow below commands.
 
 ```
docker ps
```

Replace the placeholder <container ID> with the container id from the above command output.
 
 ```
docker exec -it <container-ID> bash
tail -f logs.log
```
#### Running on Kubernetes/OpenShift using Helm package
Exporter can be run in Kubernetes/OpenShift using Helm package published on Artifact HUB by running following commands.

Create config.yaml as specified below.

```
hosts:
  <host_ip goes here>:
    username: <uname goes here>
    password: <pwd goes here>
log:
  log_file: logs.log
  log_level: INFO
```
- host_ip: ACOS instance IP which is to be monitored
- log_level: Set log_level to DEBUG for debugging purpose. Default log_level is INFO.
 

To use the Helm package, run the following commands.

- Add Helm Repo to the local setup:
    ```
    helm repo add a10-prometheus-exporter https://a10networks.github.io/prometheus-exporter-helm/
    ```
- Install the package on the local setup:
    ```
    helm install --name a10-prometheus-exporter a10-prometheus-exporter/acos-prometheus-exporter --set-file config=config.yaml
    ```
To check the status, use one of the following commands:

- For Kubernetes, use the  **kubectl** command:
    ```
    kubectl get all
    ``` 
- For OpenShift, use the  **oc** command: 
    ```
    oc get all
    ``` 
