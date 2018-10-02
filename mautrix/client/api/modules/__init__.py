from .media_repository import MediaRepositoryMethods
from .misc import MiscModuleMethods


class ModuleMethods(MediaRepositoryMethods, MiscModuleMethods):
    """
    Methods in section 13 Modules of the spec.

    See also: `API reference <https://matrix.org/docs/spec/client_server/r0.4.0.html#modules>`__
    """

    # TODO: subregions 15, 18, 19, 21, 26, 27, others?
