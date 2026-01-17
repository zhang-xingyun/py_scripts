import json
from pathlib import Path

from hatbc.filestream.bucket.client import BucketClient


def read_infos_from_json(
    json_file_name="",
    url_name="url",
    batch_size=50,
):
    """Read json infos and return infos as a 2D list.

    Parameters
    ----------
    json_file_name:
        json file name to read
    url_name:
        type of url to read
    batch_size:
        number of data to process per iteration
    """

    file_path = []
    with open(json_file_name, "r") as f:
        lines = f.readlines()
    bkt_clt = BucketClient()
    for line in lines:
        line = json.loads(line)
        file_path.append(bkt_clt.url_to_local(line[url_name]))
    infos = []
    sub_infos = None
    file_path.sort(key=lambda x: Path(x).stem)

    for i, fname in enumerate(file_path):
        if i % batch_size == 0:
            if sub_infos is not None:
                infos.append(sub_infos)
            sub_infos = []
        sub_infos.append(fname)
        if i == len(file_path) - 1:
            infos.append(sub_infos)

    return infos
