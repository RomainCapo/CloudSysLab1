import argparse
import os

import boto3
from botocore.exceptions import ClientError

CONFIG = {
    'AWS_SRV_PK': None,
    'AWS_SRV_SK': None,
    'INSTANCES' : [
        {
            'AMI_ID': 'ami-0b775d5ae83fad744',
            'FLAVOR': 't2.micro',
            'MAX_COUNT': 1,
            'MIN_COUNT': 1,
            'NAME': 'DB',
            'SEC_GROUP_ID': 'sg-00d650c29f8e186f4',
            'START_UP_SCRIPT': None
        },
        {
            'AMI_ID': 'ami-0b1a175f158150969',
            'FLAVOR': 't2.micro',
            'MAX_COUNT': 1,
            'MIN_COUNT': 1,
            'NAME': 'BACKEND',
            'SEC_GROUP_ID': 'sg-0e53f67d06722a274',
            'START_UP_SCRIPT': 'backend_start_up.sh'
        },
        {
            'AMI_ID': 'ami-0ae068d7bfa591ae2',
            'FLAVOR': 't2.micro',
            'MAX_COUNT': 1,
            'MIN_COUNT': 1,
            'NAME': 'FRONTEND',
            'SEC_GROUP_ID': 'sg-03e940634544e2772',
            'START_UP_SCRIPT': 'frontend_start_up.sh'
        }
    ],
    'REGION': 'us-east-1',
    'VPC_ID': 'vpc-9e45bfe3'
}

def configure_instances(all_instances):
    ssm_client = boto3.client(
        'ssm',
        region_name=CONFIG['REGION']
    )
    instance_db = all_instances['DB'][0]
    instance_backend = all_instances['BACKEND'][0]
    instance_frontend = all_instances['FRONTEND'][0]
    instance_backend.reload()
    instance_frontend.reload()

    ip_priv_db = instance_db.private_ip_address
    cmd = f"sed -i 's/^DB_HOST.*$/DB_HOST={ip_priv_db}/' /var/www/html/laravel-realworld-example-app/.env"
    send_cmd([cmd], instance_backend.instance_id, ssm_client)
    
    ip_pub_frontend = instance_frontend.public_ip_address
    cmd = f"sed -i 's/^CORS.*$/CORS_ALLOWED_ORIGINS=http:\/\/{ip_pub_frontend}/' /var/www/html/laravel-realworld-example-app/.env"
    send_cmd([cmd], instance_backend.instance_id, ssm_client)

    commands = [
        "composer install -d /var/www/html/laravel-realworld-example-app --ignore-platform-reqs",
        "php /var/www/html/laravel-realworld-example-app/artisan key:generate",
        "php /var/www/html/laravel-realworld-example-app/artisan jwt:generate",
        "php /var/www/html/laravel-realworld-example-app/artisan migrate --force",
        "php /var/www/html/laravel-realworld-example-app/artisan db:seed --force",
        "php /var/www/html/laravel-realworld-example-app/artisan config:clear",
        "composer -d /var/www/html/laravel-realworld-example-app dump-autoload"
    ]
    send_cmd(commands, instance_backend.instance_id, ssm_client)
    
    ip_pub_backend = instance_backend.public_ip_address
    cmd = f"""sed -i 's/^export const.*$/export const API_URL = "http:\/\/{ip_pub_backend}\/api";/' /home/ubuntu/vue-realworld-example-app/src/common/config.js"""
    send_cmd([cmd], instance_frontend.instance_id, ssm_client)

    commands = ["sudo yarnpkg --cwd /home/ubuntu/vue-realworld-example-app install", "sudo yarnpkg --cwd /home/ubuntu/vue-realworld-example-app serve"]
    send_cmd(commands, instance_frontend.instance_id, ssm_client)


