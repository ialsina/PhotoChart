# coding: utf-8
from argparse import ArgumentParser
from dotenv import load_dotenv
import math
import os
import pandas as pd
import psycopg2 as pg
import sys

from photochart.imaging.filename_time import parse_datetime_from_filename

load_dotenv()

photo = None
path = None
device = None
df = None

DIFF_THRESHOLD = pd.Timedelta(hours=12)


def _get_parser() -> ArgumentParser:
    parser = ArgumentParser()
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        required=True,
        help="Output .html path for the report (batched writes use stem_NNN.html)",
    )
    parser.add_argument(
        "-b",
        "--batch",
        type=int,
        default=None,
        metavar="N",
        help="Max rows per HTML file; writes stem_000.html, stem_001.html, …",
    )
    parser.add_argument(
        "-d", "--device-id", type=int, nargs="+", help="Filter by device id"
    )
    return parser


def _filename_to_datetime(series: pd.Series) -> pd.Series:
    return series.map(parse_datetime_from_filename)


def _strip_tz(value):
    if value is None or (not isinstance(value, (str, bytes)) and pd.isna(value)):
        return value
    ts = pd.Timestamp(value)
    if ts.tz is not None:
        return ts.to_pydatetime().replace(tzinfo=None)
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if getattr(value, "tzinfo", None) is not None:
        return value.replace(tzinfo=None)
    return value


def _naive_db_time(series: pd.Series) -> pd.Series:
    return series.map(_strip_tz)


def _format_timestamp_series(series: pd.Series) -> pd.Series:
    return _naive_db_time(series).map(
        lambda x: x.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(x) else ""
    )


