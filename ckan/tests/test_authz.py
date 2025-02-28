# encoding: utf-8

import six
import unittest.mock as mock
import pytest

from ckan import authz as auth, model, logic

from ckan.tests import factories, helpers
from ckan.lib.create_test_data import CreateTestData

_check = auth.check_config_permission


@pytest.mark.ckan_config("ckan.auth.anon_create_dataset", None)
@pytest.mark.parametrize(
    "perm", ["anon_create_dataset", "ckan.auth.anon_create_dataset"]
)
def test_get_default_value_if_not_set_in_config(perm):
    assert (
        _check(perm) == auth.CONFIG_PERMISSIONS_DEFAULTS["anon_create_dataset"]
    )


@pytest.mark.ckan_config("ckan.auth.anon_create_dataset", True)
def test_config_overrides_default():
    assert _check("anon_create_dataset") is True


@pytest.mark.ckan_config("ckan.auth.anon_create_dataset", True)
def test_config_override_also_works_with_prefix():
    assert _check("ckan.auth.anon_create_dataset") is True


@pytest.mark.ckan_config("ckan.auth.unknown_permission", True)
def test_unknown_permission_returns_false():
    assert _check("unknown_permission") is False


def test_unknown_permission_not_in_config_returns_false():
    assert _check("unknown_permission") is False


def test_default_roles_that_cascade_to_sub_groups_is_a_list():
    assert isinstance(_check("roles_that_cascade_to_sub_groups"), list)


@pytest.mark.ckan_config(
    "ckan.auth.roles_that_cascade_to_sub_groups", "admin editor"
)
def test_roles_that_cascade_to_sub_groups_is_a_list():
    assert sorted(_check("roles_that_cascade_to_sub_groups")) == sorted(
        ["admin", "editor"]
    )


@mock.patch('flask.globals.RuntimeError')
def test_get_user_outside_web_request_py3(mock_RuntimeError):
    auth._get_user("example")
    assert mock_RuntimeError.called


@pytest.mark.usefixtures("with_request_context", "clean_db")
def test_get_user_inside_web_request_returns_user_obj():
    user = factories.User()
    assert auth._get_user(user["name"]).name == user["name"]


@pytest.mark.usefixtures("with_request_context")
def test_get_user_inside_web_request_not_found():

    assert auth._get_user("example") is None


@pytest.mark.usefixtures("with_request_context", "app")
def test_no_attributes_set_on_imported_auth_members():
    import ckan.logic.auth.get as auth_get
    import ckan.plugins.toolkit as tk

    tk.check_access("site_read", {})
    assert hasattr(auth_get.package_show, "auth_allow_anonymous_access")
    assert not hasattr(auth_get.config, "auth_allow_anonymous_access")


@pytest.mark.usefixtures("clean_db", "with_request_context")
class TestAuthOrgHierarchy(object):
    def test_parent_admin_auth(self):
        user = factories.User()
        parent = factories.Organization(
            users=[{"capacity": "admin", "name": user["name"]}]
        )
        child = factories.Organization()
        helpers.call_action(
            "member_create",
            id=child["id"],
            object=parent["id"],
            object_type="group",
            capacity="parent",
        )
        context = {"model": model, "user": user["name"]}
        helpers.call_auth(
            "organization_member_create", context, id=parent["id"]
        )
        helpers.call_auth(
            "organization_member_create", context, id=child["id"]
        )

        helpers.call_auth("package_create", context, owner_org=parent["id"])
        helpers.call_auth("package_create", context, owner_org=child["id"])

    def test_child_admin_auth(self):
        user = factories.User()
        parent = factories.Organization()
        child = factories.Organization(
            users=[{"capacity": "admin", "name": user["name"]}]
        )
        helpers.call_action(
            "member_create",
            id=child["id"],
            object=parent["id"],
            object_type="group",
            capacity="parent",
        )
        context = {"model": model, "user": user["name"]}
        with pytest.raises(logic.NotAuthorized):
            helpers.call_auth(
                "organization_member_create", context, id=parent["id"]
            )
        helpers.call_auth(
            "organization_member_create", context, id=child["id"]
        )

        with pytest.raises(logic.NotAuthorized):
            helpers.call_auth(
                "package_create", context, owner_org=parent["id"]
            )
        helpers.call_auth("package_create", context, owner_org=child["id"])

    def test_parent_editor_auth(self):
        user = factories.User()
        parent = factories.Organization(
            users=[{"capacity": "editor", "name": user["name"]}]
        )
        child = factories.Organization()
        helpers.call_action(
            "member_create",
            id=child["id"],
            object=parent["id"],
            object_type="group",
            capacity="parent",
        )
        context = {"model": model, "user": user["name"]}
        with pytest.raises(logic.NotAuthorized):
            helpers.call_auth(
                "organization_member_create", context, id=parent["id"]
            )
        with pytest.raises(logic.NotAuthorized):
            helpers.call_auth(
                "organization_member_create", context, id=child["id"]
            )

        helpers.call_auth("package_create", context, owner_org=parent["id"])
        with pytest.raises(logic.NotAuthorized):
            helpers.call_auth("package_create", context, owner_org=child["id"])

    def test_child_editor_auth(self):
        user = factories.User()
        parent = factories.Organization()
        child = factories.Organization(
            users=[{"capacity": "editor", "name": user["name"]}]
        )
        helpers.call_action(
            "member_create",
            id=child["id"],
            object=parent["id"],
            object_type="group",
            capacity="parent",
        )
        context = {"model": model, "user": user["name"]}
        with pytest.raises(logic.NotAuthorized):
            helpers.call_auth(
                "organization_member_create", context, id=parent["id"]
            )
        with pytest.raises(logic.NotAuthorized):
            helpers.call_auth(
                "organization_member_create", context, id=child["id"]
            )

        with pytest.raises(logic.NotAuthorized):
            helpers.call_auth(
                "package_create", context, owner_org=parent["id"]
            )
        helpers.call_auth("package_create", context, owner_org=child["id"])
