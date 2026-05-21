from pathlib import Path

from fcc.subtitle_align import build_alignment_plan, simplify_plan


def test_exact_basename_match_no_change(tmp_path: Path):
    root = tmp_path / "storage"
    d = root / "show"
    d.mkdir(parents=True)
    (d / "Episode.S01E02.mkv").write_text("v")
    (d / "Episode.S01E02.srt").write_text("s")
    plan = build_alignment_plan(root, "show", recursive=False)
    assert simplify_plan(plan) == []


def test_token_match_aligns_subtitle(tmp_path: Path):
    root = tmp_path / "storage"
    d = root / "show"
    d.mkdir(parents=True)
    (d / "My.Show.S01E02.1080p.mkv").write_text("v")
    (d / "S01E02.zh.ass").write_text("s")
    plan = build_alignment_plan(root, "show", recursive=False)
    rows = simplify_plan(plan)
    assert len(rows) == 1
    assert rows[0]["old_rel"].endswith("S01E02.zh.ass")
    assert rows[0]["new_rel"].endswith("My.Show.S01E02.1080p.zh.ass")
    assert rows[0]["skip"] is False


def test_ambiguous_token_is_skipped(tmp_path: Path):
    root = tmp_path / "storage"
    d = root / "show"
    d.mkdir(parents=True)
    (d / "A.S01E02.1080p.mkv").write_text("v")
    (d / "B.S01E02.4k.mp4").write_text("v")
    (d / "S01E02.srt").write_text("s")
    plan = build_alignment_plan(root, "show", recursive=False)
    rows = simplify_plan(plan)
    assert len(rows) == 1
    assert rows[0]["skip"] is True
    assert "Multiple videos match" in (rows[0]["error"] or "")


def test_token_match_drops_long_redundant_tail(tmp_path: Path):
    root = tmp_path / "storage"
    d = root / "show"
    d.mkdir(parents=True)
    (d / "Futurama.S04E01.Roswell.That.Ends.Well.DVDRip.x264.mkv").write_text("v")
    (d / "Futurama.S04E01.Roswell.That.Ends.Well.DVDRip.x264.Roswell.That.Ends.Well.720p.DSNP.WEB-DL.AAC2.0.H.264-playWEB_chs.srt").write_text("s")
    rows = simplify_plan(build_alignment_plan(root, "show", recursive=False))
    assert len(rows) == 1
    assert rows[0]["skip"] is False
    assert rows[0]["new_rel"].endswith("Futurama.S04E01.Roswell.That.Ends.Well.DVDRip.x264.srt")


def test_token_match_supports_x_style(tmp_path: Path):
    root = tmp_path / "storage"
    d = root / "show"
    d.mkdir(parents=True)
    (d / "The.Rookie.S08E03.1080p.WEB-DL.mkv").write_text("v")
    (d / "The.Rookie.8x03.eng.srt").write_text("s")
    rows = simplify_plan(build_alignment_plan(root, "show", recursive=False))
    assert len(rows) == 1
    assert rows[0]["skip"] is False
    assert rows[0]["new_rel"].endswith("The.Rookie.S08E03.1080p.WEB-DL.eng.srt")


def test_token_match_supports_3digit_style(tmp_path: Path):
    root = tmp_path / "storage"
    d = root / "show"
    d.mkdir(parents=True)
    (d / "My.Show.S02E13.1080p.mkv").write_text("v")
    (d / "My.Show.213.eng.srt").write_text("s")
    rows = simplify_plan(build_alignment_plan(root, "show", recursive=False))
    assert len(rows) == 1
    assert rows[0]["skip"] is False
    assert rows[0]["new_rel"].endswith("My.Show.S02E13.1080p.eng.srt")


def test_token_match_supports_cn_season_style(tmp_path: Path):
    root = tmp_path / "storage"
    d = root / "show"
    d.mkdir(parents=True)
    (d / "Drama.S01E13.1080p.mkv").write_text("v")
    (d / "剧名.第一季.13.zh.srt").write_text("s")
    rows = simplify_plan(build_alignment_plan(root, "show", recursive=False))
    assert len(rows) == 1
    assert rows[0]["skip"] is False
    assert rows[0]["new_rel"].endswith("Drama.S01E13.1080p.zh.srt")


def test_token_match_supports_season_ep_style(tmp_path: Path):
    root = tmp_path / "storage"
    d = root / "show"
    d.mkdir(parents=True)
    (d / "Numb3rs.S03E01.1080p.mkv").write_text("v")
    (d / "Numb3rs.Season3.EP01.cht.srt").write_text("s")
    rows = simplify_plan(build_alignment_plan(root, "show", recursive=False))
    assert len(rows) == 1
    assert rows[0]["skip"] is False
    assert rows[0]["new_rel"].endswith("Numb3rs.S03E01.1080p.cht.srt")


def test_token_match_supports_season_e_style(tmp_path: Path):
    root = tmp_path / "storage"
    d = root / "show"
    d.mkdir(parents=True)
    (d / "Numb3rs.S03E02.1080p.mkv").write_text("v")
    (d / "Numb3rs.Season3.E02.cht.srt").write_text("s")
    rows = simplify_plan(build_alignment_plan(root, "show", recursive=False))
    assert len(rows) == 1
    assert rows[0]["skip"] is False
    assert rows[0]["new_rel"].endswith("Numb3rs.S03E02.1080p.cht.srt")
