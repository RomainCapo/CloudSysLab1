from azure.common.client_factory import get_client_from_cli_profile
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network.v2017_03_01.models import NetworkSecurityGroup
import base64
import argparse

def init(RESOURCE_GROUP_NAME, LOCATION, VNET_NAME = "CloudSys-vnet-AutoDeploy"):

    print(f"Provisioning a virtual machine...some operations might take a minute or two.")

    # Step 1: Provision a resource group

    # CONSTANT
    SUBNET_NAME = "default-AutoDeploy"

    # Obtain the management object for resources, using the credentials from the CLI login
    resource_client = get_client_from_cli_profile(ResourceManagementClient)

    # Provision the resource group.
    rg_result = resource_client.resource_groups.create_or_update(RESOURCE_GROUP_NAME,
        {
            "location": LOCATION
        }
    )

    print(f"Provisioned resource group {rg_result.name} in the {rg_result.location} region")

    # Step 2: provision a virtual network

    # Obtain the management object for networks
    network_client = get_client_from_cli_profile(NetworkManagementClient)

    # Provision the virtual network and wait for completion
    poller = network_client.virtual_networks.begin_create_or_update(RESOURCE_GROUP_NAME,
        VNET_NAME,
        {
            "location": LOCATION,
            "address_space": {
                "address_prefixes": ["10.0.0.0/24"]
            }
        }
    )

    vnet_result = poller.result()

    print(f"Provisioned virtual network {vnet_result.name} with address prefixes {vnet_result.address_space.address_prefixes}")

    # Step 3: Provision the subnet and wait for completion
    poller = network_client.subnets.begin_create_or_update(RESOURCE_GROUP_NAME, 
        VNET_NAME, SUBNET_NAME,
        { "address_prefix": "10.0.0.0/24" }
    )

    subnet_result = poller.result()

    print(f"Provisioned virtual subnet {subnet_result.name} with address prefix {subnet_result.address_prefix}")

    return network_client, subnet_result

def createVM(network_client, subnet_result, KEY_DATA, IMAGE_NAME, VM_NAME, USERNAME, VM_SIZE, RESOURCE_GROUP_NAME, LOCATION, script = ""):
    
    # CONSTANTS
    IP_NAME = "CloudSys-ip-AutoDeploy-" + VM_NAME
    IP_CONFIG_NAME = "CloudSys-ip-config-AutoDeploy-" + VM_NAME 
    NIC_NAME = "CloudSys-nic-AutoDeploy-" + VM_NAME
    NSG_NAME = "CloudSys-nsg-AutoDeploy-" + VM_NAME

    sample_string = script
    sample_string_bytes = sample_string.encode("ascii") 
    base64_bytes = base64.b64encode(sample_string_bytes) 
    SCRIPT_BASE64 = base64_bytes.decode("ascii")   

    # Step 4: Provision an IP address and wait for completion
    poller = network_client.public_ip_addresses.begin_create_or_update(RESOURCE_GROUP_NAME,
        IP_NAME,
        {
            "location": LOCATION,
            "sku": { "name": "Standard" },
            "public_ip_allocation_method": "Static",
            "public_ip_address_version" : "IPV4"
        }
    )

    ip_address_result = poller.result()

    print(f"Provisioned public IP address {ip_address_result.name} with address {ip_address_result.ip_address}")

    # --- Security Group ---

    if(VM_NAME == "database"):
        ACCESS = "Deny"
    else:
        ACCESS = "Allow"

    async_nsg_create = network_client.network_security_groups.begin_create_or_update(RESOURCE_GROUP_NAME,
        NSG_NAME, 
        {
            "location": LOCATION,
            "securityRules": [
                {
                    "name": "Port_80",
                    "properties": {
                        "protocol": "*",
                        "sourcePortRange": "*",
                        "destinationPortRange": "80",
                        "sourceAddressPrefix": "*",
                        "destinationAddressPrefix": "*",
                        "access": ACCESS,
                        "priority": 100,
                        "direction": "Inbound",
                        "sourcePortRanges": [],
                        "destinationPortRanges": [],
                        "sourceAddressPrefixes": [],
                        "destinationAddressPrefixes": []
                    }
                },
                {
                    "name": "Port_22",
                    "properties": {
                        "protocol": "*",
                        "sourcePortRange": "*",
                        "destinationPortRange": "22",
                        "sourceAddressPrefix": "*",
                        "destinationAddressPrefix": "*",
                        "access": "Allow",
                        "priority": 110,
                        "direction": "Inbound",
                        "sourcePortRanges": [],
                        "destinationPortRanges": [],
                        "sourceAddressPrefixes": [],
                        "destinationAddressPrefixes": []
                    }
                }
            ]
        }
    )

    nsg = async_nsg_create.result()

    # Step 5: Provision the network interface client
    poller = network_client.network_interfaces.begin_create_or_update(RESOURCE_GROUP_NAME,
        NIC_NAME,
        {
            "location": LOCATION,
            "ip_configurations": [ {
                "name": IP_CONFIG_NAME,
                "subnet": { "id": subnet_result.id },
                "public_ip_address": {"id": ip_address_result.id },
                "private_ip_address": "10.0.0.4"
            }],
            "network_security_group": {
                "id": nsg.id
            }
        }
    )

    nic_result = poller.result()

    print(f"Provisioned network interface client {nic_result.name}")

    # Step 6: Provision the virtual machine

    # Obtain the management object for virtual machines
    compute_client = get_client_from_cli_profile(ComputeManagementClient)

    print(f"Provisioning virtual machine {VM_NAME}; this operation might take a few minutes.")

    # Provision the VM 

    poller = compute_client.virtual_machines.begin_create_or_update(RESOURCE_GROUP_NAME, VM_NAME,
        {
            "location": LOCATION,
            "storage_profile": {
                "image_reference": {
                    "id": "/subscriptions/52a91af7-73bf-4782-979d-0777122f0ec8/resourceGroups/CloudSys/providers/Microsoft.Compute/images/" + IMAGE_NAME
                }
            },
            "hardware_profile": {
                "vm_size": VM_SIZE
            },
            "os_profile": {
                "computer_name": VM_NAME,
                "admin_username": USERNAME,
                "custom_data": SCRIPT_BASE64,
                "linuxConfiguration": {
                            "disablePasswordAuthentication": True,
                            "ssh": {
                                "publicKeys": [
                                    {
                                        "path": "/home/" + USERNAME + "/.ssh/authorized_keys",
                                        "keyData": KEY_DATA
                                    }
                                ]
                            },
                            "provisionVMAgent": True
                        },
                        "secrets": [],
                        "allowExtensionOperations": True
                    },
            "network_profile": {
                "network_interfaces": [{
                    "id": nic_result.id,
                }]
            }
        }
    )

    vm_result = poller.result()

    print(f"Provisioned virtual machine {vm_result.name}")   

    if(VM_NAME == "database"):
        return "10.0.0.4"

    if(VM_NAME == "backend"):
        return ip_address_result.ip_address

    if(VM_NAME == "frontend"):
        return ip_address_result.ip_address

