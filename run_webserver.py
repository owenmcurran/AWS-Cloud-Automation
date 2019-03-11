import time
import boto3
import os
from botocore.exceptions import ClientError
import subprocess
import json

ec2_resource = boto3.resource('ec2')
ec2_client = boto3.client('ec2')
s3_resource = boto3.resource('s3')
s3_client = boto3.client('s3')

created_buckets = []
created_instances = []
created_sgs = []
created_kps = []

current_kp = ''

user_data = """#!/bin/bash
yum update -y 
yum install httpd -y 
sytemctl enable httpd
systemctl start httpd
sudo mkdir /var/www/html/efs-mount-point
sudo mount -t efs fs-114a21d9:/ /var/www/html/efs-mount-point """

def generate_key_pair(kp_name):
    kp_name_extension = str(kp_name + '.pem')
    outfile = open(kp_name_extension,'w')
    key_pair = ec2_resource.create_key_pair(KeyName=kp_name)
    KeyPairOut = str(key_pair.key_material)
    outfile.write(KeyPairOut)

    os.chmod(kp_name_extension, 0o400)
    current_kp = kp_name + '.pem'
    print('Key pair: ' + current_kp + ', created successfully')
    created_kps.append(kp_name)
    return current_kp

def check_if_kp_exists(kp_name):
    kp_exists = False
    kp_list = ec2_resource.key_pairs.all()
    for kp in kp_list:
        if kp.name == kp_name:
            kp_exists = True
    return kp_exists

def create_new_security_group_and_rule(sg_name):
    new_security_group = ec2_resource.create_security_group(
        Description='ACS Assignment 1 Security Group',
        GroupName=sg_name
    )
    ec2_client.authorize_security_group_ingress(
        GroupName=sg_name,
        IpPermissions=[
            {
            'FromPort' : 80,
            'ToPort' : 80,
            'IpProtocol' : 'TCP',
            'IpRanges' : [
                {
                    'CidrIp' : '0.0.0.0/0'
                }
            ]},
            {
            'FromPort' : 22,
            'ToPort' : 22,
            'IpProtocol' : 'TCP',
            'IpRanges' : [
                {
                    'CidrIp' : '0.0.0.0/0'
                }
            ]
            }]
    ) 
    print(sg_name + ' created successfully.')
    created_sgs.append(new_security_group.id)
    return str(new_security_group.id)

def check_if_sg_exists(sg_name):
    sq_exists = False
    sg_list = ec2_client.describe_security_groups()['SecurityGroups']
    for sg in sg_list:
        if sg['GroupName'] == sg_name:
            sg_exists = True
    return sg_exists

def return_sg_by_name(sg_name):
    sg_id = ''
    for sg in ec2_client.describe_security_groups()['SecurityGroups']:
        if sg['GroupName'] == sg_name:
            sg_id = sg['GroupId']
    return sg_id

def create_new_instance():
    kp_exists = False
    sg_exists = False
    while kp_exists == False:
        print('1. Create a new key pair.')
        print('2. Use an existing key pair.')
        selection = input('Please select: ')
        if selection == '1':
            kp_name = input('Please provide a name to identify your new key pair: ')
            current_kp = generate_key_pair(kp_name)
            time.sleep(3)
            kp_exists = check_if_kp_exists(kp_name)
            if kp_exists == False:
                print('Something went wrong, please try creating your key pair again')
            else:
                print('New key pair, ' + kp_name + ' created successfully')
                created_kps.append(kp_name)

        elif selection == '2':
            print('List of existing key pairs: ')
            for kp in ec2_resource.key_pairs.all():
                print(kp.name)
            print('')
            kp_name = input('Please provide the name of your key pair (Excluding the .pem extension): ')
            kp_exists = check_if_kp_exists(kp_name)
            if  kp_exists == False:
                print('Key pair, ' + kp_name + ' does not exist. Please check the spelling or create a new key pair.')
            else:
                current_kp = str(kp_name + '.pem')

    while sg_exists == False:
        print('')
        print('1. Create a new security group.')
        print('2. Use an existing security group.')
        selection = input('Please select: ')
        if selection == '1':
            sg_name = input('Please provide a name to identify your new security group by: ')
            create_new_security_group_and_rule(sg_name)
            time.sleep(3)
            sg_exists = check_if_sg_exists(sg_name)
            if sg_exists == False:
                print('Something went wrong when creating your security group, please try again or select an existing one.')

        if selection == '2':
            print()
            for sg in ec2_client.describe_security_groups()['SecurityGroups']:
                print(sg['GroupName'])
            print()
            sg_name = input('Please provide the name of your existing security group: ')
            sg_exists = check_if_sg_exists(sg_name)
            if sg_exists == False:
                print('Security group, ' + sg_name + ' does not exist. Please check the spelling or create a security group.')


    sg_id = return_sg_by_name(sg_name)
    print()
    instance_name = input('Would you like to name your new instance? Leave blank to leave as the default: ')
    if instance_name == '':
        instance_name = 'WebServer'
    
    instance = ec2_resource.create_instances(
        ImageId='ami-02a39bdb8e8ee056a',
        MinCount=1,
        MaxCount=1,
        SecurityGroupIds=[sg_id],
        KeyName=kp_name,
        UserData=user_data,
        TagSpecifications=[
           {
                'ResourceType': 'instance',
                'Tags': [
                    {
                        'Key': 'Name',
                        'Value': str(instance_name),
                    },
                ]
            },
        ],
        InstanceType='t2.micro')

    print('Waiting until instance is running correctly...')
    instance[0].wait_until_running()
    created_instances.append(instance[0].id)
    print(instance, ' created successfully')
    print('Obtaining Public IP Address')
    instance[0].reload()
    time.sleep(3)
    ip_address = instance[0].public_dns_name
    print(ip_address)

    
    print('Installing python on instance: ' + instance_name)
    subprocess.run('ssh -t -o StrictHostKeyChecking=no -i ' + current_kp + ' ec2-user@'+ ip_address +' sudo yum install python3 -y', check=True, shell=True)
    print('Uploading check_webserver.py file to instance')
    subprocess.run('scp -o StrictHostKeyChecking=no -i ' + current_kp + ' check_webserver.py ec2-user@' +  ip_address  + ':.', check=True, shell=True)
    subprocess.run('ssh -o StrictHostKeyChecking=no -i ' + current_kp + ' ec2-user@' +  ip_address  + ' pwd', check=True, shell=True)
    print('Running check_webserver.py script')
    subprocess.run('ssh -t -o StrictHostKeyChecking=no -i ' + current_kp + ' ec2-user@' +  ip_address  + ' python3 check_webserver.py', check=True, shell=True)
    print('Web Server configured correctly')

    print('Changing the default index page')
    subprocess.run('ssh -i ' + current_kp + ' ec2-user@' + ip_address +' sudo touch /var/www/html/index.html', check=True, shell=True)
    subprocess.run('ssh -i ' + current_kp + ' ec2-user@' + ip_address + ' sudo chmod 777 /var/www/html/index.html', check=True, shell=True)
    subprocess.run('scp -i ' + current_kp + ' index.html ec2-user@' + ip_address + ' :/var/www/html/', check=True, shell=True)

    print('Index page formatted')

