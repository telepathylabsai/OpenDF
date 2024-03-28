from setuptools import setup, find_packages

setup(
    name='opendf',
    version='1.0.0',
    packages=find_packages(),
    install_requires=[
        'graphviz',
        'jsons',
        'sqlalchemy==1.4.40',
        'tqdm',
        'ply',
        'pytest',
        'pyyaml',
        'numpy',
        'spacy'
    ],
    author='Your Name',
    author_email='your.email@example.com',
    description='A description of your package',
    long_description='A longer description of your package',
    long_description_content_type='text/markdown',
    url='https://github.com/your_username/opendf',
    license='',
    classifiers=[
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
)