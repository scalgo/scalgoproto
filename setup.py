from setuptools import setup, find_packages


with open("README.md") as fp:
    DESCRIPTION = fp.read()


headline = DESCRIPTION.split("\n", 1)[0].rstrip(".")


setup(
    name="scalgoprotoc",
    version="0.1",
    description=headline,
    long_description=DESCRIPTION,
    author="https://github.com/Mortal",
    url="https://github.com/Mortal/terrastream-scripts",
    packages=["", "scalgoprotoc"],
    package_dir={"scalgoprotoc": "scalgoprotoc", "": "lib/python"},
    include_package_data=True,
    license="MIT",
    entry_points={"console_scripts": ["scalgoprotoc = scalgoprotoc.__main__:main"]},
    classifiers=[
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ],
)
