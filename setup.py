from setuptools import setup, find_packages

# Read requirements.txt
def read_requirements():
    with open('requirements.txt', 'r') as f:
        requirements = []
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if line and not line.startswith('#'):
                requirements.append(line)
        return requirements

setup(
    name='pincrawl',
    version='0.1.0',
    description='A project for scraping and matching products/ads',
    author='pitpit',
    packages=find_packages(),
    install_requires=read_requirements(),
    entry_points={
        'console_scripts': [
            'pincrawl=pincrawl.cli:main',
        ],
    },
    include_package_data=True,
    python_requires='>=3.7',
)
