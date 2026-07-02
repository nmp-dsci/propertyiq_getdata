from io import BytesIO

import pandas as pd

from propertyiq_getdata.rentboard import (
    discover_links,
    normalize_rentboard_frame,
    prefer_monthly_when_available,
    update_rentboard,
)


def test_discover_links_handles_current_monthly_titles():
    html = """
    <a href="/sites/default/files/noindex/2026-06/rentalbond_lodgements_may_2026.xlsx">
      Rental bond lodgement data - May 2026 (XLSX 646.9KB)
    </a>
    <a href="/copy.xlsx">Copy of old spreadsheet</a>
    <a title="Rental bond lodgements for year 2023" href="/year_2023.xlsx">2023</a>
    """

    links = discover_links(html)

    assert links["period_value"].tolist() == ["2023", "May 2026"]
    assert links.set_index("period_value").loc["May 2026", "period"] == "month"
    assert links.set_index("period_value").loc["2023", "period"] == "annual"


def test_normalize_rentboard_frame_selects_expected_final_columns():
    raw = pd.DataFrame(
        {
            "Lodgement Date": ["2026-05-01"],
            "Postcode": [2000],
            "Dwelling Type": ["F"],
            "Bedrooms": [2],
            "Weekly Rent": [750],
            "Ignored": ["x"],
        }
    )

    normalized = normalize_rentboard_frame(raw)

    assert normalized.to_dict(orient="records") == [
        {
            "lodgement_dt": "2026-05-01",
            "postcode": 2000,
            "property_type": "F",
            "bedrooms": 2,
            "weekly_rent": 750,
        }
    ]


def test_prefer_monthly_when_annual_and_monthly_overlap():
    links = pd.DataFrame(
        {
            "href": ["annual", "jan", "feb", "annual-without-monthly"],
            "title": ["2025 annual", "January 2025", "February 2025", "2026 annual"],
            "period": ["annual", "month", "month", "annual"],
            "period_value": ["2025", "January 2025", "February 2025", "2026"],
            "period_start": pd.to_datetime(["2025-01-01", "2025-01-01", "2025-02-01", "2026-01-01"]),
        }
    )

    selected = prefer_monthly_when_available(links)

    assert selected["href"].tolist() == ["jan", "feb", "annual-without-monthly"]


class FakeResponse:
    def __init__(self, text=None, content=None):
        self.text = text or ""
        self.content = content or b""

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, html, xlsx_bytes):
        self.html = html
        self.xlsx_bytes = xlsx_bytes

    def get(self, url, timeout):
        if url.endswith(".xlsx"):
            return FakeResponse(content=self.xlsx_bytes)
        return FakeResponse(text=self.html)


def make_rentboard_xlsx_bytes():
    raw = pd.DataFrame(
        {
            "Lodgement Date": ["2024-09-01"],
            "Postcode": [2000],
            "Dwelling Type": ["U"],
            "Bedrooms": [1],
            "Weekly Rent": [600],
        }
    )
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        raw.to_excel(writer, index=False, startrow=2)
    return output.getvalue()


def test_update_rentboard_appends_rows_after_existing_max_date(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    final_path = data_dir / "rentboard_df.csv"
    final_path.write_text(
        "lodgement_dt,postcode,property_type,bedrooms,weekly_rent\n"
        "2024-08-31,2000,F,2,550\n",
        encoding="utf-8",
    )
    html = """
    <a href="/sites/default/files/noindex/2024-10/rental-bond-lodgements-september-2024.xlsx">
      Rental bond lodgement data - September 2024 (XLSX 725.55KB)
    </a>
    """

    status = update_rentboard(data_dir=data_dir, session=FakeSession(html, make_rentboard_xlsx_bytes()))
    result = pd.read_csv(final_path, dtype=str)

    assert status["new_rows"].tolist() == [1]
    assert result["lodgement_dt"].tolist() == ["2024-08-31", "2024-09-01"]
    assert result["weekly_rent"].tolist() == ["550", "600"]
