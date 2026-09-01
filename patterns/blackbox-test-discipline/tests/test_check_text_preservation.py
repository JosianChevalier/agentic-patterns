"""Tests outer-loop pour `1-sources/outils/ressources/check_text_preservation.py`.

Le script compare `<slug>/index.md` à son snapshot `<slug>/.extract.md` et
autorise uniquement deux types d'insertions :
- une ligne `![](filename.png)` sans `/` dans le chemin (Embed root),
- un bloc ouvert par `<retranscription>` et fermé par `</retranscription>`
  (contenu libre à l'intérieur, lignes vides incluses).

Toute délétion, modification, ou insertion hors-règle fait échouer le check.
"""
from __future__ import annotations

from pathlib import Path

SLUG = "monslug"
SCRIPT = "ressources/check_text_preservation.py"

EXTRACT_BODY = (
    "# Titre\n"
    "\n"
    "Paragraphe un.\n"
    "Paragraphe deux.\n"
)


def _setup(repo: Path, *, index: str, extract: str | None) -> None:
    """Crée `<repo>/1-sources/1.2-nettoyes/ressources/<SLUG>/{index.md,.extract.md}`.

    Si `extract` est `None`, le snapshot n'est pas créé (cas absent).
    """
    out_dir = repo / "1-sources" / "1.2-nettoyes" / "ressources" / SLUG
    out_dir.mkdir(parents=True)
    (out_dir / "index.md").write_text(index)
    if extract is not None:
        (out_dir / ".extract.md").write_text(extract)


def test_identique(run_script, tmp_repo: Path) -> None:
    _setup(tmp_repo, index=EXTRACT_BODY, extract=EXTRACT_BODY)
    result = run_script(SCRIPT, SLUG, repo=tmp_repo)
    assert result.returncode == 0, result.stderr
    assert f"OK {SLUG}: text preserved" in result.stdout


def test_insertion_embed_racine_ok(run_script, tmp_repo: Path) -> None:
    """Une image embed au niveau racine (chemin sans `/`) est autorisée."""
    index = (
        "# Titre\n"
        "\n"
        "Paragraphe un.\n"
        "\n"
        "![](photo.png)\n"
        "\n"
        "Paragraphe deux.\n"
    )
    _setup(tmp_repo, index=index, extract=EXTRACT_BODY)
    result = run_script(SCRIPT, SLUG, repo=tmp_repo)
    assert result.returncode == 0, result.stderr + result.stdout


def test_insertion_embed_avec_slash_interdite(run_script, tmp_repo: Path) -> None:
    """Une image avec `/` dans le chemin (ex: `_all_pages/x.png`) n'est PAS une
    insertion Embed valide — c'est du contenu Extract, donc soit elle était déjà
    dans le snapshot, soit c'est une insertion interdite."""
    index = (
        "# Titre\n"
        "\n"
        "Paragraphe un.\n"
        "\n"
        "![](_all_pages/slide-1.png)\n"
        "\n"
        "Paragraphe deux.\n"
    )
    _setup(tmp_repo, index=index, extract=EXTRACT_BODY)
    result = run_script(SCRIPT, SLUG, repo=tmp_repo)
    assert result.returncode == 1
    assert "forbidden insertion" in result.stderr


def test_bloc_transcription_ok(run_script, tmp_repo: Path) -> None:
    """Un bloc ouvert par `<retranscription>` et clos par `</retranscription>`
    est autorisé, peu importe le contenu intérieur."""
    index = (
        "# Titre\n"
        "\n"
        "Paragraphe un.\n"
        "\n"
        "<retranscription>\n"
        "- item un\n"
        "- item deux\n"
        "ascii art quelconque\n"
        "</retranscription>\n"
        "\n"
        "Paragraphe deux.\n"
    )
    _setup(tmp_repo, index=index, extract=EXTRACT_BODY)
    result = run_script(SCRIPT, SLUG, repo=tmp_repo)
    assert result.returncode == 0, result.stderr + result.stdout


def test_bloc_transcription_avec_lignes_vides_ok(run_script, tmp_repo: Path) -> None:
    """Lignes vides internes autorisées (la différence-clé vs l'ancien format)."""
    index = (
        "# Titre\n"
        "\n"
        "Paragraphe un.\n"
        "\n"
        "<retranscription>\n"
        "- premier paragraphe\n"
        "\n"
        "| col1 | col2 |\n"
        "|------|------|\n"
        "| a    | b    |\n"
        "\n"
        "```\n"
        "code dans la retranscription\n"
        "```\n"
        "</retranscription>\n"
        "\n"
        "Paragraphe deux.\n"
    )
    _setup(tmp_repo, index=index, extract=EXTRACT_BODY)
    result = run_script(SCRIPT, SLUG, repo=tmp_repo)
    assert result.returncode == 0, result.stderr + result.stdout


def test_bloc_transcription_non_ferme_interdit(run_script, tmp_repo: Path) -> None:
    """Ouvrir `<retranscription>` sans `</retranscription>` doit échouer."""
    index = (
        "# Titre\n"
        "\n"
        "Paragraphe un.\n"
        "\n"
        "<retranscription>\n"
        "- item un\n"
        "Paragraphe deux.\n"
    )
    _setup(tmp_repo, index=index, extract=EXTRACT_BODY)
    result = run_script(SCRIPT, SLUG, repo=tmp_repo)
    assert result.returncode == 1
    assert "unclosed" in result.stderr


def test_deletion_interdite(run_script, tmp_repo: Path) -> None:
    """Supprimer une ligne du snapshot fait échouer."""
    index = (
        "# Titre\n"
        "\n"
        "Paragraphe deux.\n"
    )
    _setup(tmp_repo, index=index, extract=EXTRACT_BODY)
    result = run_script(SCRIPT, SLUG, repo=tmp_repo)
    assert result.returncode == 1
    assert "forbidden delete" in result.stderr
    assert "'Paragraphe un.'" in result.stderr


def test_modification_interdite(run_script, tmp_repo: Path) -> None:
    """Réécrire une ligne du snapshot fait échouer (replace)."""
    index = (
        "# Titre\n"
        "\n"
        "Paragraphe MODIFIE.\n"
        "Paragraphe deux.\n"
    )
    _setup(tmp_repo, index=index, extract=EXTRACT_BODY)
    result = run_script(SCRIPT, SLUG, repo=tmp_repo)
    assert result.returncode == 1
    assert "forbidden replace" in result.stderr
    assert "'Paragraphe un.'" in result.stderr
    assert "'Paragraphe MODIFIE.'" in result.stderr


def test_insertion_prose_libre_interdite(run_script, tmp_repo: Path) -> None:
    """Une ligne de prose insérée hors transcription / hors embed est interdite."""
    index = (
        "# Titre\n"
        "\n"
        "Paragraphe un.\n"
        "Note ajoutée à la main, non encadrée.\n"
        "Paragraphe deux.\n"
    )
    _setup(tmp_repo, index=index, extract=EXTRACT_BODY)
    result = run_script(SCRIPT, SLUG, repo=tmp_repo)
    assert result.returncode == 1
    assert "forbidden insertion" in result.stderr


def test_snapshot_absent_pointe_vers_snapshot_only(run_script, tmp_repo: Path) -> None:
    _setup(tmp_repo, index=EXTRACT_BODY, extract=None)
    result = run_script(SCRIPT, SLUG, repo=tmp_repo)
    assert result.returncode == 2
    assert "--snapshot-only" in result.stderr
