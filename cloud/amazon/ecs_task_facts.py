#!/usr/bin/python
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

DOCUMENTATION = '''
---
module: ecs_task_facts
short_description: list or describe tasks in ecs
notes:
    - for details of the parameters and returns see U(http://boto3.readthedocs.org/en/latest/reference/tasks/ecs.html)
description:
    - Lists or describes tasks in ecs.
version_added: "2.1"
author: Darek Kaczynski (@kaczynskid)
requirements: [ json, boto, botocore, boto3 ]
options:
    details:
        description:
            - Set this to true if you want detailed information about the tasks.
        required: false
        default: 'false'
    cluster:
        description:
            - The short name or ARN of the cluster that hosts the tasks to list.
        required: false
        default: 'default'
    container:
        description:
            -  The container instance ID or ARN of the container instance with which to filter the result.
        required: false
    task:
        description:
            - The task to get details for. Overrides family, service and status when details is true.
        required: false
    family:
        description:
            - The name of the family with which to filter the result.
        required: false
    service:
        description:
            - The service name to find tasks by.
        required: false
    status:
        description:
            - The task status to find tasks by.
        required: false
        choices: ['running', 'pending', 'stopped']
    started_by:
        description:
            - The startedBy value with which to filter result.
        required: false
extends_documentation_fragment:
    - aws
    - ec2
'''

EXAMPLES = '''
# Note: These examples do not set authentication details, see the AWS Guide for details.

# Basic listing example
- ecs_task_facts:
    cluster: test-cluster

# Basic listing example by more detailed criteria
- ecs_task_facts:
    cluster: test-cluster
    family: console-test-task
    service: test-service
    status: running

# Detaled listing example by task ARN
- ecs_task_facts:
    cluster: test-cluster
    task: console-test-task
    details: "true"

'''

RETURN = '''
tasks:
    description: When details is false, returns an array of task ARNs, otherwise an array of complex objects as described below.
    returned: success
    type: list of complex
    contains:
        taskArn:
            description: The Amazon Resource Name (ARN) that identifies the task.
            returned: always
            type: string
        clusterArn:
            description: The Amazon Resource Name (ARN) of the of the cluster that hosts the task.
            returned: only when details is true
            type: string
        taskDefinitionArn:
            description: The Amazon Resource Name (ARN) of the task definition.
            returned: only when details is true
            type: string
        containerInstanceArn:
            description: The Amazon Resource Name (ARN) of the container running the task.
            returned: only when details is true
            type: string
        overrides:
            description: The container overrides set for this task.
            returned: only when details is true
            type: list of complex
        lastStatus:
            description: The last recorded status of the task.
            returned: only when details is true
            type: string
        desiredStatus:
            description: The desired status of the task.
            returned: only when details is true
            type: string
        containers:
            description: The container details.
            returned: only when details is true
            type: list of complex
        startedBy:
            description: The used who started the task.
            returned: only when details is true
            type: string
        stoppedReason:
            description: The reason why the task was stopped.
            returned: only when details is true
            type: string
        createdAt:
            description: The timestamp of when the task was created.
            returned: only when details is true
            type: string
        startedAt:
            description: The timestamp of when the task was started.
            returned: only when details is true
            type: string
        stoppedAt:
            description: The timestamp of when the task was stopped.
            returned: only when details is true
            type: string
'''
try:
    import boto
    import botocore
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

