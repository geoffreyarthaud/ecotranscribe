from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton

from ecotranscribe.gui.widgets.layout import Section, WizardPage


def test_wizard_page_exposes_title_and_actions(qtbot) -> None:
    page = WizardPage("Titre")
    qtbot.addWidget(page)
    assert page.title_label.text() == "Titre"
    primary = QPushButton("Suivant")
    secondary = QPushButton("Retour")
    page.add_primary(primary)
    page.add_secondary(secondary)
    assert primary.isVisibleTo(page)
    assert secondary.isVisibleTo(page)


def test_wizard_page_can_hide_title(qtbot) -> None:
    page = WizardPage("Titre", show_title=False)
    qtbot.addWidget(page)
    assert page.title_label.isHidden()
    assert page.accessibleName() == "Titre"


def test_section_wraps_children(qtbot) -> None:
    section = Section("Section")
    label = QLabel("contenu")
    section.add(label)
    qtbot.addWidget(section)
    assert label.parent() is not None
