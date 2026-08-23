from pathlib import Path

from training.live_metrics import LiveMetricsWriter
from training.trainer import train


def test_live_metrics_writer(tmp_path):
    w = LiveMetricsWriter(output_dir=tmp_path)
    w.record_episode({"episode": 1, "won": True})
    w.write(status="running", episode=1, total_episodes=10, metrics={"x": 1})
    assert (tmp_path / "live.json").exists()


def test_short_training_run(tmp_path):
    root = Path(__file__).resolve().parent.parent
    result = train(
        episodes=3,
        seed=99,
        config_path=str(root / "configs" / "training_test.yaml"),
        live=False,
        output_dir=tmp_path,
    )
    assert result["episodes"] == 3
    assert (tmp_path / "live.json").exists()
