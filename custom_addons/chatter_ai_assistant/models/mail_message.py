# -*- coding: utf-8 -*-

from odoo import api, models


class MailMessage(models.Model):
    _inherit = "mail.message"

    @api.model_create_multi
    def create(self, vals_list):
        messages = super().create(vals_list)
        run_model = self.env["chatter.ai.run"]
        for message in messages:
            if message.model == "chatter.ai.run":
                continue
            if message.subtype_id and message.subtype_id.internal:
                continue
            if run_model._should_trigger_from_message(message):
                run = run_model.create_run_from_message(message)
                if run:
                    run._trigger_processing()
        return messages
