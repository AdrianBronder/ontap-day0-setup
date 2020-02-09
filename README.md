Repository for making my first steps on GitHub.

Sharing some ideas on how to automate FAS/AFF Day0 deployment steps (initialize, node setup, cluster setup). The scripts require access to the service processor of each node.

I am using a config JSON that is processed by three seperate scripts:

1) SSH Initialize:
- Expects nodes to be shut down and in boot loader
- Boots nodes into special menue and performs a factory reset (disks must have been assigned already)

2) SSH Node Setup:
- Expects nodes to be powered on
- Runs node setup (e.g. creates mgmt LIF) and configures a password for the admin user (required for later access via ONTAP APIs)

3) Cluster Setup:
- Creates a cluster and joins nodes
- Performs a couple of steps like setting parameters, creating networks & aggregates, adding licenses...

General:
- All possible steps run in parallel
- It was my first Python learning experience. Please don't be to harsh on me ;-)

Have fun!
