"""Citation metadata and the three human-readable formats stay aligned."""
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def test_cff_has_valid_shape_and_real_repository_metadata():
    text = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert "\t" not in text
    assert re.search(r"^cff-version: 1\.2\.0$", text, re.MULTILINE)
    assert re.search(r"^type: software$", text, re.MULTILINE)
    assert 'title: "EP-VISTA: Electric Propulsion for VLEO Integrated System Trade Analysis"' in text
    assert 'family-names: "Ritz"' in text
    assert "email:" not in text
    assert 'version: "V1.0"' in text
    assert 'date-released: "2026-09-01"' in text
    assert 'repository-code: "https://github.com/Ritz1207/EP-VISTA"' in text
    assert "CITATION.md" in text
    assert not re.search(r"^\s*doi:", text, re.MULTILINE)


def test_three_citation_formats_match_cff_metadata():
    text = (ROOT / "CITATION.md").read_text(encoding="utf-8")
    assert all(heading in text for heading in
               ("## BibTeX", "## GB/T 7714—2025", "## MLA"))
    assert "@software{ritz_ep_vista_v1_0" in text
    assert "author  = {Ritz}" in text
    assert "version = {V1.0}" in text
    assert "year    = {2026}" in text
    release_url = "https://github.com/Ritz1207/EP-VISTA/releases/tag/V1.0"
    assert f"url     = {{{release_url}}}" in text
    assert "RITZ. EP-VISTA:" in text and "[CP/OL]. V1.0版. 2026-09-01[引用日期]." in text
    assert "Ritz. *EP-VISTA:" in text and "Version V1.0, 1 Sept. 2026" in text
    assert text.count(release_url) >= 4
    assert "GB/T 7714—2015" in text and "取代" in text
    assert "当前尚未取得DOI" in text
    assert "openstd.samr.gov.cn" in text
    assert "style.mla.org/citing-source-code" in text


def test_citation_entry_points_link_to_human_and_machine_files():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    sources = (ROOT / "docs/DATA_SOURCES.md").read_text(encoding="utf-8")
    for text in (readme, sources):
        assert "CITATION.md" in text
        assert "CITATION.cff" in text
