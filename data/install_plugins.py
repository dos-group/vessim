#!/usr/bin/env python3
"""
Plugin Dependency Installer for Vessim Central Data API - Fixed version.
"""

import subprocess
import sys
import logging
from pathlib import Path
from typing import List, Set, Dict, Tuple
import tempfile
import platform
import importlib.util
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class PluginDependencyInstaller:
    """Handles installation of plugin dependencies without pkg_resources."""

    def __init__(self, base_path: Path = None, dry_run: bool = False):
        self.base_path = base_path or Path(__file__).parent
        self.plugins_path = self.base_path / "plugins"
        self.dry_run = dry_run
        self.system_info = {
            "python": sys.version,
            "platform": platform.platform(),
            "executable": sys.executable
        }

    def log_system_info(self):
        """Log relevant system information."""
        logger.info("=" * 60)
        logger.info("Plugin Dependency Installer (Fixed Version)")
        logger.info("=" * 60)
        logger.info(f"Python: {self.system_info['python'].split()[0]}")
        logger.info(f"Platform: {self.system_info['platform']}")
        logger.info(f"Base path: {self.base_path}")
        logger.info("-" * 60)

    def find_plugin_requirements(self) -> Dict[str, Path]:
        """Find all requirements.txt files in plugin directories."""
        requirements_files = {}

        if not self.plugins_path.exists():
            logger.warning(f"Plugins directory not found: {self.plugins_path}")
            return requirements_files

        for plugin_dir in sorted(self.plugins_path.iterdir()):
            if not plugin_dir.is_dir() or plugin_dir.name.startswith(("_", ".")):
                continue

            req_file = plugin_dir / "requirements.txt"
            if req_file.exists():
                requirements_files[plugin_dir.name] = req_file

        logger.info(f"Found {len(requirements_files)} plugin(s) with requirements")
        return requirements_files

    def parse_requirements_file(self, file_path: Path) -> List[str]:
        """Parse a requirements.txt file, filtering out invalid entries."""
        requirements = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()

                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue

                    # Filter out pkg-resources and other problematic packages
                    if self._is_problematic_requirement(line):
                        logger.warning(f"Skipping problematic requirement: {line}")
                        continue

                    # Handle inline comments
                    if '#' in line:
                        line = line.split('#')[0].strip()

                    if line:
                        requirements.append(line)

        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")

        return requirements

    def _is_problematic_requirement(self, requirement: str) -> bool:
        """Check if a requirement is known to be problematic."""
        problematic_patterns = [
            r'^pkg-resources',
            r'^pkg_resources',
            r'^setuptools\s*==',  # Avoid pinning setuptools to specific version
            r'^pip\s*==',  # Avoid pinning pip
        ]

        for pattern in problematic_patterns:
            if re.match(pattern, requirement, re.IGNORECASE):
                return True

        return False

    def deduplicate_requirements(self, all_requirements: List[str]) -> Tuple[List[str], Dict[str, List[str]]]:
        """Remove duplicate requirements."""
        # Simple deduplication for now
        unique_reqs = []
        seen = set()

        for req in all_requirements:
            # Extract base package name for comparison
            base_name = self._extract_package_name(req)
            if base_name not in seen:
                seen.add(base_name)
                unique_reqs.append(req)

        # For now, no conflict detection
        conflicts = {}

        return sorted(unique_reqs), conflicts

    def _extract_package_name(self, requirement: str) -> str:
        """Extract the base package name from a requirement string."""
        # Remove version specifiers and extras
        name = requirement.split('>')[0].split('<')[0].split('=')[0].split('~')[0]
        name = name.split('[')[0]  # Remove extras like [dev]
        name = name.strip().lower().replace('-', '_')
        return name

    def check_existing_installation(self, requirements: List[str]) -> Dict[str, bool]:
        """
        Check which requirements are already installed using importlib.
        """
        status = {}

        for req_str in requirements:
            package_name = self._extract_package_name(req_str)

            # Skip Python standard library modules
            if self._is_standard_library(package_name):
                status[req_str] = True
                continue

            # Try to import the package
            if self._can_import_package(package_name):
                status[req_str] = True
                logger.debug(f"Already installed: {req_str}")
            else:
                status[req_str] = False

        installed = sum(1 for v in status.values() if v)
        logger.info(f"Already installed: {installed}/{len(requirements)}")

        return status

    def _is_standard_library(self, package_name: str) -> bool:
        """Check if a package is part of Python standard library."""
        import sys
        return package_name in sys.stdlib_module_names

    def _can_import_package(self, package_name: str) -> bool:
        """Try to import a package to check if it's installed."""
        try:
            # Try different import names
            import_names = [
                package_name,
                package_name.replace('_', '-'),
                package_name.replace('-', '_'),
            ]

            for import_name in import_names:
                spec = importlib.util.find_spec(import_name)
                if spec is not None:
                    return True

            # Try direct import as last resort
            try:
                __import__(package_name)
                return True
            except ImportError:
                return False

        except Exception:
            return False

    def install_requirements(self, requirements: List[str]) -> bool:
        """Install requirements using pip."""
        if not requirements:
            logger.info("No requirements to install")
            return True

        if self.dry_run:
            logger.info("DRY RUN - Would install:")
            for req in requirements:
                logger.info(f"  {req}")
            return True

        # Create temporary requirements file
        with tempfile.NamedTemporaryFile(mode='w', suffix='_requirements.txt',
                                         delete=False, encoding='utf-8') as temp_file:
            temp_file.write('\n'.join(requirements))
            temp_file_path = temp_file.name

        try:
            logger.info(f"Installing {len(requirements)} package(s)...")

            # Build pip command
            cmd = [sys.executable, "-m", "pip", "install"]

            # Add requirements file
            cmd.extend(["-r", temp_file_path])

            # Add upgrade flag to avoid conflicts
            cmd.append("--upgrade")

            # Add quiet flag for cleaner output
            cmd.append("--quiet")

            logger.debug(f"Running: {' '.join(cmd)}")

            # Execute with timeout
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes
            )

            # Clean up temp file
            Path(temp_file_path).unlink()

            if result.returncode == 0:
                logger.info("✅ Installation successful")
                if result.stderr:
                    logger.debug(f"pip stderr: {result.stderr[:200]}")
                return True
            else:
                logger.error("❌ Installation failed")
                if result.stdout:
                    logger.error(f"pip stdout: {result.stdout[:500]}")
                if result.stderr:
                    logger.error(f"pip stderr: {result.stderr[:500]}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("❌ Installation timed out after 5 minutes")
            return False
        except Exception as e:
            logger.error(f"❌ Installation error: {e}")
            # Try to clean up temp file
            try:
                Path(temp_file_path).unlink()
            except:
                pass
            return False

    def run(self) -> bool:
        """Main execution method."""
        self.log_system_info()

        try:
            # Step 1: Find requirements files
            req_files = self.find_plugin_requirements()

            if not req_files:
                logger.info("No plugin requirements found")
                return True

            # Step 2: Parse requirements
            all_requirements = []
            for plugin_name, req_file in req_files.items():
                try:
                    reqs = self.parse_requirements_file(req_file)
                    all_requirements.extend(reqs)
                    logger.info(f"  {plugin_name}: {len(reqs)} requirement(s)")
                except Exception as e:
                    logger.error(f"Failed to parse {req_file}: {e}")

            if not all_requirements:
                logger.info("No valid requirements found")
                return True

            # Step 3: Deduplicate
            unique_reqs, conflicts = self.deduplicate_requirements(all_requirements)

            if conflicts:
                logger.warning(f"Found {len(conflicts)} potential conflict(s)")

            # Step 4: Check existing installation
            installation_status = self.check_existing_installation(unique_reqs)
            new_requirements = [r for r in unique_reqs if not installation_status.get(r, False)]

            if not new_requirements:
                logger.info("✅ All requirements already satisfied")
                return True

            # Step 5: Install missing requirements
            logger.info(f"Need to install {len(new_requirements)} package(s)")

            success = self.install_requirements(new_requirements)

            if success:
                logger.info("=" * 60)
                logger.info("✅ Plugin dependency installation completed")
                logger.info("=" * 60)
            else:
                logger.error("=" * 60)
                logger.error("❌ Installation failed")
                logger.error("=" * 60)
                logger.error("Manual installation commands:")
                for req in new_requirements:
                    logger.error(f"  pip install --upgrade {req}")

            return success

        except KeyboardInterrupt:
            logger.info("\n⚠️ Installation cancelled by user")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}", exc_info=True)
            return False


def main():
    """Command-line interface."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Install plugin dependencies without pkg-resources"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be installed without actually installing"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose/debug logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    installer = PluginDependencyInstaller(dry_run=args.dry_run)
    success = installer.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()