def launch_instances(ec2, client):
    print('Lauching instances')

    all_instances = {}

    for instance in CONFIG['INSTANCES']:
        print(instance['NAME'])

        startup_script = ''
        if instance['START_UP_SCRIPT'] is not None : 
            startup_script = open(instance['START_UP_SCRIPT'], 'r').read()

        try:
            instances = ec2.create_instances(
                IamInstanceProfile={
                    'Name': 'AmazonSSMRoleForInstancesQuickSetup'
                },
                ImageId=instance['AMI_ID'],
                InstanceType=instance['FLAVOR'],
                MinCount=instance['MIN_COUNT'],
                MaxCount=instance['MAX_COUNT'],
                SecurityGroupIds=[instance['SEC_GROUP_ID']],
                UserData=startup_script
            )

            instances[0].wait_until_running()

            waiter = client.get_waiter('instance_status_ok')
            waiter.wait(InstanceIds=[instances[0].instance_id])
            
            all_instances[instance['NAME']] = instances
        except ClientError as ce:
            print(f'ERROR : {ce}')

    return all_instances


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('--aws_srv_pk', help='Your AWS server public key.', required=True)
    parser.add_argument('--aws_srv_sk', help='Your AWS server secret key.', required=True)

    parser.add_argument(
        '--flavor_backend',
        default=CONFIG['INSTANCES'][0]['FLAVOR'],
        help='The backend VM flavor'
    )
    parser.add_argument(
        '--flavor_db',
        default=CONFIG['INSTANCES'][1]['FLAVOR'],
        help='The database VM flavor'
    )
    parser.add_argument(
        '--flavor_frontend',
        default=CONFIG['INSTANCES'][2]['FLAVOR'],
        help='The frontend VM flavor'
    )

    parser.add_argument(
        '--min_count_backend',
        default=CONFIG['INSTANCES'][0]['MIN_COUNT'],
        help='The backend min count of instances'
    )
    parser.add_argument(
        '--min_count_db',
        default=CONFIG['INSTANCES'][1]['MIN_COUNT'],
        help='The db min count of instances'
    )
    parser.add_argument(
        '--min_count_frontend',
        default=CONFIG['INSTANCES'][2]['MIN_COUNT'],
        help='The frontend min count of instances'
    )

    parser.add_argument(
        '--max_count_backend',
        default=CONFIG['INSTANCES'][0]['MAX_COUNT'],
        help='The backend max count of instances'
    )
    parser.add_argument(
        '--max_count_db',
        default=CONFIG['INSTANCES'][1]['MAX_COUNT'],
        help='The db max count of instances'
    )
    parser.add_argument(
        '--max_count_frontend',
        default=CONFIG['INSTANCES'][2]['MAX_COUNT'],
        help='The frontend max count of instances'
    )

    parser.add_argument(
        '--start_up_script_path_backend',
        default=CONFIG['INSTANCES'][0]['START_UP_SCRIPT'],
        help='The backend instance start up script path'
    )
    parser.add_argument(
        '--start_up_script_path_db',
        default=CONFIG['INSTANCES'][1]['START_UP_SCRIPT'],
        help='The db instance start up script path'
    )
    parser.add_argument(
        '--start_up_script_path_frontend',
        default=CONFIG['INSTANCES'][2]['START_UP_SCRIPT'],
        help='The frontend instance start up script path'
    )

    args = parser.parse_args()

    CONFIG['AWS_SRV_PK'] = args.aws_srv_pk
    CONFIG['AWS_SRV_SK'] = args.aws_srv_sk

    CONFIG['INSTANCES'][0]['FLAVOR'] = args.flavor_backend
    CONFIG['INSTANCES'][1]['FLAVOR'] = args.flavor_db
    CONFIG['INSTANCES'][2]['FLAVOR'] = args.flavor_frontend

    CONFIG['INSTANCES'][0]['MIN_COUNT'] = args.min_count_backend
    CONFIG['INSTANCES'][1]['MIN_COUNT'] = args.min_count_db
    CONFIG['INSTANCES'][2]['MIN_COUNT'] = args.min_count_frontend

    CONFIG['INSTANCES'][0]['MAX_COUNT'] = args.max_count_backend
    CONFIG['INSTANCES'][1]['MAX_COUNT'] = args.max_count_db
    CONFIG['INSTANCES'][2]['MAX_COUNT'] = args.max_count_frontend

    CONFIG['INSTANCES'][0]['START_UP_SCRIPT'] = args.start_up_script_path_backend
    CONFIG['INSTANCES'][1]['START_UP_SCRIPT'] = args.start_up_script_path_db
    CONFIG['INSTANCES'][2]['START_UP_SCRIPT'] = args.start_up_script_path_frontend


def send_cmd(cmd, instance_id, ssm_client):
    print(f'Configuring : {instance_id}')
    print(f'Using command : {cmd}')
    ssm_client.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={'commands': cmd}
    )

def terminate_instances(all_instances):
    print('Terminating instances')

    for instance_name in all_instances:
        instance = all_instances[instance_name][0]
        instance.terminate()


if __name__ == '__main__':
    parse_args()

    ec2 = boto3.resource(
        'ec2',
        region_name=CONFIG['REGION']
    )
    client = boto3.client(
        'ec2',
        region_name=CONFIG['REGION']
    )

    all_instances = launch_instances(ec2, client)
    configure_instances(all_instances)

    if input("Press [d|D] to delete all instances : ") in ['d', 'D']:
        terminate_instances(all_instances)

    