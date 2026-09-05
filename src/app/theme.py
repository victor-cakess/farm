"""Chart palette and shared Altair styling.

Validated for contrast and colour-vision separation against the light surface the app pins
itself to in .streamlit/config.toml.
"""

SURFACE = "#fcfcfb"
SERIES_1 = "#2a78d6"  # blue
SERIES_2 = "#eb6834"  # orange
CRITICAL = "#d03b3b"  # status: frost
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
TITLE = "#52514e"

CHART_HEIGHT = 260


def configure(chart):
    """Recessive grid and axes. Works on a single chart or a concatenation."""
    return chart.configure_axis(
        gridColor=GRID,
        domainColor=AXIS,
        tickColor=AXIS,
        labelColor=MUTED,
        titleColor=TITLE,
    ).configure_view(strokeWidth=0)


def base(chart, height=CHART_HEIGHT):
    """A single chart at the standard height, styled."""
    return configure(chart.properties(height=height))
