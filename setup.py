try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup, find_packages

setup(name='yspecies',
      version='0.2.2',
      py_modules=['yspecies', 'dataset', 'workflow', 'utils', 'partition', "selection", "results", 'tuning', 'model', 'pipelines'],
      packages=find_packages(),
      description='yspecies')