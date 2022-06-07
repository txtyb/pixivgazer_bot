import contextlib
import io
import zipfile
from typing import ContextManager, Dict, Tuple
from pixivpy3 import AppPixivAPI
from PIL import Image

api = AppPixivAPI()

api.auth(refresh_token='7Za6idDkEavN3hhOvsexHNnFkiPX56elDv_Y34TRR_Q')

FRAME_DATA_TYPE = Dict[str, int]

@contextlib.contextmanager
def open_zip_blob(blob: bytes) -> ContextManager[zipfile.ZipFile]:
    """Make temporary zip file and open it for touch inner files
    :param blob: blob of zip file from :func:`ugoira.lib.download_ugoira_zip`
    :type blob: :class:`bytes`
    """

    assert isinstance(blob, (bytes, bytearray)), "Parameter `blob` must be " \
        "of types (bytes, bytearray). Passed %s (%s)" % (type(blob), blob)

    f = io.BytesIO(blob)
    with zipfile.ZipFile(f) as zf:
        yield zf


def make_via_pillow(
    dest: str,
    blob: bytes,
    frames: FRAME_DATA_TYPE,
    speed: float = 1.0,
    format: str = 'gif',
):
    """Make animated file from given file data and frame data.
    :param dest: path of output file
    :type dest: :class:`str`
    :param blob: blob of zip file from :func:`ugoira.lib.download_ugoira_zip`
    :type blob: :class:`bytes`
    :param frames: mapping object of each frame's filename and interval
    :param speed: frame interval control value
    :type speed: :class:`float`
    :param format: format of result file
    :type format: :class:`str`
    """

    with open_zip_blob(blob) as zf:
        files = zf.namelist()
        images = []
        durations = []
        width = 0
        height = 0
        for file in files:
            f = io.BytesIO(zf.read(file))
            im = Image.open(fp=f)
            width = max(im.width, width)
            height = max(im.height, height)
            images.append(im)
            if format == 'gif':
                durations.append(int(frames[file] / speed))
            elif format == 'webp':
                durations.append(int(frames[file] / speed))

        first_im = images.pop(0)
        kwargs = {
            'format': format,
            'save_all': True,
            'append_images': images,
        }
        if format == 'gif':
            kwargs['duration'] = durations
            kwargs['loop'] = 0
            # kwargs['version'] = 'GIF89a'
            # kwargs['optimize'] = True
        elif format == 'webp':
            kwargs['duration'] = durations
            kwargs['lossless'] = False
            kwargs['quality'] = 80
            kwargs['method'] = 4

        first_im.save(dest, **kwargs)


def gen_frames(path, body) -> Tuple[bytes, FRAME_DATA_TYPE]:
    frames = {f['file']: f['delay'] for f in body.frames}
    with open(path, 'rb') as f:
        blob = f.read()
        return blob, frames


def ugoira(
    speed: float,
    format: str,
    dest: str,
    path: str,
    ugoira_metadata, 
):
    blob, frames = gen_frames(path, ugoira_metadata)

    make_via_pillow(dest, blob, frames, speed, format)

    # print('Done! ')


if __name__ == '__main__':
    meta_page = api.ugoira_metadata(98766380).ugoira_metadata
    url = meta_page.zip_urls.medium
    api.download(url, name='test.zip')

    ugoira(1, 'gif', '1.gif', 'test.zip', meta_page)
