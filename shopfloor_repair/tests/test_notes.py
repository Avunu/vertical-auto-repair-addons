# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.tests.common import tagged

from .common import RepairJobCase


@tagged("post_install", "-at_install")
class TestNotes(RepairJobCase):
    def test_note_is_appended_and_tagged_with_the_technician(self):
        self.repair.sudo().internal_notes = "<p>Earlier note</p>"
        response = self._dispatch(
            "add_note", repair_id=self.repair.id, note="Brake <b>pads</b> worn"
        )
        self.assert_next_state(response, "services")
        self.assert_no_error(response)
        notes = self.repair.internal_notes
        self.assertIn("Earlier note", notes)
        self.assertIn("[Tina Technician]", notes)
        self.assertIn("Brake &lt;b&gt;pads&lt;/b&gt; worn", notes)
        self.assertIn("Brake", self.state_data(response)["notes"])

    def test_note_is_posted_with_the_subtype_to_followers(self):
        subtype = self.env.ref("shopfloor_repair.mt_repair_technician_note")
        advisor = (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "Sam Advisor",
                    "login": "sam.advisor",
                    "email": "sam@example.com",
                }
            )
        )
        self.repair.sudo().message_subscribe(
            partner_ids=advisor.partner_id.ids, subtype_ids=subtype.ids
        )
        self._dispatch("add_note", repair_id=self.repair.id, note="Needs rotors")
        message = self.repair.sudo().message_ids[0]
        self.assertEqual(message.subtype_id, subtype)
        self.assertIn(advisor.partner_id, message.notified_partner_ids)

    def test_empty_note_is_rejected(self):
        before = self.repair.internal_notes
        response = self._dispatch("add_note", repair_id=self.repair.id, note="  ")
        self.assertEqual(response["message"]["message_type"], "error")
        self.assertEqual(self.repair.internal_notes, before)
