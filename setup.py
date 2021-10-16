from setuptools import setup

with open("README.md", "rb") as f:
    long_descr = f.read().decode("utf-8")

setup(
    license="GPLv3",
    name="gwatson",
    version="0.0.1",
    py_modules=["gwatson"],
    long_description=long_descr,
    long_description_content_type="text/markdown",
    description="A GUI wrapper for watson.",
    entry_points={"console_scripts": ['gwatson = gwatson:main']},
    setup_requires=['setuptools>=18.0'],
    install_requires=["pyqt5", "click==7.1.2", "td-watson"],
)