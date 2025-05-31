from setuptools import setup, find_packages

setup(
    name="anki_ocr",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "genanki",
        "gTTS",
        "Pillow",
        "openai",
        "numpy",
        "python-dotenv",
    ],
    entry_points={
        "console_scripts": [
            "anki-ocr=src.cli.main:main",
        ],
    },
    python_requires=">=3.8",
) 