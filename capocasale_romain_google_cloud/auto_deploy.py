"""
Romain Capocasale
02.10.2020
HES-SO Master
CloudSys Lab 1
"""

"""Note :
For the script to work properly, an internal and external IP address must be reserved on the network. 
In addition, the images of the three instances must exist in Google Cloud. 

By default, the database is in a security group that does not open any port from the outside. 
The back-office and front-office are in a security group where port 80 is open from the outside.        
"""

import os
import time
import argparse

import googleapiclient.discovery


def wait_for_operation(compute, project, zone, operation):
    """waits until the current operation is completed. 
    Method from : https://github.com/GoogleCloudPlatform/python-docs-samples/blob/master/compute/api/create_instance.py

    Args:
        compute (googleapiclient.discovery.Resource): Google API Instance.
        project (str): Project id.
        zone (str): Zone name.
        operation (dict): Operation dict return after VM instanciation or deletion.
    """

    print('Waiting for operation to finish...')
    while True:
        result = compute.zoneOperations().get(
            project=project,
            zone=zone,
            operation=operation).execute()

        if result['status'] == 'DONE':
            print("done.")
            if 'error' in result:
                raise Exception(result['error'])
            return result

        time.sleep(1)

def create_instance(compute, name, image, startup_script='', project_id='cloudsys-290308', zone='europe-west6-a', flavor='e2-micro', private_ip=None, public_ip=None, tags=None):
    """Allow to create a VM instance.

    Args:
        compute (googleapiclient.discovery.Resource): Google API Instance.
        name (str): VM instance name.
        image (str): Image name.
        startup_script (str, optional): Instance startup script. Defaults to ''.
        project_id (str, optional): Project id. Defaults to 'cloudsys-290308'.
        zone (str, optional): Zone name. Defaults to 'europe-west6-a'.
        flavor (str, optional): Desired characteristic of the instance . Defaults to 'e2-micro'.
        private_ip (str, optional): Private static IP adress for database . Assume that the private IP address is reserved in Google Cloud. Defaults to None.
        public_ip (str, optional): Private public IP adress for back office. Assume that the public IP address is reserved in Google Cloud. Defaults to None.
        tags (str, optional): Network tags for the external opening of ports. Defaults to None.

    Returns:
        dict: Operation dict return after VM instanciation.
    """

    '''if startup_script != '' : 
        startup_script = open(os.path.join(os.path.dirname('__file__'), startup_script), 'r').read()'''

    config = {
        "kind": "compute#instance",
        "name": name,
        "zone": f"projects/{project_id}/zones/{zone}",
        "machineType": f"projects/{project_id}/zones/{zone}/machineTypes/{flavor}",
        "displayDevice": {
            "enableDisplay": False
        }, 
        "tags": {
            "items": tags
        },
         "disks": [
             {
                "type": "PERSISTENT",
                "boot": True,
                "mode": "READ_WRITE",
                "autoDelete": True,
                "deviceName": image,
                 "initializeParams": {
                   "sourceImage": f"projects/{project_id}/global/images/{image}",
                   "diskType": f"projects/{project_id}/zones/{zone}/diskTypes/pd-standard",
                   "diskSizeGb": "20"
                 },
                 "diskEncryptionKey": {}
         }],
         
         "networkInterfaces": [
            {
              "subnetwork": "projects/cloudsys-290308/regions/europe-west6/subnetworks/default",
              "accessConfigs": [
                {
                  "kind": "compute#accessConfig",
                  "name": "External NAT",
                  "type": "ONE_TO_ONE_NAT",
                  "networkTier": "STANDARD"
                }
              ],
            }
        ],
        "description": "",
        "metadata": {
            "items": [{
                "key": "startup-script",
                "value": startup_script
            }]
        }
    }

    if private_ip is not None : config['networkInterfaces'][0]['networkIP'] = private_ip
    if public_ip is not None : config['networkInterfaces'][0]['accessConfigs'][0]['natIP'] = public_ip

    return compute.instances().insert(project=project_id,zone=zone,body=config).execute()

def delete_instances(compute, instance, project_id='cloudsys-290308', zone='europe-west6-a'):
    """Allow to delete a VM instance.

    Args:
        compute (googleapiclient.discovery.Resource): Google API Instance.
        instance (str): VM instance name.
        project_id (str, optional): Project id. Defaults to 'cloudsys-290308'.
        zone (str, optional): Zone name. Defaults to 'europe-west6-a'.

    Returns:
        dict: Operation dict return after VM deletion.
    """

    return compute.instances().delete(project=project_id,zone=zone,instance=instance).execute()

def open_script(startup_script):
    """Open the startup script from script file path. 
    If path is empty, return empty script

    Args:
        startup_script (str): Startup script file path.

    Returns:
        str: Startup script.
    """
    if startup_script != '' : 
        return  open(os.path.join(os.path.dirname('__file__'), startup_script), 'r').read()
    else :
        return ''

def replace_internal_ip(script, new_ip, old_ip='10.172.0.2', line_to_insert=1):
    """Replace the internal IP address of the database in back office startup script.

    Args:
        script (str): Startup script.
        new_ip (str): Database internal IP address.
        old_ip (str, optional): Old database internal IP in the .env Laravel file. Defaults to '10.172.0.2'.
        line_to_insert (int, optional): Line number in the script where to add the command line. Defaults to 1.

    Returns:
        str: Updated statup script
    """
    script_list = script.split('\n')
    script_list.insert(line_to_insert, f"sudo sed -i 's/{old_ip}/{new_ip}/g' /home/romain_capocasale99/.env")
    return '\n'.join(script_list)

