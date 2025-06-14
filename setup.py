from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="steve-code",
    version="0.1.1",
    author="Steve Code Contributors",
    description="A self-contained AI code assistant CLI tool using AWS Bedrock",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/StoliRocks/steve-code",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "boto3>=1.34.0",
        "prompt_toolkit>=3.0.43",
        "rich>=13.7.0",
        "click>=8.1.7",
        "python-dotenv>=1.0.0",
        "beautifulsoup4>=4.10.0",
        "requests>=2.25.0",
        "Pillow>=9.0.0",
        "pyautogui>=0.9.50",
        "tiktoken>=0.5.0",
        "packaging>=21.0",
    ],
    entry_points={
        "console_scripts": [
            "steve-code=ai_code_assistant.cli:main",
            "sc=ai_code_assistant.cli:main",  # Short alias
        ],
    },
)