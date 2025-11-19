from setuptools import setup, find_packages

setup(
    name="ddr5-power-tool",
    version="0.1.0",
    description="DDR5/LPDDR5 Power Measurement Tool",
    author="Lucas Song",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "numpy>=1.20.0",
        "matplotlib>=3.3.0",
    ],
    entry_points={
        "console_scripts": [
            "ddr5-power=ddr5_power_tool.cli:main",
        ],
    },
)

