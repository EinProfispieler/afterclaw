from pathlib import Path

from fcc.security import ensure_under_root, is_lan


def test_is_lan_private_and_public():
    assert is_lan("127.0.0.1")
    assert is_lan("192.168.1.2")
    assert not is_lan("8.8.8.8")


def test_ensure_under_root_ok(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    child = root / "a" / "b"
    child.mkdir(parents=True)
    out = ensure_under_root(root, child)
    assert out == child.resolve()


def test_ensure_under_root_reject(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    outsider = tmp_path / "other"
    outsider.mkdir()
    try:
        ensure_under_root(root, outsider)
        raised = False
    except ValueError:
        raised = True
    assert raised
