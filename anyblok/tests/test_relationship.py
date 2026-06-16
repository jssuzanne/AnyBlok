# This file is a part of the AnyBlok project
#
#    Copyright (C) 2014 Jean-Sebastien SUZANNE <jssuzanne@anybox.fr>
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file,You can
# obtain one at http://mozilla.org/MPL/2.0/.
import pytest

from anyblok import Declarations
from anyblok.column import Integer
from anyblok.field import FieldException
from anyblok.relationship import (
    Many2Many,
    Many2One,
    One2Many,
    One2One,
    RelationShip,
    RelationShipList,
    ordering_list,
    AnyBlokOrderingList,
)
from anyblok.common import cache_to_instance

from .conftest import init_registry_with_bloks

register = Declarations.register
Model = Declarations.Model


class OneRelationShip(RelationShip):
    pass


class OneModel:
    __tablename__ = "test"
    __registry_name__ = "One.Model"


class MockRegistry:
    InstrumentedList = []

class Fake:
    __declaration_type__ = 'Model'
    __tablename__ = "test"
    __registry_name__ = "Model.Fake"

setattr(Model, 'Fake', Fake)


RELATIONSHIPS = [
    pytest.param(
        (Many2One, dict(model=Model.Fake, remote_columns=["id"], column_names=['blok_id'], on2many="other", nullable=False)),
        id="Many2One1",
    ),
    pytest.param(
        (Many2One, dict(model=Model.Fake, remote_columns="id", on2many=["other", dict(order_by="ModelFake.name", collection_class=ordering_list('name'))], nullable=False)),
        id="Many2One2",
    ),
    pytest.param(
        (Many2One, dict(model=Model.Fake)),
        id="Many2One3",
    ),
    pytest.param(
        (Many2One, dict(model="Model.Fake")),
        id="Many2One4",
    ),
    pytest.param(
        (
            Many2Many,
            dict(
                model=Model.Fake,
                join_table="join_addresses_by_persons",
                remote_columns=["id"],
                local_columns=["name"],
                m2m_remote_columns=["a_id"],
                m2m_local_columns=["p_name"],
                many2many="persons",
            )
        ),
        id="Many2Many1",
    ),
    pytest.param(
        (
            Many2Many,
            dict(
                model=Model.Fake,
                join_table="join_addresses_by_persons",
                remote_columns="id",
                local_columns="name",
                m2m_remote_columns="a_id",
                m2m_local_columns="p_name",
                schema="test_db_m2m_schema",
                many2many=(
                    "persons",
                    dict(
                        order_by="ModelPerson.name",
                        collection_class=AnyBlokOrderingList("name"),
                    ),
                ),
            )
        ),
        id="Many2Many2",
    ),
    pytest.param(
        (Many2Many, dict(model=Model.Fake)),
        id="Many2Many2",
    ),
    pytest.param(
        (
            One2Many,
            dict(
                model=Model.Fake,
                remote_columns="address_id",
                primaryjoin="primaryjoin",
                many2one="address",
            )
        ),
        id="One2Many1",
    ),
    pytest.param(
        (
            One2Many,
            dict(
                model=Model.Fake,
                remote_columns="address_id",
                primaryjoin="primaryjoin",
                many2one="address",
                order_by="ModelPerson.name",
                collection_class=AnyBlokOrderingList("name"),
            )
        ),
        id="One2Many2",
    ),
    pytest.param(
        (
            One2One,
            dict(
                model=Model.Fake,
                column_names=("test_id", "test_id2"),
                backref="address",
            )
        ),
        id="One2One",
    ),
]


@pytest.fixture(params=RELATIONSHIPS)
def relationship_definition(request):
    return request.param


class TestRelationShip:
    def test_forbid_instance(self):
        with pytest.raises(FieldException):
            RelationShip(model=OneModel)

    def test_must_have_a_model(self):
        OneRelationShip(model=OneModel)
        with pytest.raises(FieldException):
            OneRelationShip()

    def test_cache(self, relationship_definition):
        field, kwargs = relationship_definition
        f1 = field(**kwargs)
        cache1 = f1.to_cache()
        f2 = cache_to_instance(cache1)
        cache2 = f2.to_cache()
        assert cache1 == cache2


class List(RelationShipList, list):
    def relationship_field_append_value(*a, **kw):
        return True

    def relationship_field_remove_value(*a, **kw):
        return True


class TestRelationShipList:
    def test_append(self):
        list_ = List()
        list_.append(1)
        assert list_ == [1]

    def test_extend(self):
        list_ = List()
        list_.extend([1, 2])
        assert list_ == [1, 2]

    def test_insert(self):
        list_ = List()
        list_.insert(0, 1)
        assert list_ == [1]
        list_.insert(0, 2)
        assert list_ == [2, 1]

    def test_pop(self):
        list_ = List()
        list_.extend([1, 2])
        assert list_ == [1, 2]
        list_.pop(0)
        assert list_ == [2]
        list_.pop(0)
        assert list_ == []

    def test_remove(self):
        list_ = List()
        list_.extend([3, 2, 1])
        assert list_ == [3, 2, 1]
        list_.remove(1)
        assert list_ == [3, 2]

    def test_clear(self):
        list_ = List()
        list_.extend([3, 2, 1])
        assert list_ == [3, 2, 1]
        list_.clear()
        assert list_ == []


def multi_parallel_foreign_key_with_definition():
    @register(Model)
    class Address:
        id = Integer(primary_key=True)

    @register(Model)
    class Person:
        id = Integer(primary_key=True)
        address_1_id = Integer(foreign_key=Model.Address.use("id"))
        address_2_id = Integer(foreign_key=Model.Address.use("id"))
        address_1 = Many2One(model=Model.Address, column_names=["address_1_id"])
        address_2 = Many2One(model=Model.Address, column_names=["address_2_id"])

    @register(Model)  # noqa
    class Address:
        persons = One2Many(model=Model.Person)


def multi_parallel_foreign_key_auto_detect():
    @register(Model)
    class Address:
        id = Integer(primary_key=True)
        persons = One2Many(model="Model.Person")

    @register(Model)
    class Person:
        id = Integer(primary_key=True)
        address_1 = Many2One(model=Model.Address)
        address_2 = Many2One(model=Model.Address)


@pytest.fixture(
    scope="class",
    params=[
        multi_parallel_foreign_key_with_definition,
        multi_parallel_foreign_key_auto_detect,
    ],
)
def registry_relationship_multiple_foreign_keys(request, bloks_loaded):
    registry = init_registry_with_bloks([], request.param)
    request.addfinalizer(registry.close)
    return registry


class TestComplexeRelationShipCase:
    @pytest.fixture(autouse=True)
    def transact(self, request, registry_relationship_multiple_foreign_keys):
        transaction = registry_relationship_multiple_foreign_keys.begin_nested()
        request.addfinalizer(transaction.rollback)
        return

    def test_with_multi_parallel_foreign_key_with_definition(
        self, registry_relationship_multiple_foreign_keys
    ):
        registry = registry_relationship_multiple_foreign_keys
        address_1 = registry.Address.insert()
        address_2 = registry.Address.insert()
        person = registry.Person.insert(
            address_1=address_1, address_2=address_2
        )
        assert address_1.persons == [person]
        assert address_2.persons == [person]
