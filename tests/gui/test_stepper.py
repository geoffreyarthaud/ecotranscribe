from __future__ import annotations

from ecotranscribe.gui.widgets.stepper import Stepper


def test_stepper_has_four_steps_and_current_state(qtbot) -> None:
    stepper = Stepper()
    qtbot.addWidget(stepper)
    assert stepper.STEPS == ("Fichier", "Prompt", "Réglages", "Transcription")
    stepper.set_current(1)
    assert stepper.current == 1
    assert "Étape 2 sur 4" in stepper.accessibleName()
    assert stepper._numbers[0].property("stepNumber") == "done"
    assert stepper._numbers[1].property("stepNumber") == "current"
    assert stepper._numbers[2].property("stepNumber") == "future"
