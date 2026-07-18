from services.tracking_urls import (
    build_tracking_url,
    carrier_display_name,
    is_trackable_shipping_method,
    resolve_carrier,
)


def test_resolve_carrier_from_method():
    assert resolve_carrier("click_post", None) == "japan_post"
    assert resolve_carrier("takkyubin_compact", None) == "yamato"


def test_resolve_carrier_from_carrier_text():
    assert resolve_carrier(None, "ヤマト運輸") == "yamato"
    assert resolve_carrier(None, "日本郵便") == "japan_post"
    assert resolve_carrier(None, "佐川急便") == "sagawa"


def test_build_tracking_url_japan_post():
    url = build_tracking_url(
        "12345678901",
        shipping_method="click_post",
    )
    assert url is not None
    assert "trackings.post.japanpost.jp" in url
    assert "12345678901" in url


def test_build_tracking_url_yamato():
    url = build_tracking_url(
        "999988887777",
        shipping_method="takkyubin_60",
    )
    assert url is not None
    assert "kuronekoyamato" in url
    assert "999988887777" in url


def test_build_tracking_url_empty_number():
    assert build_tracking_url("", shipping_method="click_post") is None


def test_non_trackable_methods():
    assert is_trackable_shipping_method("teikei_post") is False
    assert is_trackable_shipping_method("click_post") is True


def test_carrier_display_name_prefers_admin_input():
    assert carrier_display_name("click_post", "クリックポスト") == "クリックポスト"
    assert carrier_display_name("takkyubin_compact", None) == "ヤマト運輸"
