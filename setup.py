from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

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
    description="An implementation of the dataflow paradigm for dialogue systems",
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/your_username/opendf',
    license='MIT',
    classifiers=[
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
)