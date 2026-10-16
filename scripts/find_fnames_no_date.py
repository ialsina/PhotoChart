# coding: utf-8
from argparse import ArgumentParser
from dotenv import load_dotenv
import pandas as pd
import psycopg2 as pg
import os
import re

load_dotenv()

photo = None
path = None
device = None
df = None


def _get_parser() -> ArgumentParser:
    parser = ArgumentParser()
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="Output write path for list of photographs without a path",
    )
    parser.add_argument(
        "-d", "--device-id", type=int, nargs="+", help="Filter by device id"
    )
    return parser


def main():

    global photo, path, device, df

    args = _get_parser().parse_args()

    output = args.output
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

    fnames_no_date = sorted(
        df[(df["time"].isna()) & (df["model"].isna())]["filename"].unique()
    )

    filters = (
        re.compile(r"^\d+\.(jpg|jpeg|png)$").match,
        re.compile(r"^\W+\.(jpg|jpeg|png)$").match,
        re.compile(r"WA\d{4}\.(jpg|jpeg|png)$").search,
        re.compile(r"^STK.*\.webp$").match,
        re.compile(r"^tile_").match,
        lambda x: sum(c.isdigit() for c in x) < 8,
    )

    fnames_no_date = set(fnames_no_date)
    total_filtered = 0
    initial = len(fnames_no_date)

    for i, filt in enumerate(filters, start=1):
        filt_out = set(filter(filt, fnames_no_date))
        print(f"{i} rule: Filtered out {len(filt_out)} elements.")
        total_filtered += len(filt_out)
        fnames_no_date = fnames_no_date - filt_out

    print(
        f"Filtered out {total_filtered} out of {initial} entries in filenames without a date."
    )

    if output:
        with open(output, "w") as wf:
            wf.write("\n".join(sorted(fnames_no_date)) + "\n")


if __name__ == "__main__":
    main()
