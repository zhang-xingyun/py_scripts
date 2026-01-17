import base64
import logging
import lzma
import os
import pickle
from io import BytesIO
from subprocess import PIPE, CompletedProcess, Popen, getstatusoutput

import numpy as np
from numpy.lib.format import write_array


logger = logging.getLogger(__name__)

has_7z = None

COMPRESS_METHOD = "compress_method"


class CompressMethod(StrEnum):
    LZMA = "lzma"
    SEVEN_Z = "7z"
    PY7ZR = "py7zr"


def subprocess_pipe_run(*popenargs, input=None):
    with Popen(*popenargs, stdin=PIPE, stdout=PIPE, stderr=PIPE) as process:
        try:
            stdout, stderr = process.communicate(input)
        except:  # noqa
            process.kill()
            process.wait()
            logger.error("subprocess exit error")
            stdout = ""
            stderr = "ERROR"
        retcode = process.poll()
    return CompletedProcess(process.args, retcode, stdout, stderr)


@profile
def compress_using_7z(numpy_array, key="classname", dtype=np.uint8):
    deprecated_warning("Please use `compress_using_lzma` instead.")
    uint8_numpy = numpy_array.astype(dtype)

    global has_7z
    if has_7z is None:
        has_7z, _ = getstatusoutput("7z")
    if has_7z != 0:
        return compress_using_py7zr(uint8_numpy, key, dtype)

    bytesio = BytesIO()
    write_array(bytesio, uint8_numpy)

    p = subprocess_pipe_run(
        ["7z", "a", "-an", "-txz", "-si", "-so"], input=bytesio.getvalue()
    )
    bytesio.close()

    if p.returncode != 0 or p.stderr == "ERROR":
        err_msg = f"code: {p.returncode}, err: {p.stderr}"
        logger.error(err_msg)
        raise RuntimeError(err_msg)
    b64_str = base64.b64encode(p.stdout)
    return b64_str.decode("utf-8")


@profile
def decompress_using_7z(b64_str, key="classname", dtype=np.uint8):
    deprecated_warning("Please use `decompress_using_lzma` instead.")
    global has_7z
    if has_7z is None:
        has_7z = os.system("7z")
    if has_7z != 0:
        return decompress_using_py7zr(b64_str, key, dtype)

    b64_bytes = base64.b64decode(b64_str)
    p = subprocess_pipe_run(
        ["7z", "e", "-an", "-txz", "-si", "-so"], input=b64_bytes
    )
    if p.returncode == 2:
        return decompress_using_py7zr(b64_bytes, key, dtype)
    elif p.returncode != 0:
        err_msg = f"code: {p.returncode}, err: {p.stderr}"
        logger.error(err_msg)
        raise RuntimeError(err_msg)

    with BytesIO(p.stdout) as bytesio:
        return np.load(bytesio, allow_pickle=True)


@profile
def decompress_using_py7zr(b64_str, key="classname", dtype=np.uint8):
    deprecated_warning("Please use `decompress_using_lzma` instead.")
    try:
        import py7zr

        tmp_file = f"{key}_tmp.7z"
        b64_bytes = base64.b64decode(b64_str)
        with open(tmp_file, "wb") as tmp_f:
            tmp_f.write(b64_bytes)
        with py7zr.SevenZipFile(tmp_file, "r") as archive:
            archive.extractall()
        result = np.load(f"{key}.npz")["data"]
        os.system(f"rm -rf {key}*")
        return result
    except ImportError:
        logger.warning("py7zr not installed.")
        return np.frombuffer(b64_bytes, dtype=dtype)


@profile
def compress_using_py7zr(numpy_array, key="classname", dtype=np.uint8):
    deprecated_warning("Please use `compress_using_lzma` instead.")
    tmp_file = f"{key}.npz"
    uint8_numpy = numpy_array.astype(dtype)
    np.savez_compressed(tmp_file, data=uint8_numpy)
    try:
        import py7zr

        tmp_file_7z = f"{tmp_file}.7z"
        with py7zr.SevenZipFile(tmp_file_7z, "w") as archive:
            archive.writeall(tmp_file)
        tmp_file = tmp_file_7z
    except ImportError:
        logger.warning("py7zr not installed.")

    with open(tmp_file, "rb") as f:
        b64_str = base64.b64encode(f.read())

    os.system(f"rm -rf {key}*")
    return b64_str.decode("utf-8")


@profile
def compress_using_lzma(np_array, dtype=np.uint8):
    uint8_numpy = np_array.astype(dtype)
    # Notice: Cannot use `to_bytes` method due to the shape info is lost.
    numpy_bytes = pickle.dumps(uint8_numpy)
    obj = lzma.compress(numpy_bytes)
    b64_str = base64.b64encode(obj)
    return b64_str.decode("utf-8")


@profile
def decompress_using_lzma(b64_str):
    b64_bytes = base64.b64decode(b64_str)
    obj = lzma.decompress(b64_bytes)
    return pickle.loads(obj)


def add_compress_str_in_common_data(
    np_array, common_data, key="classname", dtype=np.uint8
):
    if COMPRESS_METHOD not in common_data:
        common_data[key] = compress_using_7z(np_array, dtype)
        common_data[COMPRESS_METHOD] = CompressMethod.SEVEN_Z
    else:
        if common_data[COMPRESS_METHOD] == CompressMethod.LZMA:
            common_data[key] = compress_using_lzma(np_array, dtype)
        elif common_data[COMPRESS_METHOD] == CompressMethod.SEVEN_Z:
            common_data[key] = compress_using_7z(np_array, key, dtype)
        elif common_data[COMPRESS_METHOD] == CompressMethod.PY7ZR:
            common_data[key] = compress_using_py7zr(np_array, key, dtype)
        else:
            raise NotImplementedError(common_data[COMPRESS_METHOD])


def decompress_from_common_data(
    b64_str, common_data, key="classname", dtype=np.uint8
):
    if COMPRESS_METHOD in common_data:
        if common_data[COMPRESS_METHOD] == CompressMethod.LZMA:
            return decompress_using_lzma(b64_str, dtype)
        elif common_data[COMPRESS_METHOD] == CompressMethod.SEVEN_Z:
            return decompress_using_7z(b64_str, key, dtype)
        elif common_data[COMPRESS_METHOD] == CompressMethod.PY7ZR:
            return decompress_using_py7zr(b64_str, key, dtype)
        else:
            raise NotImplementedError(common_data[COMPRESS_METHOD])
    else:
        return decompress_using_7z(b64_str, key, dtype)
