"""Render Code 128-B SVG without exposing the encoded credential as text."""

from __future__ import annotations

from html import escape

CODE128_PATTERNS = (
    "212222", "222122", "222221", "121223", "121322", "131222", "122213",
    "122312", "132212", "221213", "221312", "231212", "112232", "122132",
    "122231", "113222", "123122", "123221", "223211", "221132", "221231",
    "213212", "223112", "312131", "311222", "321122", "321221", "312212",
    "322112", "322211", "212123", "212321", "232121", "111323", "131123",
    "131321", "112313", "132113", "132311", "211313", "231113", "231311",
    "112133", "112331", "132131", "113123", "113321", "133121", "313121",
    "211331", "231131", "213113", "213311", "213131", "311123", "311321",
    "331121", "312113", "312311", "332111", "314111", "221411", "431111",
    "111224", "111422", "121124", "121421", "141122", "141221", "112214",
    "112412", "122114", "122411", "142112", "142211", "241211", "221114",
    "413111", "241112", "134111", "111242", "121142", "121241", "114212",
    "124112", "124211", "411212", "421112", "421211", "212141", "214121",
    "412121", "111143", "111341", "131141", "114113", "114311", "411113",
    "411311", "113141", "114131", "311141", "411131", "211412", "211214",
    "211232", "2331112",
)


def render_code128_svg(
    value: str,
    *,
    module_width: int = 2,
    bar_height: int = 64,
    aria_label: str = "物流バーコード",
) -> str:
    if not value or any(ord(char) < 32 or ord(char) > 126 for char in value):
        raise ValueError("Code 128-B supports printable ASCII only")

    start_code = 104
    data_codes = [ord(char) - 32 for char in value]
    checksum = (start_code + sum(code * index for index, code in enumerate(data_codes, 1))) % 103
    codes = [start_code, *data_codes, checksum, 106]
    patterns = [CODE128_PATTERNS[code] for code in codes]

    quiet_modules = 10
    content_modules = sum(sum(int(width) for width in pattern) for pattern in patterns)
    width = (content_modules + quiet_modules * 2) * module_width
    x = quiet_modules * module_width
    bars: list[str] = []
    for pattern in patterns:
        draw_bar = True
        for width_code in pattern:
            segment_width = int(width_code) * module_width
            if draw_bar:
                bars.append(
                    f'<rect x="{x}" y="0" width="{segment_width}" '
                    f'height="{bar_height}" fill="#000"/>'
                )
            x += segment_width
            draw_bar = not draw_bar

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="{escape(aria_label)}" viewBox="0 0 {width} {bar_height}" '
        f'width="{width}" height="{bar_height}" shape-rendering="crispEdges">'
        f'<rect width="{width}" height="{bar_height}" fill="#fff"/>'
        f'{"".join(bars)}</svg>'
    )
