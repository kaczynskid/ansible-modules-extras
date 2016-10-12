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
module: ecr_images
short_description: handles images in ecr
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
    image_ids:
        description:
            - List of image ids to operate on
        required: true
    state:
        description:
            - Expected status of images
        required: true
        choices: ['absent']
extends_documentation_fragment:
    - aws
    - ec2
'''

EXAMPLES = '''
# Note: These examples do not set authentication details, see the AWS Guide for details.

# Deleting images
- ecr_images_facts:
    repository: test-repository
    image_ids:
        - { imageDigest: sha256:71629ea6f13308e053b6a98792cd7dabfa409e7d81a646370f3a053c1ca678b0 }
        - { imageTag: 0.0.1 }
        - { imageDigest: sha256:87249e43c32a8dd804aa93f8557e7669665c1feffb2c663d9563d2642393b7f2, imageTag: 0.0.2 }
    state: absent
'''

RETURN = '''
imageIds:
    description: list of deleted image IDs and their tags
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
failures:
    description: list of image IDs and their tags that the module failed to delete
    returned: inn case of failures
    type: list of complex
    contains:
        imageId:
            description: the image ID that failed
            returned: always
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
        failureCode:
            description: The code associated with the failure. Valid values are 'InvalidImageDigest', 'InvalidImageTag',
                'ImageTagDoesNotMatchDigest', 'ImageNotFound', 'MissingDigestAndTag'.
            returned: always
            type: string
        failureReason:
            description: The reason for the failure.
            returned: always
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

    def delete_images(self, repository, image_ids):
        fn_args = dict()

        fn_args['repositoryName'] = repository
        fn_args['imageIds'] = image_ids

        response = self.ecr.batch_delete_image(**fn_args)

        return dict(image_ids=response.get('imageIds'), failures=response.get('failures'))


def main():

    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(
        repository=dict(required=True, type='str'),
        image_ids=dict(required=True, type='list'),
        state=dict(required=True, choices=['absent'])
    ))

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)

    if not HAS_BOTO:
        module.fail_json(msg='boto is required.')

    if not HAS_BOTO3:
        module.fail_json(msg='boto3 is required.')

    ecr_facts = dict()
    changed = False

    images_mgr = EcrImagesManager(module)

    if module.params['state'] == 'absent':
        ecr_facts = images_mgr.delete_images(module.params['repository'], module.params['image_ids'])
        changed = True if ecr_facts.get('imageIds') else False

    ecr_facts_result = dict(changed=changed, ansible_facts=ecr_facts)
    module.exit_json(**ecr_facts_result)


from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

if __name__ == '__main__':
    main()

