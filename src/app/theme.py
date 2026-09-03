"""Chart palette. Validated for the light surface the app pins itself to."""

SURFACE = "#fcfcfb"
SERIES_1 = "#2a78d6"  # blue
SERIES_2 = "#eb6834"  # orange
CRITICAL = "#d03b3b"  # status: frost
MUTED = "#898781"
GRID = "#e1e0d9"

CHART_HEIGHT = 260


def base(chart):
    """Recessive grid and axes, consistent height."""
    return (
        chart.properties(height=CHART_HEIGHT)
        .configure_axis(
            gridColor=GRID,
            domainColor="#c3c2b7",
            tickColor="#c3c2b7",
            labelColor=MUTED,
            titleColor="#52514e",
        )
        .configure_view(strokeWidth=0)
    )
