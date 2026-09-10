# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Minimal fake-model loader for tests, adapted for Odoo 19.

Registers throwaway model classes into the live registry so tests can
exercise abstract mixins (here: spp.encrypted.field.mixin) on a concrete
model without shipping one in the module.

This is a scoped adaptation of odoo-test-helper's FakeModelLoader (LGPL,
ACSONE/Camptocamp/Akretion): the released helper (2.1.3) targets
``MetaModel.module_to_models`` and ``Registry.setup_models``, which Odoo 19
renamed to ``_module_to_models__`` / ``_setup_models__`` (and ``Registry.load``
now takes a module node instead of a cursor). Only the "add brand-new
models" case is supported — do NOT use this to extend existing models
(that needs the full backup/restore of their ``__bases__``). Replace with
odoo-test-helper once it supports Odoo 19.

Usage (TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.loader = FakeModelLoader(cls.env, "spp_pii_encryption")
        cls.loader.backup_registry()
        from .fake_models import EncryptionTestRecord
        cls.loader.update_registry((EncryptionTestRecord,))

    @classmethod
    def tearDownClass(cls):
        cls.loader.restore_registry()
        super().tearDownClass()
"""

from types import SimpleNamespace
from unittest import mock

from odoo import models
from odoo.tools import OrderedSet


class FakeModelLoader:
    def __init__(self, env, module_name):
        self.env = env
        self.module_name = module_name
        self._module_to_models = models.MetaModel._module_to_models__
        self._known_models = None
        self._orig_module_to_models = None

    def backup_registry(self):
        self.env.flush_all()
        self._known_models = set(self.env.registry.models)
        self._orig_module_to_models = {key: list(value) for key, value in self._module_to_models.items()}

    def update_registry(self, odoo_models):
        for model in odoo_models:
            if any(model._name == known for known in self._known_models):
                raise AssertionError(f"{model._name} already exists; this loader only adds new models")
            if model not in self._module_to_models[self.module_name]:
                self._module_to_models[self.module_name].append(model)

        registry = self.env.registry
        # The test cursor must never commit; registry.load/init_models are
        # written for the install path.
        with mock.patch.object(self.env.cr, "commit"):
            model_names = registry.load(SimpleNamespace(name=self.module_name))
            registry._setup_models__(self.env.cr)
            new_names = [name for name in model_names if name not in self._known_models]
            registry.init_models(self.env.cr, new_names, {"module": self.module_name})

    def restore_registry(self):
        registry = self.env.registry
        for name in set(registry.models) - self._known_models:
            del registry.models[name]
        for key, value in self._orig_module_to_models.items():
            self._module_to_models[key] = list(value)
        for key in set(self._module_to_models) - set(self._orig_module_to_models):
            del self._module_to_models[key]
        # Drop dangling references the fake models left on their parents
        # (e.g. the mixin's _inherit_children)
        for model_cls in registry.models.values():
            model_cls._inherit_children = OrderedSet(
                name for name in model_cls._inherit_children if name in registry.models
            )
        with mock.patch.object(self.env.cr, "commit"):
            registry._setup_models__(self.env.cr)