if __name__ == "__main__":
    # Parameters
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--location', default='southcentralus', help='Define the location of the deployment')
    parser.add_argument('--resource_group_name', default='CloudSys-AutoDeploy', help='Define the resource group name')
    parser.add_argument('--vm_size', default='Standard_DS1_v2', help='Define the virtual machine size')
    
    args = parser.parse_args()

    LOCATION = args.location
    RESOURCE_GROUP_NAME = args.resource_group_name
    VM_SIZE = args.vm_size

    # Init resource group and virtual network
    network_client, subnet_result = init(RESOURCE_GROUP_NAME=RESOURCE_GROUP_NAME, LOCATION=LOCATION)

    # Database
    USER_DB = "databaseuser"
    script = "#!/bin/sh\n"
    KEY_DATA_DB = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQCjw0sLcKK/n/PQ2dUGtnJjhOPZ\r\nHvRKkF8WGYqpSRAr4env0hap2M5k4O7Fg4RYKlmf/DWe7uHj1mmoX7VWEbjsMjsJ\r\nF6MfsaGfXAyWE6DH4toah7x2frxyl2c+MPokoW/Flnd47khoUilDr1CZAKbqvLoz\r\nQoEkq1X8R2FI6v6eVar5LdtANkOu3r0ExeBpaSR+eskWlnTOrNaWnfH1E0g4ZAlk\r\nljoT1b0WhBxiQCOksFgyjAq9kutfCjyPpgC05oDErwAAxYStoqA7N7wiGREP/YgC\r\nWBDHTGAqMwA5+9+plmGMlEEOGO32cKWIk41JH5qLO5PGEQDQvCTNyuTxXNPkNWX4\r\na4ZmOe3fo27Fum7qfr1nZ4BScCfcZO0bvXyM6DgWXAuaPig63unia+PzllDqnIsC\r\ndW2R/iHn2JeFhizqUMnYnF6IF1cNyxxkDOW+h2cK9FxgbeagsqlJWso/cRFpmC5f\r\nKasUFEkIUoW73T/QCWSkYEAk1XKIVMVOYoq3ppE= generated-by-azure\r\n"
    IP_PRIVATE_DB = createVM(network_client, subnet_result, KEY_DATA_DB, "db-image", "database", USER_DB, VM_SIZE, RESOURCE_GROUP_NAME, LOCATION, script=script)

    # Backend
    USER_BACKEND = "backenduser"
    script = "#!/bin/sh\ncd /var/www/html\nsudo git clone https://github.com/dicksor/laravel-realworld-example-app.git\ncd laravel-realworld-example-app\nsudo sed -i 's/10.0.1.6/" + IP_PRIVATE_DB + "/g' /home/" + USER_BACKEND + "/.env\nsudo cp /home/" + USER_BACKEND + "/.env /var/www/html/laravel-realworld-example-app\nsudo composer install --ignore-platform-reqs\nsudo php artisan key:generate --force\nsudo php artisan jwt:generate\nsudo php artisan migrate --force\nsudo php artisan db:seed --force\nsudo php artisan config:clear\nsudo composer dump-autoload"
    KEY_DATA_BACK = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC/w6ZVmZFNaSpcI+QLrkQyGrT0\r\ntaXzgCqbQHzbn64o9FF56vQjcCC3SnDp2J4at4Sp2WD2Xj2SiIltQxdGqDuXhgpj\r\nv+KJus5Iv6gYXE3haixkYeTuGTUz2H8lg/CMIGBDZ5KGEB2dguCzN6o2xjr/XvDr\r\n10lBJa4meOlTLDp4weDq2jRNxpk2scHZRs9DfRQbJhR3JpqeJ54yazLLH+NnYXUO\r\n3RIlVour8cDP5X7PSVUwBeNkQ56xChZRTR8Fq2BYJMqiFlnaIXHeQM+2iO1FFs0a\r\nh4ZSnQO+ElpYtiQIBzar3avL7x+KfBmviTM4D6+YHeU5dflgw16BtPhI4QVLx0bk\r\n2gZVp5qj2/v9cT65AxnFxoH7DXmC3vcisAvfYgpUkqWatNR/DNriy8cuBuI9lBIL\r\nNe+JsRwGbH0lY2n0p1czD6z/y8jBGZZrknaoqjAX6MuWo3FdhwT17uimaa2kvfnZ\r\ncR/R9IYRyLg9pPe1XQbidnmOdhnykYcX+aRQ9xc= generated-by-azure\r\n"
    IP_PUBLIC_BACK = createVM(network_client, subnet_result, KEY_DATA_BACK, "back-end-image", "backend", USER_BACKEND, VM_SIZE, RESOURCE_GROUP_NAME, LOCATION, script=script)

    # Front-end
    USER_FRONTEND = "frontenduser"
    script = "#!/bin/sh\ncd /home/" + USER_FRONTEND + "\nsudo git clone https://github.com/dicksor/vue-realworld-example-app.git\nsudo sed -i 's/70.37.87.34/" + IP_PUBLIC_BACK + "/g' /home/" + USER_FRONTEND + "/vue-realworld-example-app/src/common/config.js\ncd vue-realworld-example-app\nsudo npm install -g editorconfig\nsudo yarn install --ignore-engines\nsudo yarn serve"
    KEY_DATA_FRONT = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDCwhmizEha0tkwIKhNOPSAwfPZ\r\nrBVD54C0wLFH4eRULuIyheKQcmpHr0xVqYN8coFIRBeIGCoM7p0Kuc8kVE9App9I\r\nv5IS1futdqtilPShEIPIVsJok9ztViuUbHFjVR7Q5ihJNnUNWljzo7i8rGgll91u\r\nzTFWsSiFmxoH6FksE8sAqkO8OcNbj7jmqCfY2v6Sxh07MurFRvOEBoJXJS5GFyiJ\r\nXbmHTMZ0FaMtiP4cPNAhV9l8a3DToL9y1v68soVJV9nbmF0fQ81gdopoHq0zDIPQ\r\nIEWk2BN6OqYgS+MRz4x1u6vVzySVSh6Jy2bZ8G3ZMgXtIz1GAZx2L04nbXOheOHi\r\n2hswrlG6vknhuSMcZqpi9CWkt58H4cABkzpCKxFsTSPsaXGQ4RFekXlX8is1WUz8\r\nP9JJj0YIJoS1iy3dIveTAH4/uc+Hv/WV8TUf+NYjJoWDdbCYOJLub7r9UdGuC/ZU\r\nWyJgnDt2Rr3O8UGpNTSZQne6NpGqidmWgdSbZiM= generated-by-azure\r\n"
    IP_PUBLIC_FRONT = createVM(network_client, subnet_result, KEY_DATA_FRONT, "front-end-image", "frontend", USER_FRONTEND, VM_SIZE, RESOURCE_GROUP_NAME, LOCATION, script=script)

    print(f"Application is running at : {IP_PUBLIC_FRONT}")

    if input("Press [y] to delete the resource group : ") == 'y':
        RESOURCE_GROUP_NAME = "CloudSys-AutoDeploy"
        client = get_client_from_cli_profile(ResourceManagementClient)
        delete_async_operation = client.resource_groups.delete(RESOURCE_GROUP_NAME)
        delete_async_operation.wait()
        print("Resource group deleted !")


    