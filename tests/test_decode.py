from yfphonecam.decode import jpeg_dimensions


def test_invalid_jpeg_has_no_dimensions() -> None:
    assert jpeg_dimensions(b"not a jpeg") is None
