from pathlib import Path
from unittest.mock import MagicMock

from core.persistence import StatePersistence


def test_state_persistence_saves_consciousness():
    consciousness = MagicMock()
    consciousness.brain_path = Path("trinity_brain.json")
    report = StatePersistence(consciousness).save()
    assert report.success is True
    consciousness.save.assert_called_once()
    assert report.brain_path.endswith("trinity_brain.json")


def test_state_persistence_reports_failure_without_raising():
    consciousness = MagicMock()
    consciousness.save.side_effect = OSError("disk full")
    report = StatePersistence(consciousness).save()
    assert report.success is False
    assert "disk full" in report.error
