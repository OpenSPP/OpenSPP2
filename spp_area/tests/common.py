import base64
import os

from odoo.tests.common import TransactionCase


class AreaImportBaseTestMixin(TransactionCase):
    @staticmethod
    def _get_test_file_path(filename):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

    @staticmethod
    def get_file_path_irq():
        return AreaImportBaseTestMixin._get_test_file_path("irq_adminboundaries_tabulardata.xlsx")

    @staticmethod
    def get_file_path_pse():
        return AreaImportBaseTestMixin._get_test_file_path("pse_adminboundaries_tabulardata.xlsx")

    @staticmethod
    def get_file_path_lka():
        """Sri Lanka - uses admin{N}Name_{lang} format"""
        return AreaImportBaseTestMixin._get_test_file_path("lka_adminboundaries_tabulardata.xlsx")

    @staticmethod
    def get_file_path_tgo():
        """Togo - uses French as primary language (no EN column)"""
        return AreaImportBaseTestMixin._get_test_file_path("tgo_adminboundaries_tabulardata.xlsx")

    @staticmethod
    def get_file_path_phl():
        """Philippines - standard format with many levels"""
        return AreaImportBaseTestMixin._get_test_file_path("phl_adminboundaries_tabulardata.xlsx")

    @classmethod
    def _create_import_from_file(cls, file_path):
        """Helper to create an area import record from a file path"""
        with open(file_path, "rb") as f:
            xls_file_name = os.path.basename(f.name)
            xls_file = base64.b64encode(f.read())

        return cls.env["spp.area.import"].create(
            {
                "excel_file": xls_file,
                "name": xls_file_name,
                "state": "Uploaded",
            }
        )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Set context to avoid job queue delay for faster tests
        # Note: job_worker module uses 'queue_job__no_delay' (double underscore)
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                queue_job__no_delay=True,
            )
        )

        # Iraq - standard format (EN + AR)
        cls.area_import_id = cls._create_import_from_file(cls.get_file_path_irq())

        # Palestine - standard format, smaller file
        cls.area_import_id_2 = cls._create_import_from_file(cls.get_file_path_pse())

        # Sri Lanka - different column naming convention
        cls.area_import_lka = cls._create_import_from_file(cls.get_file_path_lka())

        # Togo - French as primary language
        cls.area_import_tgo = cls._create_import_from_file(cls.get_file_path_tgo())

        # Philippines - standard format, many rows
        cls.area_import_phl = cls._create_import_from_file(cls.get_file_path_phl())
