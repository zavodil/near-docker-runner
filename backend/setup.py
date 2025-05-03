from setuptools import setup, find_packages

setup(
    name="ai-agent-backend",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi==0.103.1",
        "uvicorn==0.23.2",
        "pydantic==2.3.0",
        "openai==1.2.0",
        "httpx==0.27.2",
        "python-dotenv==1.0.0",
        "python-multipart==0.0.6",
        "docker==6.1.3",
    ],
    extras_require={
        "dev": [
            "black==23.1.0",
            "isort==5.12.0",
            "mypy==1.1.1",
            "pytest==7.3.1",
            "pytest-cov==4.1.0",
        ],
    },
    python_requires=">=3.9",
)