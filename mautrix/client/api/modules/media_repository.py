from ..base import BaseClientAPI


class MediaRepositoryMethods(BaseClientAPI):
    """
    Methods in section 13.8 Content Repository of the spec. See also: `API reference`_

    .. _API reference: https://matrix.org/docs/spec/client_server/r0.4.0.html#id112
    """

    async def upload_media(self):
        pass

    async def download_media(self):
        pass

    async def download_thumbnail(self):
        pass

    async def get_url_preview(self):
        pass

    async def get_media_repo_config(self):
        pass
