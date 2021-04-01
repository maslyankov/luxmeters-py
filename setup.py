from setuptools import setup, find_packages

with open('requirements.txt', 'r') as f:
    required = f.read().splitlines()

setup(name='luxmeters', version='0.1.0', author='Martin Maslyankov', author_email='m.maslyankov@me.com',
      # packages=find_packages('src'),
      packages=['luxmeters'],
      install_requires=required,
      # scripts=[],
      url='http://pypi.python.org/pypi/luxmeters/',
      license='LICENSE.txt',
      description='A package giving you interface for several luxmeter devices',
      long_description=open('README.txt').read(),
      )
