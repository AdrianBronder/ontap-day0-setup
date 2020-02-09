#!/usr/bin/python3

# Author:		Adrian Bronder
# Date:			October 15th, 2018
# Description:  Setup preparing nodes for cluster create/join

import sys
import time
from threading import Thread
from pexpect import pxssh
import re
import json

def print_usage():
	print("\nUsage: " + __file__ + " <config_file>\n")
	print("<config_file> -- JSON file with setup parameters\n")
	
def exec_ssh(session, match_str, send_string, hostname):
	found = False
	if(not match_str is None):
		# Load content
		session.prompt()
		# Get strings by row
		ssh_return = session.before.decode('UTF-8').strip().split("\n")
		# Print last row
		print(hostname + " -> I found this string: " + ssh_return[-1])
		if(re.match(match_str, ssh_return[-1])):
			found = True
	
	# Compare with input RegEx and send string if valid
	if(not send_string is None):
		if((match_str is None) or \
			found):
			if(send_string == "c") or \
				(send_string == "d"):
				print(hostname + " -> I am sending 'ctrl-" + send_string + "'")
				session.sendcontrol(send_string)
			else:
				print(hostname + " -> I am sending '" + str(send_string) + "'")
				session.sendline(str(send_string))
		else:
			print(hostname + " -> Unexpected string..." + send_string)
	
	return found

def node_setup(node):
	sp = pxssh.pxssh()
	print(node["node-name"] + " -> Logging into SP")
	if(not sp.login(node["sp-ip"], node["user"], node["password"], auto_prompt_reset=False)):
		print(node["node-name"] + " -> SSH session failed on login.")
		print(str(sp))
	else:
		print(node["node-name"] + " -> SSH session login successful")
		
		# Switching to system console
		if(not exec_ssh(sp, "^SP.*>", "system console", node["node-name"])):
			print(node["node-name"] + " -> Unexpected prompt. Exiting NOW!")
			sys.exit(1)
		exec_ssh(sp, None, "", node["node-name"])
		
		# Get to default ONTAP prompt
		counter = 0
		while not exec_ssh(sp, "::\**>", None, node["node-name"]) and \
				(counter < 5):
			last_row = sp.before.decode('UTF-8').strip().split("\n")[-1]
			if(str("login:") in last_row):
				exec_ssh(sp, None, node["user"], node["node-name"])
			elif("assword:" in last_row):
				exec_ssh(sp, None, node["password"], node["node-name"])
			else:
				exec_ssh(sp, None, "c", node["node-name"])
			counter = counter + 1
		if(counter >= 5):
			print(node["node-name"] + " -> Could not set prompt. Exiting NOW!")
			sys.exit(1)
			
		# preparing console - no page breaks
		exec_ssh(sp, None, "rows 0", node["node-name"])
		# starting cluster setup
		exec_ssh(sp, None, "cluster setup", node["node-name"])
		# Acknowledging ASUP warning
		if(not exec_ssh(sp, "Type yes to confirm and continue \{yes\}:", "yes", node["node-name"])):
			print(node["node-name"] + " -> Unexpected return. Exiting NOW!")
			sys.exit(1)
		
		# Send node management details
		if(not exec_ssh(sp, "Enter the node management interface port \[", "e0M", node["node-name"])):
			print(node["node-name"] + " -> Unexpected return. Exiting NOW!")
			sys.exit(1)
		exec_ssh(sp, None, node["ip"], node["node-name"])
		exec_ssh(sp, None, "255.255.255.0", node["node-name"])
		exec_ssh(sp, None, "10.65.59.1", node["node-name"])
		
		# Send "Enter" to continue on command line
		exec_ssh(sp, None, "", node["node-name"])
		exec_ssh(sp, None, "", node["node-name"])
		
		# Exit cluster setup
		if(not exec_ssh(sp, "Do you want to create a new cluster or join an existing cluster?.*", "c", node["node-name"])):
			print(node["node-name"] + " -> Unexpected return. Exiting NOW!")
			sys.exit(1)
		
		# Set admin password
		if(not exec_ssh(sp, "::\**>", "security login password -user " + node["user"], node["node-name"])):
			print(node["node-name"] + " -> Unexpected return. Exiting NOW!")
			sys.exit(1)
		exec_ssh(sp, None, "", node["node-name"])
		exec_ssh(sp, None, node["password"], node["node-name"])
		exec_ssh(sp, None, node["password"], node["node-name"])
		
		# Log out from ONTAP properly and return to service processor prompt
		exec_ssh(sp, "::\**>", "exit", node["node-name"])
		exec_ssh(sp, None, "d", node["node-name"])
	print(node["node-name"] + " -> logging out...")
	sp.logout()

	
if(len(sys.argv) != 2):
	print_usage()
	sys.exit(1)

with open(sys.argv[1]) as json_file:
        json_data = json.load(json_file)


setup_threads = []
for cluster in json_data["clusters"]:
	for node in cluster["cluster-nodes"]:
		try:
			t = Thread(target=node_setup, args=(node,))
			t.start()
			setup_threads.append(t)
		except:
			print("Error: unable to start thread")

for x in setup_threads: 
    x.join()

print("I am done")