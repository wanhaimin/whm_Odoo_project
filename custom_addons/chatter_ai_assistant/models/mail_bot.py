# -*- coding: utf-8 -*-

from odoo import models


class MailBot(models.AbstractModel):
    _inherit = "mail.bot"

    def _apply_logic(self, channel, values, command=None):
        run_model = self.env["chatter.ai.run"]
        pseudo_message = self.env["mail.message"].new(
            {
                "model": "discuss.channel",
                "res_id": channel.id,
                "author_id": values.get("author_id"),
                "body": values.get("body"),
                "message_type": values.get("message_type") or "comment",
            }
        )
        if run_model._is_odoobot_private_chat(pseudo_message):
            return
        return super()._apply_logic(channel, values, command=command)
