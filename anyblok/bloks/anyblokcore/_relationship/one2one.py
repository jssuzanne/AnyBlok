from anyblok.field import FieldException
from AnyBlok import RelationShip, target_registry
from sqlalchemy.orm import backref

# FIXME cause of refactore relation ship api


@target_registry(RelationShip)
class One2One(RelationShip.Many2One):
    """ Define a relation ship attribute on the model

    ::

        @target_registry(Model)
        class TheModel:

            relationship = One2One(label="The relation ship",
                                   model=Model.RemoteModel,
                                   remote_column="The remote column",
                                   column_name="The column which have the "
                                               "foreigh key",
                                   nullable=False,
                                   backref="themodels")

    If the remote_column are not define then, the system take the primary key
    of the remote model

    If the column doesn't exist, then the column will be create. Use the
    nullable option.
    If the name has not filled then the name is "'remote table'_'remote colum'"

    :param model: the remote model
    :param remote_column: the column name on the remote model
    :param column_name: the column on the model which have the foreign key
    :param nullable: If the column_name is nullable
    :param backref: create the one2one link with this one2one
    """

    def __init__(self, **kwargs):
        super(One2One, self).__init__(**kwargs)

        if 'backref' not in kwargs:
            raise FieldException("backref is a required argument")

        if 'one2many' in kwargs:
            raise FieldException("Unknow argmument 'one2many'")

        self.kwargs['backref'] = backref(
            self.kwargs['backref'], uselist=False)