def create_bucket():
    print()
    bucket_name = input('What would you like to call your bucket: ')
    try:
        bucket = s3_resource.create_bucket(
            ACL='public-read',
            Bucket=bucket_name,
            CreateBucketConfiguration={'LocationConstraint': 'eu-west-1'})
        bucket.wait_until_exists()
        print("Bucket: " + bucket_name + " created successfully: " + str(bucket))
        created_buckets.append(bucket_name)
    except Exception as error:
        print("Bucket creation unccessful: " + str(error))

def upload_image():
    print()
    for bucket in s3_resource.buckets.all():
        print(bucket.name)
    print()
    bucket_name = input('Which bucket would you like to upload to: ')

    print()
    file = input('Please provide the name of the image you would like to upload: ')

    s3_resource.Object(bucket_name, file).put(
        ACL='public-read', 
        ContentType='image/jpeg',
        Body=open(file, 'rb')
        )
    print(file + ' uploaded to ' + bucket_name + ' successfully')

def stop_all_instances():
    instances = ec2_resource.instances.filter(
    Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])
    for instance in instances:
        print('Stopping instance: ' + instance.id)
        instance.stop()

def delete_key_pairs():
    if created_kps: 
        for key in created_kps:
            response = ec2_client.delete_key_pair(
                KeyName=key)
            print(key + ' deleted successfully')
    else:
        print('No key pairs created in this session.')

def delete_sgs():
    if created_sgs:
        for sg in created_sgs:
            response = ec2_client.delete_security_group(
                GroupId=sg)
            print( sg + ' deleted successfully')
        else:
            print('No security groups created in this session.')

def delete_instances():
    if created_instances:
        for instance in created_instances:
            ec2_client.terminate_instances(
                InstanceIds=[instance])
            print(instance + ' deleted successfully')
        else: 
            print('No instandes created in this session are still running.')

def delete_buckets():
    if created_buckets:
        for bucket_name in created_buckets:
            bucketObj = s3_resource.Bucket(bucket_name)
            for element in bucketObj.objects.all():
                element.delete()
            bucketObj.delete()
            print(bucket_name + ' and its contents deleted successful')

def delete_all():
    delete_key_pairs()
    delete_sgs()
    delete_instances()
    delete_buckets()


def menu_delete():
    menu_delete = {}
    print('Please select which type of object you would like to delete: ')
    menu_delete['1'] =  'All key pairs created in this session.'
    menu_delete['2'] =  'All security groups created in this session'
    menu_delete['3'] =  'All instances created in this session'
    menu_delete['4'] =  'All buckets and their contents created in this instance'
    menu_delete['5'] =  'All of the above.'
    menu_delete['0'] =  'Cancel'
    while True: 
        options = menu_delete.keys()
        options = sorted(options)
        for entry in options: 
            print (entry, menu_delete[entry])

        print('')
        selection = input("Please Select: ") 

        print(created_buckets, created_instances, created_kps, created_sgs)
        if selection == '1': 
            delete_key_pairs()
        elif selection == '2': 
            delete_sgs()
        elif selection == '3':
            delete_instances()
        elif selection == '4':
            delete_buckets()
        elif selection == '5':
            delete_all()
        
        elif selection == '0': 
            break
        else: 
            print("Unknown Option Selected!") 

def menu():
    menu = {}
    menu['1']="Create an instance." 
    menu['2']="Stop all instances."
    menu['3']="Create a bucket."
    menu['4']="Upload an image to bucket"
    menu['5']="Delete an element you have created."
    menu['0']="Exit"
    while True: 
        options=menu.keys()
        options = sorted(options)
        for entry in options: 
            print (entry, menu[entry])

        print('')
        selection = input("Please Select: ") 

        if selection == '1': 
            create_new_instance()
        elif selection == '2': 
            stop_all_instances()
        elif selection == '3':
            create_bucket()
        elif selection == '4':
            upload_image()
        elif selection == '5':
            menu_delete()
        
        elif selection == '0': 
            stop_all_instances()
            break
        else: 
            print("Unknown Option Selected!") 

def main():
    menu()

if __name__ == "__main__":
  main()