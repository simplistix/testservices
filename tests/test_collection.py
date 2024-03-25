from testfixtures import compare, ShouldRaise

from testservices.collection import Collection, NameConflict, MissingService
from testservices.service import Service


class SampleService(Service['SampleService']):

    def __init__(self, name: str | None = None) -> None:
        self.name = name
        self.running = False

    def exists(self) -> bool:
        return self.running

    def create(self) -> None:
        assert not self.running
        self.running = True

    def get(self) -> "SampleService":
        assert self.running
        return self

    def destroy(self) -> None:
        assert self.running
        self.running = False


class TestNaming:

    def test_all_explicit(self):
        collection = Collection(name='cname')
        service = SampleService(name='sname')
        collection.manage(service, name='mname')
        compare(service.name, expected='cname_mname')

    def test_all_implicit(self):
        collection = Collection()
        service = SampleService()
        collection.manage(service)
        compare(service.name, expected='tests_SampleService')

    def test_duplicate_implicit(self):
        collection = Collection()
        service1 = SampleService()
        service2 = SampleService()
        collection.manage(service1)
        collection.manage(service2)
        compare(service1.name, expected='tests_SampleService')
        compare(service2.name, expected='tests_SampleService_2')

    def test_duplicate_explicit_service_name(self):
        collection = Collection()
        service1 = SampleService(name='bad')
        service2 = SampleService(name='bad')
        collection.manage(service1)
        with ShouldRaise(NameConflict('bad')):
            collection.manage(service2)

    def test_duplicate_explicit_managed_name(self):
        collection = Collection()
        service1 = SampleService()
        service2 = SampleService()
        collection.manage(service1, name='bad')
        with ShouldRaise(NameConflict('bad')):
            collection.manage(service2, name='bad')

    def test_duplicate_explicit_managed_name_clashes_with_service_name(self):
        collection = Collection()
        service1 = SampleService(name='bad')
        service2 = SampleService()
        collection.manage(service1)
        with ShouldRaise(NameConflict('bad')):
            collection.manage(service2, name='bad')

    def test_different_explict_managed_named(self):
        collection = Collection()
        service1 = SampleService(name='s1')
        service2 = SampleService()
        collection.manage(service1)
        collection.manage(service2, name='s2')
        compare(service1.name, expected='tests_s1')
        compare(service2.name, expected='tests_s2')


class TestObtain:

    def test_minimal(self):
        managed = SampleService()
        collection = Collection(managed)
        obtained = collection.obtain(SampleService)
        assert obtained.possible()
        assert not obtained.exists()
        with ShouldRaise(MissingService(
                '<SampleService: tests_SampleService> did not exist, collection not up?'
        )):
            obtained.create()
        with collection:
            assert managed.running
            with obtained as service:
                assert service is managed
                assert managed.running
            assert managed.running
        assert not managed.running

    def test_by_name(self):
        managed = SampleService(name='foo')
        collection = Collection(SampleService(name='bar'), managed)
        obtained = collection.obtain(SampleService, name='foo')
        assert obtained.service is managed

    def test_by_name_mapping_to_constructor(self):
        foo = SampleService()
        bar = SampleService()
        collection = Collection({'foo': foo, 'bar': bar})
        obtained = collection.obtain(SampleService, name='foo')
        assert obtained.service is foo

    def test_by_name_gives_wrong_type(self):
        collection = Collection(SampleService(name='foo'))

        class OtherService(Service[None]): pass

        with ShouldRaise(TypeError(
                "'foo' is of type SampleService, "
                "but TestObtain.test_by_name_gives_wrong_type.<locals>.OtherService requested"
        )):
            collection.obtain(OtherService, name='foo')

    def test_by_type_returns_multiple(self):
        collection = Collection(SampleService(name='foo'), SampleService(name='bar'))
        with ShouldRaise(TypeError(
                'Multiple services, specify name: '
                '<Managed SampleService: foo>, <Managed SampleService: bar>'
        )):
            collection.obtain(SampleService)
