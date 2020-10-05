import errno
import os
import openstack
import time

from openstack import connection
from openstack import utils
from getpass   import getpass
from base64    import b64encode
import subprocess

#ssh -i key.pem ubuntu@86.119.31.215 - front
#ssh -i key.pem ubuntu@86.119.30.120 - back
#ssh -i key.pem ubuntu@86.119.31.232 - DB

conn = openstack.connect(cloud="openstack")

frontend_conf = {"ip_id": "bd52f34b-1291-49e3-942c-792283858217",
                 "key":"test-keypair",
                 "grp":"default",
                 "flv":"m1.small",
                 "net":"public",
                 "img":"3e11375c-a89e-4b98-be73-5b883faed43c"}
backend_conf  = {"ip_id": "0afc29c3-b8cd-4b30-8efb-bc9524cc5f45",
                 "key":"test-keypair",
                 "grp":"default",
                 "flv":"m1.small",
                 "net":"public",
                 "img":"0a5a1758-ecfc-4ed7-8980-b8f573fed400"}
database_conf = {"ip_id": "323d66f9-2900-4fa3-82cf-5270eb33fee0",
                 "key":"test-keypair",
                 "grp":"default",
                 "flv":"m1.small",
                 "net":"public",
                 "img":"6fe116a6-d83e-4e14-8fbe-106aac40a2c1"}

def create_instance(conn, name, config, userdata = ""):

    sgrp = conn.network.find_security_group(config["grp"])
    image = conn.compute.find_image(config["img"])
    flavor = conn.compute.find_flavor(config["flv"])
    network = conn.network.find_network(config["net"])
    keypair = conn.compute.find_keypair(config["key"])

    args= {
        'name' : name,
        'image_id' : image.id,
        'flavor_id' : flavor.id,
        'key_name' : config["key"],
        'network' : network,
        'sgrp' : sgrp
    }

    server = conn.compute.create_server(**args)
    print("Waiting for creation...")
    conn.compute.wait_for_server(server, status='ACTIVE', failures=None, interval=2, wait=120)
    server = conn.get_server_by_id(server.id)

    ip = conn.network.get_ip(config["ip_id"])
    attach_floating_ip_to_instance(conn, server, ip)

    return server

def attach_floating_ip_to_instance(conn, instance, floating_ip):
    instance_port = None
    for port in conn.network.ports():
        if port.device_id == instance.id:
            instance_port = port

    conn.network.add_ip_to_port(instance_port, floating_ip)

def print_floating_ip_id(conn, public_network='public'):
    print('Checking Floating IP...')
    for floating_ip in conn.network.ips(tenant_id=conn.compute.get_project_id()):
        print(floating_ip.floating_ip_address, " -> ", floating_ip.id)

def delete_instance(conn, inst):
    print("Delete instance ...",)
    conn.compute.delete_server(inst)

if "__main__":

    db_inst = create_instance(conn, "database-inst", database_conf)
    back_inst = create_instance(conn, "backend-inst", backend_conf)
    front_inst = create_instance(conn, "frontend-inst", frontend_conf)

    delete = 'C'
    while delete != 'E':
        delete = input('End an d delete instances (E) ?')

    delete_instance(conn, front_inst)
    delete_instance(conn, back_inst)
    delete_instance(conn, db_inst)
