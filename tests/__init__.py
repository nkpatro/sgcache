import os

from sgmock.unittest import TestCase
from shotgun_api3 import Shotgun as _Shotgun


class Shotgun(_Shotgun):

    def __init__(self, *args, **kwargs):

        self.pragmas = kwargs.pop('pragmas', {})
        super(Shotgun, self).__init__(*args, **kwargs)

        # Absolutely make sure that we can use it.
        cache_info = self.server_info.get('sgcache')
        mock_info = self.server_info.get('sgmock')

        if not (cache_info or mock_info):
            raise RuntimeError('%s is not a sgcache or sgmock', self.base_url)

        if cache_info:
            if not isinstance(cache_info, dict):
                raise RuntimeError('%s is a pre-testable sgcache', self.base_url)
            if not cache_info.get('testing'):
                raise RuntimeError('%s is not in testing mode', self.base_url)

    def _build_payload(self, *args, **kwargs):
        payload = super(Shotgun, self)._build_payload(*args, **kwargs)
        if self.pragmas:
            payload['pragmas'] = self.pragmas
        return payload

    def clear(self):
        self._call_rpc('clear', None)

    def count(self):
        return self._call_rpc('count', None)


def connect(url=None, script_name=None, api_key=None, **kwargs):
    return Shotgun(
        url or os.environ.get('SGCACHE_TEST_URL', 'http://localhost:8010/'),
        script_name or os.environ.get('SGCACHE_TEST_SCRIPT_NAME', 'sgcache_testing'),
        api_key or os.environ.get('SGCACHE_TEST_API_KEY', 'not-a-key'),
        **kwargs
    )


class SGTestCase(TestCase):

    def __init__(self, *args):
        super(SGTestCase, self).__init__(*args)
        self.direct = connect(os.environ.get('SGCACHE_SHOTGUN_URL', 'http://localhost:8020/'))
        self.cached = connect()


def uuid(len_=32):
    return os.urandom(len_ / 2 + 1).encode('hex')[:len_]
