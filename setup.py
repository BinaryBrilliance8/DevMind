"""Include the buildless console in installed wheels."""

from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py


class BuildWithConsole(build_py):
    def run(self):
        super().run()
        self.copy_tree("web", str(Path(self.build_lib) / "devmind" / "web"))


setup(cmdclass={"build_py": BuildWithConsole})
