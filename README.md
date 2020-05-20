# Prometheus Exporter Module for ACOS Devices

The ACOS Prometheus Exporter module collects ACOS device statistics (stats) and displays the resulting metrics. It internally invokes the target ACOS device axAPIs to obtain those stats and then exposes the respective metrics via HTTP(s), which can be pulled by the Prometheus server.   

The following sections describe how to analyze the ACOS stats using Prometheus and communicate with the Prometheus server.  

## Analyzing ACOS Stats Using Prometheus
To analyze the ACOS stats, configure a visualization client, like Grafana, to perform the following functions:
-  Query the stats from the Prometheus server.
-  Plot the stats.
-  Set thresholds.
-  Configure alerts.
-  Create heat maps.
-  Generate tables and other elements as required.

The Prometheus server works on a pull-based model and queries the Exporter periodically based on the intervals specified. It runs by default on port 9090. 

## Communicating with the Prometheus Server
To communicate with the Prometheus server:
-  Create and view dashboards using Visualization and Analytics tools like Grafana.
-  Configure the Exporter to communicate with multiple ACOS devices in a multi-cloud environment.  
   (More details on configuration to follow.)  <Better to be more specific or provide a reference or a link to information.>

The Exporter supports the querying of any stats from the APIs as configured in the YAML file of the Prometheus server.  The Exporter creates gauge metrics for each stats field and exposes them on port 9734.  (More details on the Prometheus server's YAML file to follow.) <Better to be more specific or provide a reference or a link to information.>
	
## Prometheus Architecture in the ACOS Environment
The following illustration presents the architecture and setup of Prometheus in the ACOS environment:
![picture](img/prometheus.png)
<Please capitalize the call outs in the illustration.  They are not consistently capitalized.>
	
## Components of the Solution
The components of the solution are the Exporter, the Prometheus Server, and the Visualization Tool.

#### 1) The Exporter
The Exporter is a python script/container that performs the following functions:
- Invokes the ACOS axAPIs to fetch the data from the stats fields.
- Exposes the queried stats in the form of Prometheus metrics.
- Follows the principle of URL intercepting where:
    - The URLs are specified in the Prometheus server’s configuration file. 
    - The specified axAPI is invoked as per the URL name.
- Creates gauge metrics for each stats field and exposes them on port 9734.

#### Sample config.yml Snippet:
```
hosts:
  <host_ip goes here>:
    username: <uname goes here>
    password: <pwd goes here>
log:
  log_file: logs.log
  log_level: INFO
```
#### Field Descriptions:
```
 host_ip	:	The ACOS instance IP that is to be monitored.
 log_level	:	The Set Log Level value to debug for debugging purposes. (The default log_level ID is set to INFO.)
 ```

#### 2) The Prometheus Server
The Prometheus server monitors and continuously polls the stats fields that are exposed by the Exporter.
It refers to the prometheus.yml configuration file for polling. It can also send out the alerts to Information Technology Security Management (ITSM) systems, such as, PagerDuty, ServiceNow, Slack, and similar software.  The Prometheus server runs on port 9090 by default. 
   
#### Sample prometheus.yml Config Snippet: 

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

#### Field Descriptions
```
scrape_interval	:	The time intervals between the queries that are sent to the stats fields.
target		: 	The hostname and the port that the Exporter is running on.
api_endpoint	: 	The URI endpoint that the Exporter intercepts to invoke the appropriate axAPI. 
			(A comma seperated list of APIs can be provided here for a single host.)
api_name	: 	The API name or the unique identifier used to indentify the API endpoint. 
			(The comma seperated list of API names must be in sync with the list of API endpoints.)
partition	: 	The name of the partition. This is an optional parameter. 
			(If not specified, the shared partition is used.) 
```
In this scenario, once the Prometheus server is started, it invokes a custom Exporter after each 15-second interval, as specified in the Scraping Interval field.

The api_endpoint and the api_name (unique identifier for a job) are passed to the Exporter as parameters.
The Exporter invokes the axAPI for the port and fetches the stats fields.  It then creates gauge metrics for each stats field and exposes the metrics to the Prometheus server.
 
#### 3) The Visualization Tool
The Prometheus UI has an in-built visualization functionality that displays the metrics exposed by the Exporter.  
To get all the metrics for an endpoint, perform one of the following steps:
- Select the targets.
- Search for a specific metric by using the Prometheus's Query Language expressions.

The same metrics may be visualized in a graphical form by using visualization tools, such as, Grafana.

To display metrics in a graphical form in Grafana:
- Add a data source called 'Prometheus'

To query for metrics in Prometheus or Grafana:
- Enter the stats field name in the Query box found in the Prometheus Query page or in Grafana 
  (for example, curr_proxy, total_fwd_bytes, etc.). Refer to the following file for more information:
  [Prometheus Querying](https://prometheus.io/docs/prometheus/latest/querying/basics/). 

The Prometheus User Interface (UI) runs on port 9090 by default.

## Installation and Setup Instructions

The Exporter can be run as a standalone python script, or be built into a container. 
<Please clarify the above concept.  Are we speaking of two choices here?  Please correct the edits if wrong.>

#### Exporter Running as a Standalone Script 
To run the Exporter as a standalone script, enter the following command:
```
pip install -r requirements.txt
python acos_exporter.py
```

#### Exporter Running as a Container
To use the Exporter as a container, directly use an image from the Docker Hub:

Run the Exporter using the following command:
 ```
docker run -d -p 9734:9734 -v <local_path_to_config.yml>:/app/config.yml a10networks/acos-prometheus-exporter:latest
```
Replace the placeholder <local_path_to_config.yml> with the local path to the Config YML file (config.yml).
	
To inspect the logs, use the following command: 
 ```
docker ps
```

Replace the placeholder <container-ID> with the ID of the container from the output of the above command.
 ```
docker exec -it <container-ID> bash
tail -f logs.log
```
#### Running on Kubernetes using the Helm Package
The Exporter can be run in Kubernetes using the Helm package published publically by running the following commands:
1.  Create the config.yaml file as specified in section 1 above.

2.  Add the Helm Repo to the local setup:
	```
	helm repo add a10-prometheus-exporter https://a10networks.github.io/acos-prometheus-exporter-helm-chart/
	```
3.  Install the package to the local setup: 
	```
	helm install --name a10-prometheus-exporter a10-prometheus-exporter/acos-prometheus-exporter --set-file 
	config=config.yaml
	```
4.  Check the status using the following command:
	```
	kubectl get all
	``` 
#### Example
Below is an example of a Prometheus YML Config Snippet file (prometheus.yml) for Automatic Service Discovery in Kubernetes:

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
