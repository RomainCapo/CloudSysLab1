from cs import CloudStack
import json
import time
import base64

cs = CloudStack(endpoint='https://api.exoscale.ch/v1',
            key='EXOf89522678165c544107d1099',
            secret='JgfCHbX_6cS-I3xoetLEXgHfHlJQe7e2Vlv0SC6XpCc')

print("Deploying Database")
#database
db = cs.deployVirtualMachine(serviceofferingid = "21624abb-764e-4def-81d7-9fc54b5957fb", 
                                templateid = "2e9be9bf-558d-4a0b-8e6d-03695fe93555", 
                                zoneid = "1128bd56-b4d9-4ac6-a7b9-c715b187ce11",
                                keypair = "CloudSys",
                                securitygroupids = ["83e73717-774f-4361-b8c1-a28158dd09c1", "21714f20-3e37-4e45-93da-b515ecdfdc03"])
databaseID = db["id"]
jobID = db["jobid"]

#wait for job
while True:
    res = cs.queryAsyncJobResult(jobid = jobID)
    if(res["jobstatus"] == 1):
        break
    time.sleep(1)

allVM = cs.listVirtualMachines()
for vm in allVM["virtualmachine"]:
    if vm["id"] == databaseID:
        databaseVM = vm
databaseIP = databaseVM["nic"][0]["ipaddress"]

print("Deploying Backend")
#backend
backend_script = "#!/bin/sh\nsudo sed -i 's/185.19.29.168/" + databaseIP + "/g' /var/www/html/.env"
byte = backend_script.encode("ascii") 
b64_bytes = base64.b64encode(byte) 
backend = cs.deployVirtualMachine(serviceofferingid = "21624abb-764e-4def-81d7-9fc54b5957fb", 
                                templateid = "349b4b9b-d65d-41a3-a62b-54f835358f2c", 
                                zoneid = "1128bd56-b4d9-4ac6-a7b9-c715b187ce11",
                                keypair = "CloudSys",
                                securitygroupids = ["83e73717-774f-4361-b8c1-a28158dd09c1", "805164ab-6858-4b9f-ad11-336291c49aa6"],
                                userdata = b64_bytes)
backendID = backend["id"]
jobID = backend["jobid"]

#wait for job
while True:
    res = cs.queryAsyncJobResult(jobid = jobID)
    if(res["jobstatus"] == 1):
        break
    time.sleep(1)

allVM = cs.listVirtualMachines()
for vm in allVM["virtualmachine"]:
    if vm["id"] == backendID:
        backendVM = vm
backendIP = backendVM["nic"][0]["ipaddress"]

print("Deploying Frontend")
#frontend
frontend_script = "#!/bin/sh\ncd /home/ubuntu/vue-realworld-example-app/\nsudo sed -i 's/89.145.166.62/" + backendIP + "/g' /home/ubuntu/vue-realworld-example-app/src/common/config.js\nyarn build\nsudo cp -r /home/ubuntu/vue-realworld-example-app/dist/. /var/www/html"
byte = frontend_script.encode("ascii") 
b64_bytes = base64.b64encode(byte) 
frontend = cs.deployVirtualMachine(serviceofferingid = "21624abb-764e-4def-81d7-9fc54b5957fb", 
                                templateid = "7dd93291-6fb7-439d-b937-c7e50f225edf", 
                                zoneid = "1128bd56-b4d9-4ac6-a7b9-c715b187ce11",
                                keypair = "CloudSys",
                                securitygroupids = ["83e73717-774f-4361-b8c1-a28158dd09c1", "8fb66678-38d8-4709-9908-125fb150e881"],
                                userdata = b64_bytes)
frontendID = frontend["id"]
jobID = frontend["jobid"]

#wait for job
while True:
    res = cs.queryAsyncJobResult(jobid = jobID)
    if(res["jobstatus"] == 1):
        break
    time.sleep(1)

allVM = cs.listVirtualMachines()
for vm in allVM["virtualmachine"]:
    if vm["id"] == frontendID:
        frontendVM = vm
frontendIP = frontendVM["nic"][0]["ipaddress"]
print("Application deployed on " + frontendIP + ". Please wait at least 1min to let the application start up properly. If it does not work directly try again after some time.")

input("Press Enter to delete the created VMs...")
cs.destroyVirtualMachine(id = databaseID)
cs.destroyVirtualMachine(id = frontendID)
cs.destroyVirtualMachine(id = backendID)