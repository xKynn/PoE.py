from setuptools import setup

with open("README.md") as f:
    desc = f.read()

setup(
    name="PoE.py",
    packages=['poe'],   
    include_package_data=True,
    version="1.5.2a",
    description="A Path of Exile wrapper/lib that supports multitudes of filters to list and render items as PNGs and retreive useful character data.",
    long_description=desc,
    long_description_content_type="text/markdown",    
    author="xKynn",
    author_email="xkynn@github.com",
    url="https://github.com/xKynn/PoE.py",
    classifiers=(
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ),
)
