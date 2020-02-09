#!/usr/local/bin/python3

# Author:		Adrian Bronder
# Date:			October 15th, 2018
# Description:  Cluster setup + configuration based on JSON input

from threading import Thread
import sys
import time
import json
sys.path.append("./NetApp")
from NaServer import *


def print_usage():
	print("\nUsage: " + __file__ + " <config_file>\n")
	print("<config_file> -- JSON file with setup parameters\n")

	
if(len(sys.argv) != 2):
	print_usage()
	sys.exit(1)

with open(sys.argv[1]) as json_file:
        json_data = json.load(json_file)
	
def cluster_setup(cluster):
	print("> " + cluster["cluster-name"] + ": Creating Cluster ")
	
	for node in cluster["cluster-nodes"]:
	
		print("---> " + node["node-name"] + ": Working on node ")
		session = NaServer(node["ip"], 1, 140)
		session.set_server_type("Filer")
		session.set_admin_user(node["user"], node["password"])
		session.set_transport_type("HTTPS")
		
		# STEP: Create cluster
		if("-01" in node["node-name"]):
			print("---> " + node["node-name"] + ": Creating cluster...")
			zapi_post = NaElement("cluster-create")
			zapi_post.child_add_string("cluster-name", cluster["cluster-name"])
			if len(cluster["cluster-nodes"]) > 1:
				zapi_post.child_add_string("single-node-cluster", "false")
			else:
				zapi_post.child_add_string("single-node-cluster", "true")

			zapi_post_return = session.invoke_elem(zapi_post)
			if(zapi_post_return.results_status() == "failed"):
				print("--- " + node["node-name"] + ": " + zapi_post.sprintf().strip())
				print("--- " + node["node-name"] + ": " + zapi_post_return.sprintf().strip())
				sys.exit(1)
			else:
				zapi_get = NaElement("cluster-create-join-progress-get")
				is_complete = ""
				create_iterator = 1
				while is_complete != "true" and \
						create_iterator < 13:
					time.sleep(10)
					zapi_get_return = session.invoke_elem(zapi_get)
					is_complete = zapi_get_return.child_get("attributes").child_get("cluster-create-join-progress-info").child_get_string("is-complete")
					action_status = zapi_get_return.child_get("attributes").child_get("cluster-create-join-progress-info").child_get_string("status")
					create_iterator = create_iterator + 1
				if(is_complete == "true") and (action_status == "success"):
					print("---> " + node["node-name"] + ": SUCCESS")
				else:
					print("---> " + node["node-name"] + ": " + zapi_get.sprintf().strip())
					print("---> " + node["node-name"] + ": " + zapi_get_return.sprintf().strip())
					sys.exit(1)
		
		# STEP: Create cluster management LIF
		if("-01" in node["node-name"]):
			print("--- " + node["node-name"] + ": Creating cluster management LIF...")
			found = False
			for lif in cluster["net-interfaces"]:
				if lif["role"] == "cluster-mgmt":
					found = True
					zapi_post = NaElement("net-interface-create")
					zapi_post.child_add_string("vserver", cluster["cluster-name"])
					for k, v in lif.items():
						zapi_post.child_add_string(k, v)
					break
			if found:
				zapi_post_return = session.invoke_elem(zapi_post)
				if (zapi_post_return.results_status() == "failed"):
					print("---> " + node["node-name"] + ": " + zapi_post.sprintf().strip())
					print("---> " + node["node-name"] + ": " + zapi_post_return.sprintf().strip())
				else:
					print("---> " + node["node-name"] + ": SUCCESS")
		
		# STEP: Remove existing cluster LIFs
		print("---> " + node["node-name"] + ": Removing existing cluster LIFs...")
		zapi_get = NaElement("net-interface-get-iter")
		elementQuery = NaElement("query")
		elementInterfaces = NaElement("net-interface-info")
		elementInterfaces.child_add_string("role", "cluster")
		elementQuery.child_add(elementInterfaces)
		zapi_get.child_add(elementQuery)
		zapi_get_return = session.invoke_elem(zapi_get)
		if (zapi_get_return.results_status() == "failed"):
			print("---> " + node["node-name"] + ": " + zapi_get.sprintf().strip())
			print("---> " + node["node-name"] + ": " + zapi_get_return.sprintf())
		else:
			if(int(zapi_get_return.child_get_string("num-records")) > 0):
				for lif in zapi_get_return.child_get("attributes-list").children_get():
					print("   --- " + node["node-name"] + ": Deleting " + lif.child_get_string("interface-name") + "...")
					zapi_post = NaElement("net-interface-delete")
					zapi_post.child_add_string("vserver", "Cluster")
					zapi_post.child_add_string("interface-name", lif.child_get_string("interface-name"))
					zapi_post_return = session.invoke_elem(zapi_post)
					if (zapi_post_return.results_status() == "failed"):
						print("   ---> " + node["node-name"] + ": " + zapi_post.sprintf().strip())
						print("   ---> " + node["node-name"] + ": " + zapi_post_return.sprintf().strip())
					else:
						print("   ---> " + node["node-name"] + ": SUCCESS")
			else:
				print("---> " + node["node-name"] + ": Nothing to delete")
		
		# STEP: Modifying port configuration
		print("--- " + node["node-name"] + ": Modifying network ports...")
		zapi_get = NaElement("net-port-get-iter")
		zapi_get_return = session.invoke_elem(zapi_get)
		
		if(int(zapi_get_return.child_get_string("num-records")) > 1):
			for port in zapi_get_return.child_get("attributes-list").children_get():
				if port.child_get_string("port") != "e0M":
					# Remove from broadcast domain
					if(port.child_get_string("node") != "localhost"):
						print("   --- " + node["node-name"] + ": Removing " + port.child_get_string("port") + " from broadcast domain...")
						if not port.child_get_string("broadcast-domain") is None:
							zapi_post = NaElement("net-port-broadcast-domain-remove-ports")
							elementPorts = NaElement("ports")
							elementPorts.child_add_string("net-qualified-port-name", port.child_get_string("node") + ":" + port.child_get_string("port"))
							zapi_post.child_add_string("ipspace", port.child_get_string("ipspace"))
							zapi_post.child_add_string("broadcast-domain", port.child_get_string("broadcast-domain"))
							zapi_post.child_add(elementPorts)
							zapi_post_return = session.invoke_elem(zapi_post)
							if (zapi_post_return.results_status() == "failed"):
								print("   ---> " + node["node-name"] + ": " + zapi_post.sprintf().strip())
								print("   ---> " + node["node-name"] + ": " + zapi_post_return.sprintf().strip())
							else:
								print("   ---> " + node["node-name"] + ": SUCCESS")
						else:
							print("   ---> " + node["node-name"] + ": Skipping (port has no broadcast domain assigned")
					# Modify port
					print("   --- " + node["node-name"] + ": Modifying " + port.child_get_string("port") + "...")
					zapi_post = NaElement("net-port-modify")
					for params in node["net-ports"]:
						if params["port"] == port.child_get_string("port"):
							zapi_post.child_add_string("port", params["port"])
							zapi_post.child_add_string("node", port.child_get_string("node"))
							zapi_post.child_add_string("is-administrative-auto-negotiate", params["is-administrative-auto-negotiate"])
							zapi_post.child_add_string("administrative-duplex", params["administrative-duplex"])
							zapi_post.child_add_string("administrative-speed", params["administrative-speed"])
							zapi_post.child_add_string("administrative-flowcontrol", params["administrative-flowcontrol"])
							zapi_post.child_add_string("is-administrative-up", "true")
							if port.child_get_string("node") == "localhost":
								zapi_post.child_add_string("mtu", params["mtu"])
								zapi_post.child_add_string("role", params["role"])
								zapi_post.child_add_string("ipspace", params["ipspace"])
							zapi_post_return = session.invoke_elem(zapi_post)
							if (zapi_post_return.results_status() == "failed"):
								print("   ---> " + node["node-name"] + ": " + zapi_post.sprintf().strip())
								print("   ---> " + node["node-name"] + ": " + zapi_post_return.sprintf().strip())
							else:
								print("   ---> " + node["node-name"] + ": SUCCESS")
					# Add to broadcast domain
					if(port.child_get_string("node") != "localhost"):
						for params in node["net-ports"]:
							if params["port"] == port.child_get_string("port"):
								print("   --- Adding " + port.child_get_string("port") + " to broadcast domain 'Cluster'...")
								if(params["broadcast-domain"] == "Cluster"):
									zapi_post = NaElement("net-port-broadcast-domain-add-ports")
									elementPorts = NaElement("ports")
									elementPorts.child_add_string("net-qualified-port-name", node["node-name"] + ":" + params["port"])
									zapi_post.child_add_string("ipspace", params["ipspace"])
									zapi_post.child_add_string("broadcast-domain", params["broadcast-domain"])
									zapi_post.child_add(elementPorts)
									zapi_post_return = session.invoke_elem(zapi_post)
									if(zapi_post_return.results_status() == "failed"):
										print("   ---> " + node["node-name"] + ": " + zapi_post.sprintf().strip())
										print("   ---> " + node["node-name"] + ": " + zapi_post_return.sprintf().strip())
									else:
										print("   ---> " + node["node-name"] + ": SUCCESS")
								else:
									print("   ---> " + node["node-name"] + ": Skipping (port is not a cluster port)")
		time.sleep(15)
		
		# STEP: Create new cluster LIFs
		print("--- " + node["node-name"] + ": Creating cluster LIFs...")
		zapi_get = NaElement("net-port-get-iter")
		elementQuery = NaElement("query")
		elementPorts = NaElement("net-port-info")
		elementPorts.child_add_string("ipspace", "Cluster")
		elementQuery.child_add(elementPorts)
		zapi_get.child_add(elementQuery)
		zapi_get_return = session.invoke_elem(zapi_get)
		if(int(zapi_get_return.child_get_string("num-records")) > 0):
			lif_iterator = 1
			lif_count = int(zapi_get_return.child_get_string("num-records"))
			while lif_iterator < lif_count + 1:
				print("   --- " + node["node-name"] + ": Creating cluster LIF #" + str(lif_iterator) + "...")
				zapi_post = NaElement("net-interface-create")
				zapi_post.child_add_string("vserver", "Cluster")
				zapi_post.child_add_string("interface-name", "clus" + str(lif_iterator))
				zapi_post.child_add_string("role", "Cluster")
				zapi_post.child_add_string("home-node", zapi_get_return.child_get("attributes-list").children_get()[lif_iterator - 1].child_get_string("node"))
				zapi_post.child_add_string("home-port", zapi_get_return.child_get("attributes-list").children_get()[lif_iterator - 1].child_get_string("port"))
				zapi_post.child_add_string("is-ipv4-link-local", "true")
				zapi_post_return = session.invoke_elem(zapi_post)
				if(zapi_post_return.results_status() == "failed"):
					print("   ---> " + node["node-name"] + ": " + zapi_post.sprintf().strip())
					print("   ---> " + node["node-name"] + ": " + zapi_post_return.sprintf().strip())
				else:
					print("   ---> " + node["node-name"] + ": SUCCESS")
				lif_iterator = lif_iterator + 1
		else:
			print("---> " + node["node-name"] + ": No ports found to create LIFs on!")
			
		# STEP: Reading cluster LIF IP for joining additional nodes later
		if("-01" in node["node-name"]):
			print("--- " + node["node-name"] + ": Reading cluster LIF IP for joining further nodes later...")
			clus_lif_ip = ""
			zapi_get = NaElement("net-interface-get-iter")
			elementQuery = NaElement("query")
			elementInterface = NaElement("net-interface-info")
			elementInterface.child_add_string("vserver", "Cluster")
			elementQuery.child_add(elementInterface)
			zapi_get.child_add_string("max-records", 1)
			zapi_get.child_add(elementQuery)
			zapi_get_return = session.invoke_elem(zapi_get)
			if(zapi_get_return.results_status() == "failed"):
				print("---> " + node["node-name"] + ": " + zapi_get.sprintf().strip())
				print("---> " + node["node-name"] + ": " + zapi_get_return.sprintf().strip())
			else:
				if(int(zapi_get_return.child_get_string("num-records")) == 0):
					print("---> " + node["node-name"] + ": No LIFs found")
				else:
					clus_lif_ip = zapi_get_return.child_get("attributes-list").child_get("net-interface-info").child_get_string("address")
					print("---> " + node["node-name"] + ": SUCCESS")

		# STEP: Join nodes to cluster
		if(not "-01" in node["node-name"]):
			print("--- " + node["node-name"] + ": Joining node to cluster...")
			zapi_post = NaElement("cluster-join")
			zapi_post.child_add_string("cluster-ip-address", clus_lif_ip)
			zapi_post_return = session.invoke_elem(zapi_post)
			if(zapi_post_return.results_status() == "failed"):
				print("---> " + node["node-name"] + ": " + zapi_post_return.sprintf().strip())
				sys.exit(1)
			else:
				zapi_get = NaElement("cluster-create-join-progress-get")
				is_complete = ""
				join_iterator = 1
				while is_complete != "true" and \
						join_iterator < 13:
					time.sleep(10)
					zapi_get_return = session.invoke_elem(zapi_get)
					is_complete = zapi_get_return.child_get("attributes").child_get("cluster-create-join-progress-info").child_get_string("is-complete")
					action_status = zapi_get_return.child_get("attributes").child_get("cluster-create-join-progress-info").child_get_string("status")
					join_iterator = join_iterator + 1
				if(is_complete == "true") and (action_status == "success"):
					print("---> " + node["node-name"] + ": SUCCESS")
				else:
					print("---> " + node["node-name"] + ": " + zapi_get.sprintf().strip())
					print("---> " + node["node-name"] + ": " + zapi_get_return.sprintf().strip())
					sys.exit(1)
	
	print("> " + cluster["cluster-name"] + ": Configuring Cluster")
	
	session = NaServer(cluster["ip"], 1, 140)
	session.set_server_type("Filer")
	session.set_admin_user(cluster["user"], cluster["password"])
	session.set_transport_type("HTTPS")
		
	# STEP: Correcting network ports
	print("--- " + cluster["cluster-name"] + ": Cleaning port configuration...")
	zapi_get = NaElement("net-port-get-iter")
	zapi_get_return = session.invoke_elem(zapi_get)
	if(int(zapi_get_return.child_get_string("num-records")) > 0):
		for port in zapi_get_return.child_get("attributes-list").children_get():
			if(port.child_get_string("ipspace") != "Cluster") and \
				(port.child_get_string("port") != "e0M") and \
				(not port.child_get_string("broadcast-domain") is None):
				# Remove from broadcast domain
				print("   --- " + cluster["cluster-name"] + ": Removing " + port.child_get_string("port") + " from broadcast domain...")
				zapi_post = NaElement("net-port-broadcast-domain-remove-ports")
				elementPorts = NaElement("ports")
				elementPorts.child_add_string("net-qualified-port-name", port.child_get_string("node") + ":" + port.child_get_string("port"))
				zapi_post.child_add_string("ipspace", port.child_get_string("ipspace"))
				zapi_post.child_add_string("broadcast-domain", port.child_get_string("broadcast-domain"))
				zapi_post.child_add(elementPorts)
				zapi_post_return = session.invoke_elem(zapi_post)
				if (zapi_post_return.results_status() == "failed"):
					print("   ---> " + cluster["cluster-name"] + ": " + zapi_post.sprintf().strip())
					print("   ---> " + cluster["cluster-name"] + ": " + zapi_post_return.sprintf().strip())
				else:
					print("   ---> " + cluster["cluster-name"] + ": SUCCESS")

	# STEP: Create IPspaces
	print("--- " + cluster["cluster-name"] + ": Creating IPspaces...")
	for ipspace in cluster["net-ipspaces"]:
		print("   --- " + cluster["cluster-name"] + ": Creating IPspace " + ipspace["ipspace"])
		zapi_post = NaElement("net-ipspaces-create")
		for k, v in ipspace.items():
			zapi_post.child_add_string(k, v)
		zapi_post_return = session.invoke_elem(zapi_post)
		if (zapi_post_return.results_status() == "failed"):
			print("   ---> " + cluster["cluster-name"] + ": " + zapi_post.sprintf().strip())
			print("   ---> " + cluster["cluster-name"] + ": " + zapi_post_return.sprintf().strip())
		else:
			print("   ---> " + cluster["cluster-name"] + ": SUCCESS")
	
	# STEP: Create VLANs
	print("--- " + cluster["cluster-name"] + ": Creating VLANs...")
	for node in cluster["cluster-nodes"]:
		for port in node["net-ports"]:
			if "-" in port["port"]:
				print("   --- " + cluster["cluster-name"] + ": Creating VLAN " + port["port"] + " on node " + node["node-name"])
				zapi_post = NaElement("net-vlan-create")
				elementVLAN = NaElement("vlan-info")
				elementVLAN.child_add_string("node", node["node-name"])
				elementVLAN.child_add_string("parent-interface", port["port"].split("-")[0])
				elementVLAN.child_add_string("vlanid", port["port"].split("-")[1])
				zapi_post.child_add(elementVLAN)
				zapi_post_return = session.invoke_elem(zapi_post)
				if (zapi_post_return.results_status() == "failed"):
					print("   ---> " + cluster["cluster-name"] + ": " + zapi_post.sprintf().strip())
					print("   ---> " + cluster["cluster-name"] + ": " + zapi_post_return.sprintf().strip())
				else:
					print("   ---> " + cluster["cluster-name"] + ": SUCCESS")
	
	# STEP: Create broadcast domains
	print("--- " + cluster["cluster-name"] + ": Creating broadcast domains...")
	for bcdomain in cluster["net-port-broadcast-domains"]:
		print("   --- " + cluster["cluster-name"] + ": Creating broadcast domain " + bcdomain["broadcast-domain"])
		zapi_post = NaElement("net-port-broadcast-domain-create")
		for k, v in bcdomain.items():
			zapi_post.child_add_string(k, v)
		elementPorts = NaElement("ports")
		for node in cluster["cluster-nodes"]:
			for port in node["net-ports"]:
				if(port["ipspace"] != "Cluster") and \
					(port["port"] != "e0M") and \
					(bcdomain["broadcast-domain"] == port["broadcast-domain"]):
					print("   --- " + cluster["cluster-name"] + ": adding " + port["port"] + " on node " + node["node-name"])
					elementPorts.child_add_string("net-qualified-port-name", node["node-name"] + ":" + port["port"])
		if(len(elementPorts.children_get()) > 0):
			zapi_post.child_add(elementPorts)
		zapi_post_return = session.invoke_elem(zapi_post)
		if (zapi_post_return.results_status() == "failed"):
			print("   ---> " + cluster["cluster-name"] + ": " + zapi_post.sprintf().strip())
			print("   ---> " + cluster["cluster-name"] + ": " + zapi_post_return.sprintf().strip())
		else:
			print("   ---> " + cluster["cluster-name"] + ": SUCCESS")
	
	# STEP: Set options
	print("--- " + cluster["cluster-name"] + ": Setting options...")
	for k, v in cluster["options"].items():
		print("   --- " + cluster["cluster-name"] + ": modifying " + k)
		zapi_post = NaElement("options-modify-iter")
		elementAttributes = NaElement("attributes")
		elementAttributesInfo = NaElement("option-info")
		elementAttributesInfo.child_add_string("value", v)
		elementQuery = NaElement("query")
		elementQueryInfo = NaElement("option-info")
		elementQueryInfo.child_add_string("name", k)
		elementAttributes.child_add(elementAttributesInfo)
		elementQuery.child_add(elementQueryInfo)
		zapi_post.child_add(elementQuery)
		zapi_post.child_add(elementAttributes)
		zapi_post_return = session.invoke_elem(zapi_post)
		if (zapi_post_return.results_status() == "failed"):
			print("   ---> " + cluster["cluster-name"] + ": " + zapi_post.sprintf().strip())
			print("   ---> " + cluster["cluster-name"] + ": " + zapi_post_return.sprintf().strip())
		else:
			print("   ---> " + cluster["cluster-name"] + ": SUCCESS")
	
	# STEP: Set network options
	print("--- " + cluster["cluster-name"] + ": Setting network options...")
	zapi_post = NaElement("net-options-modify")
	elementNetOptions = NaElement("net-options")
	for option in cluster["net-options"]:
		print("   --- " + cluster["cluster-name"] + ": adding " + option)
		elementOption = NaElement(option)
		for k, v in cluster["net-options"][option].items():
			elementOption.child_add_string(k, v)
		elementNetOptions.child_add(elementOption)
	zapi_post.child_add(elementNetOptions)
	zapi_post_return = session.invoke_elem(zapi_post)
	if (zapi_post_return.results_status() == "failed"):
		print("   ---> " + cluster["cluster-name"] + ": " + zapi_post.sprintf().strip())
		print("   ---> " + cluster["cluster-name"] + ": " + zapi_post_return.sprintf().strip())
	else:
		print("   ---> " + cluster["cluster-name"] + ": SUCCESS")

	# STEP: Create DNS
	session.set_vserver(cluster["cluster-name"])
	print("--- " + cluster["cluster-name"] + ": Creating DNS...")
	zapi_post = NaElement("net-dns-create")
	elementDomains = NaElement("domains")
	for domain in cluster["net-dns"]["domains"]["string"]:
		elementDomains.child_add_string("string", domain)
	elementServers = NaElement("name-servers")
	for dnsserver in cluster["net-dns"]["name-servers"]["ip-address"]:
		elementServers.child_add_string("ip-address", dnsserver)
	zapi_post.child_add(elementDomains)
	zapi_post.child_add(elementServers)
	zapi_post_return = session.invoke_elem(zapi_post)
	if (zapi_post_return.results_status() == "failed"):
		print("---> " + cluster["cluster-name"] + ": " + zapi_post.sprintf().strip())
		print("---> " + cluster["cluster-name"] + ": " + zapi_post_return.sprintf().strip())
	else:
		print("---> " + cluster["cluster-name"] + ": SUCCESS")
	session.set_vserver("")
	
	# STEP: Create NTP
	print("--- " + cluster["cluster-name"] + ": Creating NTP...")
	for timeserver in cluster["ntp-servers"]:
		zapi_post = NaElement("ntp-server-create")
		for k, v in timeserver.items():
			zapi_post.child_add_string(k, v)
		zapi_post_return = session.invoke_elem(zapi_post)
		if (zapi_post_return.results_status() == "failed"):
			print("---> " + cluster["cluster-name"] + ": " + zapi_post.sprintf().strip())
			print("---> " + cluster["cluster-name"] + ": " + zapi_post_return.sprintf().strip())
		else:
			print("---> " + cluster["cluster-name"] + ": SUCCESS")
	
	# STEP: Set timezone
	print("--- " + cluster["cluster-name"] + ": Setting timezone...")
	zapi_post = NaElement("system-cli")
	elementArgs = NaElement("args")
	elementArgs.child_add_string("arg", "timezone " + cluster["timezone"])
	zapi_post.child_add_string("priv", "admin")
	zapi_post.child_add(elementArgs)
	zapi_post_return = session.invoke_elem(zapi_post)
	if (zapi_post_return.results_status() == "failed"):
		print("---> " + cluster["cluster-name"] + ": " + zapi_post.sprintf().strip())
		print("---> " + cluster["cluster-name"] + ": " + zapi_post_return.sprintf().strip())
	else:
		print("---> " + cluster["cluster-name"] + ": SUCCESS")
	
	# STEP: Create LIFs
	print("--- " + cluster["cluster-name"] + ": Creating LIFs...")
	for lif in cluster["net-interfaces"]:
		if(lif["role"] != "cluster-mgmt"):
			print("   --- " + cluster["cluster-name"] + ": Creating " + lif["interface-name"])
			zapi_post = NaElement("net-interface-create")
			for k, v in lif.items():
				zapi_post.child_add_string(k, v)
			zapi_post_return = session.invoke_elem(zapi_post)
			if (zapi_post_return.results_status() == "failed"):
				print("   ---> " + cluster["cluster-name"] + ": " + zapi_post.sprintf().strip())
				print("   ---> " + cluster["cluster-name"] + ": " + zapi_post_return.sprintf().strip())
			else:
				print("   ---> " + cluster["cluster-name"] + ": SUCCESS")
	
	# STEP: Install licenses
	print("--- " + cluster["cluster-name"] + ": Adding Licenses...")
	zapi_post = NaElement("license-v2-add")
	elementCodes = NaElement("codes")
	for k, v in cluster["licenses"].items():
		print("   --- " + cluster["cluster-name"] + ": Adding " + k)
		elementCodes.child_add_string("license-code-v2", v)
	zapi_post.child_add(elementCodes)
	zapi_post_return = session.invoke_elem(zapi_post)
	if (zapi_post_return.results_status() == "failed"):
		print("---> " + cluster["cluster-name"] + ": " + zapi_post.sprintf().strip())
		print("---> " + cluster["cluster-name"] + ": " + zapi_post_return.sprintf().strip())
	else:
		print("---> " + cluster["cluster-name"] + ": SUCCESS")
	
	# STEP: Create subnets
	print("--- " + cluster["cluster-name"] + ": Creating subnets...")
	for subnet in cluster["net-subnets"]:
		print("   --- Creating subnet " + subnet["subnet-name"])
		zapi_post = NaElement("net-subnet-create")
		elementIPRanges = NaElement("ip-ranges")
		for k, v in subnet.items():
			if(k == "ip-ranges"):
				for range in v["ip-range"]:
					elementIPRanges.child_add_string("ip-range", range)
			else:
				zapi_post.child_add_string(k, v)
		zapi_post.child_add(elementIPRanges)
		zapi_post_return = session.invoke_elem(zapi_post)
		if (zapi_post_return.results_status() == "failed"):
			print("   ---> " + cluster["cluster-name"] + ": " + zapi_post.sprintf().strip())
			print("   ---> " + cluster["cluster-name"] + ": " + zapi_post_return.sprintf().strip())
		else:
			print("   ---> " + cluster["cluster-name"] + ": SUCCESS")
	
	# STEP: Create aggrs
	print("--- " + cluster["cluster-name"] + ": Creating aggregates...")
	for node in cluster["cluster-nodes"]:
		for aggregate in node["aggregates"]:
			print("   --- " + cluster["cluster-name"] + ": Creating aggregates " + aggregate["aggregate"])
			zapi_post = NaElement("aggr-create")
			elementNodes = NaElement("nodes")
			for k, v in aggregate.items():
				if(k == "nodes"):
					for nodename in v["node-name"]:
						if(nodename == ""):
							elementNodes.child_add_string("node-name", node["node-name"])
						else:
							elementNodes.child_add_string("node-name", nodename)
				else:
					zapi_post.child_add_string(k, v)
			zapi_post.child_add(elementNodes)
			zapi_post_return = session.invoke_elem(zapi_post)
			if (zapi_post_return.results_status() == "failed"):
				print("   ---> " + cluster["cluster-name"] + ": " + zapi_post.sprintf().strip())
				print("   ---> " + cluster["cluster-name"] + ": " + zapi_post_return.sprintf().strip())
			else:
				print("   ---> " + cluster["cluster-name"] + ": SUCCESS")

	#STEP: Disable ASUP
	print("--- " + cluster["cluster-name"] + ": Configuring Autosupport...")
	for node in cluster["cluster-nodes"]:
		print("   --- " + cluster["cluster-name"] + ": ASUP on node " + node["node-name"])
		zapi_post = NaElement("autosupport-config-modify")
		zapi_post.child_add_string("node-name", node["node-name"])
		for k, v in cluster["autosupport"].items():
			zapi_post.child_add_string(k, v)
		zapi_post_return = session.invoke_elem(zapi_post)
		if (zapi_post_return.results_status() == "failed"):
			print("   ---> " + cluster["cluster-name"] + ": " + zapi_post.sprintf().strip())
			print("   ---> " + cluster["cluster-name"] + ": " + zapi_post_return.sprintf().strip())
		else:
			print("   ---> " + cluster["cluster-name"] + ": SUCCESS")
	
	#STEP: Allow ssh access for user 'admin'
	print("--- " + cluster["cluster-name"] + ": Allowing admin ssh access...")
	zapi_post = NaElement("security-login-create")
	zapi_post.child_add_string("vserver", cluster["cluster-name"])
	zapi_post.child_add_string("user-name", "admin")
	zapi_post.child_add_string("application", "ssh")
	zapi_post.child_add_string("authentication-method", "password")
	zapi_post.child_add_string("role-name", "admin")
	zapi_post_return = session.invoke_elem(zapi_post)
	if (zapi_post_return.results_status() == "failed"):
		print("---> " + cluster["cluster-name"] + ": " + zapi_post.sprintf().strip())
		print("---> " + cluster["cluster-name"] + ": " + zapi_post_return.sprintf().strip())
	else:
		print("---> " + cluster["cluster-name"] + ": SUCCESS")
	
	# STEP: Set special options
	# NOTE: The session might be closed by the ONTAP, if the option value is really changed (interrupts HTTP(S) traffic)
	try:
		print("--- " + cluster["cluster-name"] + ": Enabling HTTP...")
		zapi_post = NaElement("system-cli")
		elementArgs = NaElement("args")
		elementArgs.child_add_string("arg", "system services web modify -http-enabled true")
		zapi_post.child_add_string("priv", "advanced")
		zapi_post.child_add(elementArgs)
		zapi_post_return = session.invoke_elem(zapi_post)
		if (zapi_post_return.results_status() == "failed"):
			print("---> " + cluster["cluster-name"] + ": " + zapi_post.sprintf().strip())
			print("---> " + cluster["cluster-name"] + ": " + zapi_post_return.sprintf().strip())
		else:
			print("---> " + cluster["cluster-name"] + ": SUCCESS")
	except:
		print("---> " + cluster["cluster-name"] + ": I have modified the branch I am currently sitting on... Session gone ;-)")
		print("---> " + cluster["cluster-name"] + ": Waiting for 10 seconds...")
		# making sure, cluster recovers from HTTP(S) modification
		time.sleep(10)


# Start threads (install cluster by cluster)
setup_threads = []
for cluster in json_data["clusters"]:
	try:
		t = Thread(target=cluster_setup, args=(cluster,))
		t.start()
		setup_threads.append(t)
	except:
		print("> " + cluster["cluster-name"] + ": Error: Unable to start setup thread")

for x in setup_threads: 
    x.join()

print("DONE")