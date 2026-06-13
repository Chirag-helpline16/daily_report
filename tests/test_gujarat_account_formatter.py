import io
import zipfile

import pandas as pd
from openpyxl import load_workbook

from src.gujarat_account_formatter import (
    OUTPUT_COLUMNS,
    bankwise_zip_bytes,
    dataframe_to_styled_excel_bytes,
    detect_columns,
    process_gujarat_account_file,
)


def test_detect_columns_for_automated_workflow_headers():
    columns = ["S No.", "Acknowledgement No.", "IFSC Code", "Bank/FIs", "Account No."]

    detected = detect_columns(columns)

    assert detected == {
        "ACK NO": "Acknowledgement No.",
        "IFSC CODE": "IFSC Code",
        "BANK NAME": "Bank/FIs",
        "AC NO": "Account No.",
    }


def test_process_gujarat_file_removes_duplicate_accounts_and_keeps_blank_suspect_fields():
    df = pd.DataFrame(
        {
            "Acknowledgement No.": ["3111", "3112", "3113", "3114"],
            "IFSC Code": ["SBIN0001", "HDFC0001", "BARB0001", "ICIC0001"],
            "Bank/FIs": ["SBI", "HDFC", "BOB", "ICICI"],
            "Account No.": ["1001", "1001", "", "2002.0"],
        }
    )
    mapping = {
        "ACK NO": "Acknowledgement No.",
        "IFSC CODE": "IFSC Code",
        "BANK NAME": "Bank/FIs",
        "AC NO": "Account No.",
    }

    output, stats = process_gujarat_account_file(df, mapping)

    assert list(output.columns) == OUTPUT_COLUMNS
    assert output["AC NO"].tolist() == ["2002", "1001"]
    assert output["SR NO"].tolist() == [1, 2]
    assert output[["SUSPECT NAME", "SUSPECT ADDRESS", "SUSPECT MOBILE NUMBER", "SUSPECT LOCATION"]].eq("").all().all()
    assert stats["duplicate_account_rows"] == 1
    assert stats["blank_account_rows"] == 1
    assert stats["output_rows"] == 2


def test_styled_excel_has_expected_structure():
    df = pd.DataFrame(
        [[1, "3111", "SBIN0001", "SBI", "1001", "", "", "", ""]],
        columns=OUTPUT_COLUMNS,
    )

    excel_bytes = dataframe_to_styled_excel_bytes(df)
    workbook = load_workbook(io.BytesIO(excel_bytes))
    worksheet = workbook.active

    assert [cell.value for cell in worksheet[1]] == OUTPUT_COLUMNS
    assert worksheet.freeze_panes == "A2"
    assert worksheet.auto_filter.ref == "A1:I2"


def test_bankwise_zip_contains_one_excel_per_bank():
    df = pd.DataFrame(
        [
            [1, "3111", "SBIN0001", "SBI", "1001", "", "", "", ""],
            [2, "3112", "HDFC0001", "HDFC", "2002", "", "", "", ""],
        ],
        columns=OUTPUT_COLUMNS,
    )

    zip_bytes = bankwise_zip_bytes(df)

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        names = sorted(archive.namelist())
        assert names == ["HDFC.xlsx", "SBI.xlsx"]
        sbi_df = pd.read_excel(io.BytesIO(archive.read("SBI.xlsx")), dtype=str, keep_default_na=False)

    assert list(sbi_df.columns) == OUTPUT_COLUMNS
    assert sbi_df.loc[0, "SR NO"] == "1"
    assert sbi_df.loc[0, "BANK NAME"] == "SBI"
