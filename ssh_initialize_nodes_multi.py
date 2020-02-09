#!/usr/bin/python3

# Author:		Adrian Bronder
# Date:			October 15th, 2018
# Description:  Initializing system (expecting nodes to be at loader prompt)

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

def node_initialize(node):
	sp = pxssh.pxssh()
	counter = 0
	print(node["node-name"] + " -> Logging into SP")
	if(not sp.login(node["sp-ip"], node["user"], node["password"], auto_prompt_reset=False)):
		print(node["node-name"] + " -> SSH session failed on login.")
		print(str(sp))
	else:
		print(node["node-name"] + " -> SSH session login successful")
		
		# Switching to system console
		exec_ssh(sp, "^SP.*>", "system console", node["node-name"])
		exec_ssh(sp, None, "", node["node-name"])
		
		# Wait for loader prompt and boot into boot menu
		counter = 0
		while not exec_ssh(sp, "LOADER-[AB]{1}>", "boot_ontap menu", node["node-name"]) and \
				(counter < 12):
			print(node["node-name"] + " -> waiting 10 seconds...")
			counter = counter + 1
			sys.time(10)
		if(counter >= 12):
			print(node["node-name"] + " -> Could not set prompt. Exiting NOW!")
			sys.exit(1)
		
		# selecting option for initialize in boot menu
		counter = 0
		while not exec_ssh(sp, "Selection .*\?", "4", node["node-name"]) and \
			(counter < 12):
			print(node["node-name"] + " -> waiting 10 seconds...")
			counter = counter + 1
			sys.time(10)
		if(counter >= 12):
			print(node["node-name"] + " -> Could not set prompt. Exiting NOW!")
			sys.exit(1)
		
		# Confirming warnings
		counter = 0
		while not exec_ssh(sp, "Zero disks, reset config and install a new file system\?:", "y", node["node-name"]) and \
			(counter < 12):
			print(node["node-name"] + " -> waiting 10 seconds...")
			counter = counter + 1
			sys.time(10)
		if(counter >= 12):
			print(node["node-name"] + " -> Could not set prompt. Exiting NOW!")
			sys.exit(1)
		else:
			exec_ssh(sp, "This will erase all the data on the disks, are you sure\?:", "y", node["node-name"])
		
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
			t = Thread(target=node_initialize, args=(node,))
			t.start()
			setup_threads.append(t)
		except:
			print("Error: unable to start thread")

for x in setup_threads: 
    x.join()

print("I am done")