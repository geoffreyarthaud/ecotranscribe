from __future__ import annotations

from ecotranscribe.gui.app_icon import ICON_SIZES, app_icon, app_icon_pixmap
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


def test_app_icon_embeds_every_size(qtbot) -> None:
    icon = app_icon()
    assert not icon.isNull()
    assert {size.width() for size in icon.availableSizes()} == set(ICON_SIZES)


def test_app_icon_pixmap_is_not_empty(qtbot) -> None:
    pixmap = app_icon_pixmap(32)
    assert not pixmap.isNull()
    assert pixmap.width() > 0 and pixmap.height() > 0
