from setuptools import setup

setup(
    name="gif2ascii",
    version="1.2.0",
    description="Unified GIF to ASCII converter, interactive TUI, preset & library manager, and terminal player.",
    py_modules=["utils", "presets", "tui", "cli", "library", "gif2ascii", "ascii_player"],
    install_requires=["Pillow>=9.0.0"],
    entry_points={
        "console_scripts": [
            "gif2ascii=cli:main",
            "gif2ascii-player=ascii_player:main"
        ]
    },
    python_requires=">=3.8",
)
