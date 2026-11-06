from __future__ import annotations

from PySide6.QtWidgets import QPushButton

from ecotranscribe.gui.widgets.alerts import Alert


def test_alert_shows_severity_title_and_text(qtbot) -> None:
    alert = Alert("error", "Erreur", "Le fichier est absent.")
    qtbot.addWidget(alert)
    assert alert.property("severity") == "error"
    assert alert.title_label.text() == "Erreur"
    assert alert.text_label.text() == "Le fichier est absent."


def test_alert_detail_is_optional(qtbot) -> None:
    alert = Alert("info", "Information", "Message")
    qtbot.addWidget(alert)
    assert alert.detail_button.isHidden()
    alert.set_detail("Trace technique")
    assert alert.detail_button.isVisibleTo(alert)
    assert "Trace" in alert.detail_view.toPlainText()


def test_alert_accepts_actions(qtbot) -> None:
    alert = Alert("error", "Erreur", "Message")
    qtbot.addWidget(alert)
    button = QPushButton("Retour")
    alert.add_action(button, primary=True)
    assert button.parent() is not None
    assert button.isVisibleTo(alert)
