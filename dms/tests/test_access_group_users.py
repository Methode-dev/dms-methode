# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo.tests.common import TransactionCase, new_test_user


class AccessGroupUsersTestCase(TransactionCase):
    """Access group members follow Odoo group membership changes made after
    the access group was saved (users stored on the group are computed)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dms_user_group = cls.env.ref("dms.group_dms_user")
        cls.access_group = cls.env["dms.access.group"].create(
            {
                "name": "Documents users",
                "perm_write": True,
                "group_ids": [(6, 0, [cls.dms_user_group.id])],
            }
        )
        cls.user = new_test_user(cls.env, login="dms-late-user", groups="base.group_user")

    def test_user_granted_group_afterwards(self):
        self.assertNotIn(self.user, self.access_group.users)
        self.user.write({"group_ids": [(4, self.dms_user_group.id)]})
        self.assertIn(self.user, self.access_group.users)
        self.user.write({"group_ids": [(3, self.dms_user_group.id)]})
        self.assertNotIn(self.user, self.access_group.users)

    def test_group_granted_user_afterwards(self):
        self.dms_user_group.write({"user_ids": [(4, self.user.id)]})
        self.assertIn(self.user, self.access_group.users)

    def test_implied_group_counts(self):
        self.user.write({"group_ids": [(4, self.env.ref("dms.group_dms_manager").id)]})
        self.assertIn(self.user, self.access_group.users)

    def test_new_user_with_group(self):
        user = new_test_user(self.env, login="dms-new-user", groups="dms.group_dms_user")
        self.assertIn(user, self.access_group.users)
