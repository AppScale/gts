# Copyright (c) The PyAMF Project.
# See LICENSE for details.

"""
Elixir adapter module. Elixir adds a number of properties to the mapped instances.

@see: U{Elixir homepage<http://elixir.ematia.de>}
@since: 0.6
"""

import elixir.entity

import pyamf
from pyamf import adapters

adapter = adapters.get_adapter('sqlalchemy.orm')

adapter.class_checkers.append(elixir.entity.is_entity)


class ElixirAdapter(adapter.SaMappedClassAlias):

    EXCLUDED_ATTRS = adapter.SaMappedClassAlias.EXCLUDED_ATTRS + [
        '_global_session']

    def getCustomProperties(self):
        adapter.SaMappedClassAlias.getCustomProperties(self)

        self.descriptor = self.klass._descriptor
        self.parent_descriptor = None

        if self.descriptor.parent:
            self.parent_descriptor = self.descriptor.parent._descriptor

        foreign_constraints = []

        for constraint in self.descriptor.constraints:
            for col in constraint.columns:
                col = str(col)

                if adapter.__version__.startswith('0.6'):
                    foreign_constraints.append(col)
                else:
                    if col.startswith(self.descriptor.tablename + '.'):
                        foreign_constraints.append(col[len(self.descriptor.tablename) + 1:])

        if self.descriptor.polymorphic:
            self.exclude_attrs.update([self.descriptor.polymorphic])

        self.exclude_attrs.update(foreign_constraints)

    def _compile_base_class(self, klass):
        if klass is elixir.EntityBase or klass is elixir.Entity:
            return

        pyamf.ClassAlias._compile_base_class(self, klass)


pyamf.register_alias_type(ElixirAdapter, elixir.entity.is_entity)