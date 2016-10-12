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
module: ecr_images_facts
short_description: list images in ecr
description:
    - Lists images in ECR.
version_added: "2.3"
author: Darek Kaczynski (@kaczynskid)
requirements: [ json, boto, botocore, boto3 ]
options:
    repository:
        description:
            - Name of the repository to list images from
        required: true
    tag_status:
        description:
            - Tag status of returned images
        required: false
        choices: ['tagged', 'untagged']
extends_documentation_fragment:
    - aws
    - ec2
'''

EXAMPLES = '''
# Note: These examples do not set authentication details, see the AWS Guide for details.

# Basic listing example
- ecr_images_facts:
    repository: test-repository

# Listing only untagged images
- ecr_images_facts:
    repository: test-repository
    tag_status: "untagged"

'''

RETURN = '''
imageIds:
    description: list of image IDs and their tags
    returned: success
    type: list of complex
    contains:
        imageDigest:
            description: The sha256 digest of the image manifest.
            returned: always
            type: string
        imageTag:
            description: The tag used for the image.
            returned: only when the image is tagged
            type: string
'''

try:
    import boto
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


class EcrImagesManager:
    """Handles ECR Images"""

    def __init__(self, module):
        self.module = module

        try:
            # self.ecs = boto3.client('ecr')
            region, ec2_url, aws_connect_kwargs = get_aws_connection_info(module, boto3=True)
            if not region:
                module.fail_json(msg="Region must be specified as a parameter, in EC2_REGION or "
                                     "AWS_REGION environment variables or in boto configuration file")
            self.ecr = boto3_conn(module, conn_type='client', resource='ecr', region=region, endpoint=ec2_url, **aws_connect_kwargs)
        except boto.exception.NoAuthHandlerFound, e:
            self.module.fail_json(msg="Can't authorize connection - " + str(e))

    def list_images(self, repository, tag_status):
        fn_args = dict()

        fn_args['repositoryName'] = repository

        if tag_status:
            fn_args['filter'] = dict(tagStatus=tag_status.upper())

        image_ids = list()
        paginator = self.ecr.get_paginator('list_images')
        for page in paginator.paginate(**fn_args):
            image_ids += page.get('imageIds', [])

        return dict(image_ids=image_ids)


def main():

    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(
        repository=dict(required=True, type='str'),
        tag_status=dict(required=False, choices=['tagged', 'untagged'])
    ))

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)

    if not HAS_BOTO:
        module.fail_json(msg='boto is required.')

    if not HAS_BOTO3:
        module.fail_json(msg='boto3 is required.')

    images_mgr = EcrImagesManager(module)
    ecr_facts = images_mgr.list_images(module.params['repository'], module.params['tag_status'])

    ecr_facts_result = dict(changed=False, ansible_facts=ecr_facts)
    module.exit_json(**ecr_facts_result)

from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

if __name__ == '__main__':
    main()
