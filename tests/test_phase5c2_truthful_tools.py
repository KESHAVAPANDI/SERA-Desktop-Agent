import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from app.tools.windows.apps import OpenApplicationTool, OpenFolderTool, OpenFileTool


class TestPhase5C2TruthfulTools(unittest.IsolatedAsyncioTestCase):
    """Unit tests verifying computer action truthfulness and failure handling."""

    # 1. Invalid application must return False, never True
    async def test_01_invalid_application_returns_truthful_failure(self):
        tool = OpenApplicationTool()
        res = await tool.execute(application="non_existent_app_xyz_123")
        self.assertFalse(res["success"])
        self.assertFalse(res["verified"])
        self.assertIn("could not be found", res["error"])

    # 2. Known application launches and verifies
    async def test_02_valid_application_launch(self):
        tool = OpenApplicationTool()
        with patch("subprocess.Popen") as mock_popen, patch("psutil.process_iter") as mock_piter:
            mock_proc = MagicMock()
            mock_proc.info = {"name": "notepad.exe"}
            mock_piter.return_value = [mock_proc]

            res = await tool.execute(application="notepad")
            self.assertTrue(res["success"])
            self.assertTrue(res["verified"])

    # 3. Open Folder: non-existent folder must return False
    async def test_03_invalid_folder_returns_truthful_failure(self):
        tool = OpenFolderTool()
        res = await tool.execute(folder_name="enemy_folder_non_existent")
        self.assertFalse(res["success"])
        self.assertFalse(res["verified"])
        self.assertIn("could not be found", res["error"])

    # 4. Open Folder: valid folder succeeds
    async def test_04_valid_folder_success(self):
        tool = OpenFolderTool()
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("os.startfile") as mock_startfile:
                res = await tool.execute(folder_name=temp_dir)
                self.assertTrue(res["success"])
                self.assertTrue(res["verified"])
                self.assertEqual(res["folder_path"], temp_dir)

    # 5. Open File: non-existent file returns False
    async def test_05_invalid_file_returns_truthful_failure(self):
        tool = OpenFileTool()
        res = await tool.execute(file_path="non_existent_document.pdf")
        self.assertFalse(res["success"])
        self.assertFalse(res["verified"])
        self.assertIn("could not be found", res["error"])


if __name__ == "__main__":
    unittest.main()
