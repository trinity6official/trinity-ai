from core.android_doctor import AndroidTrinityDoctor


def test_android_doctor_requires_termux_python_llama_and_profile(tmp_path, monkeypatch):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "android_test.yaml").write_text("local_ai: {}")
    monkeypatch.setattr("core.android_doctor.shutil.which", lambda name: f"/bin/{name}" if name in {"python", "llama-server"} else None)
    # Prevent network/config stack from being part of this structural test.
    monkeypatch.setattr("core.android_doctor.build_local_ai_from_environment", lambda env: (_ for _ in ()).throw(RuntimeError("server not started")))
    report = AndroidTrinityDoctor(tmp_path, environ={"PREFIX": "/data/data/com.termux/files/usr"}).run()
    names = {item.name: item for item in report.checks}
    assert names["Termux environment"].ok is True
    assert names["python"].ok is True
    assert names["llama-server"].ok is True
    assert names["Android Trinity profile"].ok is True
    assert names["Memory write"].ok is True
    assert names["termux-tts-speak"].required is False
