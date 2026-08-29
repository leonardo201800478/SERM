import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.mame.executable import MameExecutable


class TestMameExecutable(unittest.TestCase):
    @patch('app.mame.executable.subprocess.run')
    def test_version_detection(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "MAME 0.289 (mame0289-...)\n"
        mock_run.return_value = mock_result

        mame = MameExecutable(Path("dummy/mame.exe"))
        with patch.object(Path, "is_file", return_value=True):
            self.assertEqual(mame.version, "0.289")

    @patch('app.mame.executable.subprocess.run')
    def test_version_unknown(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "MAME unknown\n"
        mock_run.return_value = mock_result

        mame = MameExecutable(Path("dummy/mame.exe"))
        with patch.object(Path, "is_file", return_value=True):
            self.assertEqual(mame.version, "unknown")
