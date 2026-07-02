import pandas as pd

from propertyiq_getdata.diagnostics import filter_nswgov_frame, monthly_average_sale_price


def test_filter_nswgov_frame_accepts_postcode_and_suburb():
    df = pd.DataFrame(
        {
            "locality": ["HORNSBY", "Hornsby", "WAITARA"],
            "postcode": ["2077.0", "2077", "2077"],
            "contract_dt": ["20260101", "20260102", "20260103"],
            "sale_price": ["100", "200", "300"],
        }
    )

    filtered = filter_nswgov_frame(df, postcode="2077", suburb="hornsby")

    assert filtered["sale_price"].tolist() == ["100", "200"]


def test_monthly_average_sale_price_groups_by_contract_month():
    df = pd.DataFrame(
        {
            "locality": ["A", "A", "A"],
            "postcode": ["2000", "2000", "2000"],
            "contract_dt": ["20260101", "20260120", "20260201"],
            "sale_price": ["100", "300", "600"],
        }
    )

    result = monthly_average_sale_price(df, source="latest")

    assert result["source"].tolist() == ["latest", "latest"]
    assert result["avg_sale_price"].tolist() == [200.0, 600.0]
    assert result["sales"].tolist() == [2, 1]
