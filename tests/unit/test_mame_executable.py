import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from app.mame.executable import MameExecutable

class TestMameExecutable(unittest.TestCase):
    @patch('app.mame.executable.subprocess.run')
    def test_version_detection(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "MAME 0.289 (mame0289-...)\n"
        mock_run.return_value = mock_result

        mame = MameExecutable(Path("dummy/mame.exe"))
        self.assertEqual(mame.version, "0.289")

    @patch('app.mame.executable.subprocess.run')
    def test_version_unknown(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "MAME unknown\n"
        mock_run.return_value = mock_result

        mame = MameExecutable(Path("dummy/mame.exe"))
        self.assertEqual(mame.version, "unknown")