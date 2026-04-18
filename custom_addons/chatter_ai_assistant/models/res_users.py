# -*- coding: utf-8 -*-

from odoo import models


class ResUsers(models.Model):
    _inherit = "res.users"

    def _init_odoobot(self):
        run_model = self.env["chatter.ai.run"]
        if not run_model._config()["private_chat_enabled"]:
            return super()._init_odoobot()
        self.ensure_one()
        odoobot = self.env.ref("base.partner_root", raise_if_not_found=False)
        if not odoobot:
            return False
        channel = self.env["discuss.channel"]._get_or_create_chat([odoobot.id, self.partner_id.id])
        self.sudo().odoobot_state = "disabled"
        return channel