def compute_difference(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.loc[frame["fname_time"].notna() & frame["time"].notna()].copy()
    out["difference"] = _naive_db_time(out["time"]) - out["fname_time"]
    return out


def _format_timedelta(td: pd.Timedelta) -> str:
    if pd.isna(td):
        return ""
    total_seconds = int(td.total_seconds())
    sign = "+" if total_seconds >= 0 else "−"
    total_seconds = abs(total_seconds)
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    body = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    if days:
        body = f"{days}d {body}"
    return f"{sign}{body}"


def _require_html_output_path(output_path: str) -> None:
    if not output_path.lower().endswith(".html"):
        print("error: --output must be an .html file path", file=sys.stderr)
        sys.exit(2)


def _batched_output_paths(output_path: str, part_count: int) -> list[str]:
    root, ext = os.path.splitext(output_path)
    width = max(3, len(str(part_count - 1)))
    return [f"{root}_{i:0{width}d}{ext}" for i in range(part_count)]


def _report_display_frame(report: pd.DataFrame, row_start: int = 1) -> pd.DataFrame:
    n = len(report)
    return pd.DataFrame(
        {
            "": (
                pd.RangeIndex(row_start, row_start + n) if n else pd.Series(dtype=int)
            ),
            "Photograph Id": report["photograph_id"],
            "Path id": report["id_path"],
            "filename": report["filename"],
            "time": _format_timestamp_series(report["time"]),
            "fname_time": _format_timestamp_series(report["fname_time"]),
            "difference": report["difference"].map(_format_timedelta),
        }
    )


def _html_report_table(report: pd.DataFrame, row_start: int = 1) -> str:
    over_threshold = report["difference"].abs() > DIFF_THRESHOLD
    display = _report_display_frame(report, row_start=row_start)

    highlight_cols = {"time", "fname_time", "difference"}

    def _highlight_row(row: pd.Series) -> list[str]:
        if not over_threshold.loc[row.name]:
            return [""] * len(row)
        return [
            (
                "background-color: #ffd6d6; font-weight: 600;"
                if col in highlight_cols
                else ""
            )
            for col in row.index
        ]

    n_rows, n_cols = display.shape
    styled = display.style.apply(_highlight_row, axis=1).hide(axis="index")
    styled = styled.set_table_styles(
        [
            {
                "selector": "table",
                "props": [
                    ("border-collapse", "collapse"),
                    ("width", "100%"),
                    ("font-family", "system-ui, sans-serif"),
                    ("font-size", "14px"),
                ],
            },
            {
                "selector": "th",
                "props": [
                    ("background-color", "#f0f4f8"),
                    ("border", "1px solid #c5cdd8"),
                    ("padding", "8px 10px"),
                    ("text-align", "left"),
                ],
            },
            {
                "selector": "td",
                "props": [
                    ("border", "1px solid #dde3ea"),
                    ("padding", "6px 10px"),
                    ("vertical-align", "top"),
                ],
            },
            {
                "selector": "td.col0",
                "props": [("text-align", "right"), ("color", "#5c6570")],
            },
            {
                "selector": "td.col1, td.col2, td.col4, td.col5, td.col6",
                "props": [("font-family", "ui-monospace, monospace")],
            },
            {
                "selector": "td.col3",
                "props": [
                    ("font-family", "ui-monospace, monospace"),
                    ("white-space", "pre-wrap"),
                    ("word-break", "break-all"),
                ],
            },
        ]
    )
    # Styler defaults cap cells at styler.render.max_elements and append a "..." row.
    with pd.option_context("styler.render.max_elements", n_rows * n_cols):
        return styled.to_html(max_rows=n_rows, max_columns=n_cols)


def write_html_report(
    report: pd.DataFrame,
    output_path: str,
    *,
    row_start: int = 1,
    batch_label: str | None = None,
) -> None:
    over = int((report["difference"].abs() > DIFF_THRESHOLD).sum())
    summary = (
        f"<p><strong>{len(report)}</strong> paths with both DB time and filename-inferred time; "
        f"<strong>{over}</strong> differ by more than 12 hours (highlighted).</p>"
        f"<p>Difference is <code>time − fname_time</code> (positive = DB time is later).</p>"
    )
    if batch_label:
        summary += f"<p>{batch_label}</p>"
    table_html = _html_report_table(report, row_start=row_start)
    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Filename vs DB capture time</title>
</head>
<body>
  <h1>Filename vs DB capture time</h1>
  {summary}
  {table_html}
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as wf:
        wf.write(document)


def write_html_reports(
    report: pd.DataFrame, output_path: str, batch_size: int | None
) -> list[str]:
    _require_html_output_path(output_path)
    if batch_size is None:
        write_html_report(report, output_path)
        return [output_path]

    if batch_size < 1:
        print("error: --batch must be a positive integer", file=sys.stderr)
        sys.exit(2)

    n = len(report)
    part_count = max(1, math.ceil(n / batch_size)) if n else 1
    paths = _batched_output_paths(output_path, part_count)
    for part_index, path in enumerate(paths):
        row_start = part_index * batch_size + 1
        chunk = report.iloc[row_start - 1 : row_start - 1 + batch_size]
        batch_label = (
            f"Part <strong>{part_index + 1}</strong> of <strong>{part_count}</strong>."
        )
        write_html_report(
            chunk,
            path,
            row_start=row_start,
            batch_label=batch_label,
        )
    return paths


def main():

    global photo, path, device, df

    args = _get_parser().parse_args()

    output = args.output
    batch_size = args.batch
    device_id = args.device_id

    engine = pg.connect(os.environ["DATABASE_URL"])
    photo = pd.read_sql("SELECT * FROM photograph_photograph", con=engine)
    path = pd.read_sql("SELECT * FROM photograph_photopath", con=engine)
    device = pd.read_sql("SELECT * FROM photograph_storagedevice", con=engine)
    df = path.merge(
        photo,
        left_on="photograph_id",
        right_on="id",
        how="left",
        suffixes=("_path", "_photo"),
    )

    if device_id:
        df = df[df["storage_device_id"].isin(device_id)]

    df["fname_time"] = _filename_to_datetime(df["filename"])
    report = compute_difference(df)
    report = report.sort_values(
        by="difference",
        key=lambda s: s.abs(),
        ascending=False,
    )

    over = (report["difference"].abs() > DIFF_THRESHOLD).sum()
    print(f"{len(report)} rows with both times; {over} with |difference| > 12h.")

    written = write_html_reports(report, output, batch_size)
    if len(written) == 1:
        print(f"Wrote {written[0]}")
    else:
        print(f"Wrote {len(written)} files ({written[0]} … {written[-1]})")


if __name__ == "__main__":
    main()
