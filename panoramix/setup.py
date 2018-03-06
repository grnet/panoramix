from setuptools import setup, find_packages
import os

CURPATH = os.path.dirname(os.path.realpath(__file__))

PACKAGE_NAME = "panoramix"
SHORT_DESCRIPTION = "The Panoramix Project"

version_file = os.path.join(CURPATH, "..", "version.txt")
with open(version_file) as f:
    VERSION = f.read().strip()

PACKAGES_ROOT = '.'
PACKAGES = find_packages(PACKAGES_ROOT)

# Package meta
CLASSIFIERS = []


def read_requirements(filename):
    with open(filename) as f:
        return [
            x.strip('\n')
            for x in f.readlines()
            if x and x[0] != '#'
        ]


def from_file(extra=None):
    suffix = "_%s" % extra if extra else ""
    filename = "requirements%s.txt" % suffix
    return os.path.join(CURPATH, filename)


INSTALL_REQUIRES = read_requirements(from_file())


EXTRAS = ["sphinxmix", "gpg", "zeus"]
EXTRAS_REQUIRES = {extra: read_requirements(from_file(extra))
                   for extra in EXTRAS}

TESTS_REQUIRES = [
]


setup(
    name=PACKAGE_NAME,
    version=VERSION,
    license='Affero GPL v3',
    author='GRNET S.A.',
    author_email='panoramix@dev.grnet.gr',
    description=SHORT_DESCRIPTION,
    classifiers=CLASSIFIERS,
    packages=PACKAGES,
    package_dir={'': PACKAGES_ROOT},
    namespace_packages=['panoramix'],
    zip_safe=False,
    install_requires=INSTALL_REQUIRES,
    extras_require=EXTRAS_REQUIRES,
    tests_require=TESTS_REQUIRES,

    entry_points={
        'console_scripts': [
            'panoramix-wizard = panoramix.wizard:main',
        ],
    },
)
