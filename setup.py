"""
setup.py

installation script
"""

from setuptools import setup, find_packages

PACKAGE_NAME = "dkbestball"


def run():
    setup(name=PACKAGE_NAME,
          version="0.1",
          description="python library for connecting to DK bestball leagues",
          author="Eric Truett",
          author_email="eric@erictruett.com",
          license="MIT",
          packages=find_packages(),
          package_data={'dkbestball.data': ['*.json']},
          zip_safe=False
        )


if __name__ == '__main__':
    run()