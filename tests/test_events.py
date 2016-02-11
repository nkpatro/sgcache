from . import *


class TestEvents(SGTestCase):

    def test_create_basics(self):

        self.cached.clear()
        self.direct.clear()
        self.cached.control('scanner', 'stop')

        a = self.direct.create('Task', {'content': uuid(8)})
        self.cached.control('events', 'poll')

        b = self.cached.find_one('Task', [('id', 'is', a['id'])], ['content'])

        self.assertSameEntity(a, b)