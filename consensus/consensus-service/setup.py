import os
from setuptools import setup, find_packages

CURPATH = os.path.dirname(os.path.realpath(__file__))

def get_requirements():
    req_file = os.path.join(CURPATH, "requirements.txt")
    with open(req_file) as f:
        return [
            x.strip('\n')
            for x in f.readlines()
            if x and x[0] != '#'
        ]

version_file = os.path.join(CURPATH, "..", "..", "version.txt")
with open(version_file) as f:
    version = f.read().strip()

package_name = 'consensus-service'
description = 'Panoramix negotiation and consensus service'

setup(
    name=package_name,
    version=version,
    license='Affero GPL v3',
    author='GRNET S.A.',
    author_email='panoramix@dev.grnet.gr',
    description=description,
    packages=find_packages(),
    install_requires=get_requirements()
)
