from __future__ import annotations

from ecotranscribe.gui.widgets.icons import gear_icon


def test_gear_icon_is_drawn(qtbot) -> None:
    icon = gear_icon()
    assert not icon.isNull()
    pixmap = icon.pixmap(22, 22)
    assert not pixmap.isNull()
    image = pixmap.toImage()
    assert any(
        image.pixelColor(x, y).alpha() > 0
        for x in range(image.width())
        for y in range(image.height())
    )