def replace_external_ip(script, new_ip, old_ip='35.216.163.54', line_to_insert=3):
    """Replace the external IP address of the back-office in front office startup script.

    Args:
        script (str): Startup script.
        new_ip (str): Back-office external IP address.
        old_ip (str, optional): Old back-office external IP in the config.js file. Defaults to '10.172.0.2'.
        line_to_insert (int, optional): Line number in the script where to add the command line. Defaults to 3.

    Returns:
        str: Updated statup script
    """

    script_list = script.split('\n')
    script_list.insert(line_to_insert, f"sudo sed -i 's/{old_ip}/{new_ip}/g' /home/romain_capocasale99/vue-realworld-example-app/src/common/config.js")
    return '\n'.join(script_list)

def main(project_id, 
    zone, 
    json_credentials,
    database_instance_name,
    back_office_instance_name,
    front_office_instance_name,
    database_image_name,
    back_office_image_name,
    front_office_image_name,
    database_flavor,
    back_office_flavor,
    front_office_flavor,
    database_startup_script,
    back_office_startup_script,
    front_office_startup_script,
    database_internal_ip,
    back_office_external_ip):

    # In some cases, the connection to the Google Cloud api must be made using credentials contained in a JSON file. 
    # In other cases, the connection is made automatically with the Google Cloud SDK installed on the computer. 
    # If no JSON file is provided, assume that the connection is made automatically.
    if json_credentials is not None :
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"]=json_credentials

    compute = googleapiclient.discovery.build('compute', 'v1')
    instantiated_instances = []

    # Database instanciation
    database_startup_script = open_script(database_startup_script)

    operation = create_instance(compute, database_instance_name, database_image_name, startup_script=database_startup_script, project_id=project_id, zone=zone, flavor=database_flavor, private_ip=database_internal_ip)
    wait_for_operation(compute, project_id, zone, operation['name'])
    instantiated_instances.append(database_instance_name)

    print("Database instance creation ready !\n")

    # Back office instanciation
    back_office_startup_script = open_script(back_office_startup_script)
    back_office_startup_script = replace_internal_ip(back_office_startup_script, database_internal_ip) # Comment the line for not replacing the database IP in the script

    operation = create_instance(compute, back_office_instance_name, back_office_image_name, startup_script=back_office_startup_script, project_id=project_id, zone=zone, flavor=back_office_flavor, public_ip=back_office_external_ip, tags=['http-server'])
    wait_for_operation(compute, project_id, zone, operation['name'])
    instantiated_instances.append(back_office_instance_name)

    print("Back office instance creation ready !\n")

    # Front office instanciation
    front_office_startup_script = open_script(front_office_startup_script)
    front_office_startup_script = replace_external_ip(front_office_startup_script,back_office_external_ip) # Comment the line for not replacing the back-office IP in the script

    operation = create_instance(compute, front_office_instance_name, front_office_image_name, startup_script=front_office_startup_script, project_id=project_id, zone=zone, flavor=front_office_flavor, tags=['http-server'])
    wait_for_operation(compute, project_id, zone, operation['name'])
    instantiated_instances.append(front_office_instance_name)

    print("Front office instance creation ready !\n")

    print("Auto deployement ready!\n")

    # Instances deletion
    if input("Press [d] to delete all instantiated instances : ") == 'd':
        for instance in instantiated_instances:
            operation = delete_instances(compute, instance, project_id=project_id, zone=zone)
            wait_for_operation(compute, project_id, zone, operation['name'])
        print("Instances deleted !")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--project_id', default='cloudsys-290308', help='Your Google Cloud project ID.')
    parser.add_argument('--zone',default='europe-west6-a',help='Compute Engine zone to deploy to.')
    parser.add_argument('--json_credentials', help='Json file contain the credential to connect to Google Account. If nothing is specified, the script considers that the connection is made automatically via the google cloud SDK.')

    parser.add_argument('--database_instance_name', default='auto-deploy-database', help='Database instance name.')
    parser.add_argument('--back_office_instance_name', default='auto-deploy-backoffice', help='Back office instance name.')
    parser.add_argument('--front_office_instance_name', default='auto-deploy-frontoffice', help='Front office instance name.')

    parser.add_argument('--database_image_name', default='image-database', help='Database image name.')
    parser.add_argument('--back_office_image_name', default='image-backoffice', help='Back office image name.')
    parser.add_argument('--front_office_image_name', default='image-frontoffice', help='Front office image name.')

    parser.add_argument('--database_flavor', default='e2-micro', help='Database instance flavor.')
    parser.add_argument('--back_office_flavor', default='e2-medium', help='Back office instance flavor.')
    parser.add_argument('--front_office_flavor', default='e2-micro', help='Front office instance flavor.')

    parser.add_argument('--database_startup_script', default='', help='Database startup script.')
    parser.add_argument('--back_office_startup_script', default='backoffice_script.sh', help='Back office startup script.')
    parser.add_argument('--front_office_startup_script', default='frontoffice_script.sh', help='Front office startup script.')

    parser.add_argument('--database_internal_ip', default='10.172.0.3', help='Database internal static IP.')
    parser.add_argument('--back_office_external_ip', default='35.216.163.54', help='Back office external static IP. ')

    args = parser.parse_args()

    main(args.project_id, 
    args.zone, 
    args.json_credentials,
    args.database_instance_name,
    args.back_office_instance_name,
    args.front_office_instance_name,
    args.database_image_name,
    args.back_office_image_name,
    args.front_office_image_name,
    args.database_flavor,
    args.back_office_flavor,
    args.front_office_flavor,
    args.database_startup_script,
    args.back_office_startup_script,
    args.front_office_startup_script,
    args.database_internal_ip,
    args.back_office_external_ip)