class EcsTaskManager:
    """Handles ECS Tasks"""

    def __init__(self, module):
        self.module = module

        try:
            region, ec2_url, aws_connect_kwargs = get_aws_connection_info(module, boto3=True)
            if not region:
                module.fail_json(msg="Region must be specified as a parameter, in EC2_REGION or AWS_REGION environment variables or in boto configuration file")
            self.ecs = boto3_conn(module, conn_type='client', resource='ecs', region=region, endpoint=ec2_url, **aws_connect_kwargs)
        except boto.exception.NoAuthHandlerFound, e:
            self.module.fail_json(msg="Can't authorize connection - "+str(e))

    def list_tasks(self, cluster, container, family, service, status, started_by):
        fn_args = dict()

        # apply non-exclusive parameters
        if cluster:
            fn_args['cluster'] = cluster
        if container:
            fn_args['containerInstance'] = container
        if started_by:
            fn_args['startedBy'] = started_by

        tasks = None

        # apply exclusive parameters
        if family:
            fn_args['family'] = family
            tasks = self.get_tasks_list(tasks, fn_args)
            del fn_args['family']

        if service:
            fn_args['serviceName'] = service
            tasks = self.get_tasks_list(tasks, fn_args)
            del fn_args['serviceName']

        if status:
            fn_args['desiredStatus'] = status.upper()
            tasks = self.get_tasks_list(tasks, fn_args)
            del fn_args['desiredStatus']

        # no exclusive criteria specified - apply non-exclusive filters
        if tasks is None:
            tasks = self.get_tasks_list(tasks, fn_args)

        return dict(tasks = list(tasks))

    def get_tasks_list(self, tasks, fn_args):
        try:
            listed = set()
            paginator = self.ecs.get_paginator('list_tasks')
            for page in paginator.paginate(**fn_args):
                listed.update(set(page['taskArns']))

            return listed if tasks is None else tasks.intersection(listed)
        except botocore.exceptions.ClientError:
            return tasks

    def describe_tasks(self, cluster, container, task, family, service, status, started_by):
        fn_args = dict()
        if cluster:
            fn_args['cluster'] = cluster
        if task:
            fn_args['tasks'] = task.split(",")
        else:
            fn_args['tasks'] = self.list_tasks(cluster, container, family, service, status, started_by)['tasks']

        if len(fn_args['tasks']) < 1:
            return dict(tasks = [])

        response = self.ecs.describe_tasks(**fn_args)

        relevant_response = dict(tasks = map(self.jsonize, response['tasks']))
        if 'failures' in response and len(response['failures']) > 0:
            relevant_response['tasks_not_running'] = response['failures']
        return relevant_response

    def jsonize(self, task):
        # some fields are datetime which is not JSON serializable
        # make them strings
        if 'createdAt' in task:
            task['createdAt'] = str(task['createdAt'])
        if 'startedAt' in task:
            task['startedAt'] = str(task['startedAt'])
        if 'stoppedAt' in task:
            task['stoppedAt'] = str(task['stoppedAt'])
        return task

def main():

    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(
        details=dict(required=False, type='bool'),
        cluster=dict(required=False, type='str'),
        container=dict(required=False, type='str'),
        task=dict(required=False, type='str'),
        family=dict(required=False, type='str'),
        service=dict(required=False, type='str'),
        status=dict(required=False, choices=['running', 'pending', 'stopped']),
        started_by=dict(required=False, type='str')
    ))

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)

    if not HAS_BOTO:
      module.fail_json(msg='boto is required.')

    if not HAS_BOTO3:
      module.fail_json(msg='boto3 is required.')

    show_details = module.params['details']

    task_mgr = EcsTaskManager(module)
    if show_details:
        ecs_facts = task_mgr.describe_tasks(module.params['cluster'], module.params['container'], module.params['task'],
            module.params['family'], module.params['service'], module.params['status'], module.params['started_by'])
    else:
        ecs_facts = task_mgr.list_tasks(module.params['cluster'], module.params['container'],
            module.params['family'], module.params['service'], module.params['status'], module.params['started_by'])

    ecs_facts_result = dict(changed=False, ansible_facts=ecs_facts)
    module.exit_json(**ecs_facts_result)

# import module snippets
from ansible.module_utils.basic import *
from ansible.module_utils.urls import *
from ansible.module_utils.ec2 import *

if __name__ == '__main__':
    main()
