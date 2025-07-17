from setuptools import setup, find_packages

setup(
    name="cloudflare-cli",
    version="1.0.0",
    description="CLI tool for managing Cloudflare DNS records",
    author="Your Name",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "click>=8.0.0",
        "requests>=2.25.0",
        "pyyaml>=5.4.0",
        "colorama>=0.4.4",
        "python-dotenv>=0.19.0",
    ],
    entry_points={
        "console_scripts": [
            "cfcli=cfcli.main:cli",
        ],
    },
    python_requires=">=3.6",
)
