from __future__ import annotations

import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
import shutil

from app import config as config_module


class ConfigResolutionTest(unittest.TestCase):
    def test_resolve_korean_law_mcp_dir_falls_back_to_home_downloads_build(self) -> None:
        temp_root = Path(__file__).resolve().parent / ".tmp"
        temp_root.mkdir(exist_ok=True)
        temp_path = temp_root / f"config-test-{uuid.uuid4().hex}"
        fake_home = temp_path / "home"
        built_repo = fake_home / "Downloads" / "korean-law-mcp-main"

        try:
            (built_repo / "build" / "lib").mkdir(parents=True, exist_ok=True)
            (built_repo / "build" / "lib" / "api-client.js").write_text("// test", encoding="utf-8")

            missing_configured = temp_path / "missing-korean-law-mcp"

            with patch.object(config_module, "BASE_DIR", temp_path / "repo"), patch("app.config.Path.home", return_value=fake_home):
                resolved = config_module._resolve_korean_law_mcp_dir(str(missing_configured))

            self.assertEqual(resolved, built_repo.resolve())
        finally:
            shutil.rmtree(temp_path, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
