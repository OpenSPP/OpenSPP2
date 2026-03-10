# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging
import threading

from odoo import api, models

_logger = logging.getLogger(__name__)

# Thread-local storage to pass import match counts from load() to execute_import()
_import_match_local = threading.local()


class Base(models.AbstractModel):
    _inherit = "base"

    @api.model
    def load(self, fields, data):
        usable, field_to_match = self.env["spp.import.match"]._usable_rules(
            self._name,
            fields,
            option_config_ids=self.env.context.get("import_match_ids", []),
        )
        overwrite_match = self.env.context.get("overwrite_match", False)

        if usable:
            newdata = list()
            match_created = 0
            match_skipped = 0
            match_overwritten = 0
            if ".id" in fields:
                column = fields.index(".id")
                fields[column] = "id"
                for values in data:
                    dbid = int(values[column])
                    values[column] = self.browse(dbid).get_external_id().get(dbid)
            import_fields = list(map(models.fix_import_export_id_paths, fields))
            # Odoo 19: _convert_records requires savepoint parameter
            converted_data = list(self._convert_records(self._extract_records(import_fields, data), savepoint=True))

            if "id" not in fields:
                fields.append("id")
                import_fields.append(["id"])
            clean_fields = []
            for f in import_fields:
                field_name = f[0]
                if len(f) > 1:
                    field_name += "/" + f[1]
                clean_fields.append(field_name)
            for dbid, xmlid, record, info in converted_data:
                if len(clean_fields) > len(data[info["record"]]):
                    data[info["record"]].append(None)

                _logger.debug("CLEAN FIELDS: %s", clean_fields)
                _logger.debug("Processing record at index %d", info["record"])
                row = dict(zip(clean_fields, data[info["record"]], strict=True))

                match = self
                if xmlid:
                    _logger.debug("XMLID: %s", xmlid)
                    row["id"] = xmlid
                    newdata.append(tuple(row[f] for f in clean_fields))
                    continue
                elif dbid:
                    _logger.debug("DBID: %s", dbid)
                    match = self.browse(dbid)
                else:
                    match = self.env["spp.import.match"]._match_find(self, record, row)
                    _logger.debug("MATCH found: record_id=%s", match.id if match else None)

                match.export_data(fields)

                ext_id = match.get_external_id()
                row["id"] = ext_id[match.id] if match else row.get("id", "")
                if match:
                    if overwrite_match:
                        match_overwritten += 1
                        flat_fields_to_remove = [item for sublist in field_to_match for item in sublist]
                        for fields_pop in flat_fields_to_remove:
                            # Set one2many and many2many fields to False if matched
                            # to avoid duplicates in one2many or many2many when exporting data
                            if fields_pop in row and match._fields[fields_pop].type in [
                                "one2many",
                                "many2many",
                            ]:
                                row[fields_pop] = False
                        newdata.append(tuple(row[f] for f in clean_fields))
                    else:
                        match_skipped += 1
                else:
                    match_created += 1
                    newdata.append(tuple(row[f] for f in fields))
            data = newdata
            if self.env.context.get("import_match_ids"):
                _import_match_local.counts = {
                    "created": match_created,
                    "skipped": match_skipped,
                    "overwritten": match_overwritten,
                }
        return super().load(fields, data)

    def write(self, vals):
        new_vals = vals.copy()
        for field_name, value in vals.items():
            if not value and field_name in self._fields:
                field_meta = self._fields[field_name]
                if field_meta.type in ("one2many", "many2many"):
                    new_vals.pop(field_name)
        return super().write(new_vals)
