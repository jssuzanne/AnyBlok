from anyblok.tests.testcase import TestCase
from anyblok.registry import RegistryManager
from anyblok.environment import EnvironmentManager
from anyblok import Declarations
target_registry = Declarations.target_registry
remove_registry = Declarations.remove_registry
Model = Declarations.Model


class OneModel:
    __tablename__ = 'test'


class TestModel(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestModel, cls).setUpClass()
        RegistryManager.init_blok('testModel')
        EnvironmentManager.set('current_blok', 'testModel')

    @classmethod
    def tearDownClass(cls):
        super(TestModel, cls).tearDownClass()
        EnvironmentManager.set('current_blok', None)
        del RegistryManager.loaded_bloks['testModel']

    def setUp(self):
        super(TestModel, self).setUp()
        blokname = 'testModel'
        RegistryManager.loaded_bloks[blokname]['Model'] = {
            'registry_names': []}

    def assertInModel(self, *args):
        blokname = 'testModel'
        blok = RegistryManager.loaded_bloks[blokname]
        self.assertEqual(len(blok['Model']['Model.MyModel']['bases']),
                         len(args))
        for cls_ in args:
            has = cls_ in blok['Model']['Model.MyModel']['bases']
            self.assertEqual(has, True)

    def test_add_interface(self):
        target_registry(Model, cls_=OneModel, name_='MyModel')
        self.assertEqual('Model', Model.MyModel.__declaration_type__)
        self.assertInModel(OneModel)
        dir(Declarations.Model.MyModel)

    def test_add_interface_with_decorator(self):

        @target_registry(Model)
        class MyModel:
            pass

        self.assertEqual('Model', Model.MyModel.__declaration_type__)
        self.assertInModel(MyModel)

    def test_add_two_interface(self):

        target_registry(Model, cls_=OneModel, name_="MyModel")

        @target_registry(Model)
        class MyModel:
            pass

        self.assertInModel(OneModel, MyModel)

    def test_remove_interface_with_1_cls_in_registry(self):

        target_registry(Model, cls_=OneModel, name_="MyModel")
        self.assertInModel(OneModel)
        blokname = 'testModel'
        remove_registry(Model, cls_=OneModel, name_="MyModel",
                        blok=blokname)

        blokname = 'testModel'
        self.assertEqual(hasattr(Model, blokname), False)
        self.assertInModel()

    def test_remove_interface_with_2_cls_in_registry(self):

        target_registry(Model, cls_=OneModel, name_="MyModel")

        @target_registry(Model)
        class MyModel:
            pass

        self.assertInModel(OneModel, MyModel)
        blokname = 'testModel'
        remove_registry(Model, cls_=OneModel, name_="MyModel",
                        blok=blokname)
        self.assertInModel(MyModel)
