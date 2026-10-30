from app.asr.device import resolve_device


def test_resolve_device_cpu_forced(monkeypatch):
    monkeypatch.setenv("NORTHLINE_DEVICE", "cpu")
    cfg = resolve_device()
    assert cfg.device == "cpu"
    assert cfg.backend == "ctranslate2"
