import os

import pytest
from benedict import BeneDict

from uudex_server.services import create_services, get_services

XFAIL_18_CONFIG = pytest.mark.xfail(strict=True, reason="#18: imports the removed uudex_server.core.config; fits no listed class")


@XFAIL_18_CONFIG
def test_load_config():
    from uudex_server.core.config import load_config

    # Note ENV_FILE is specified in conftest.py in this directory or one above this.
    my_dict = load_config(os.environ.get("ENV_FILE"))
    assert my_dict
    assert isinstance(my_dict, BeneDict)

    assert my_dict.DEV == True
    assert my_dict.X_SSL_CERT is not None


@XFAIL_18_CONFIG
def test_create():
    from uudex_server.core.config import load_config

    my_dict = load_config(os.environ.get("ENV_FILE"))

    with pytest.raises(RuntimeError):
        get_services()

    resp = create_services(my_dict)
    resp2 = get_services()
    assert resp is resp2
    assert resp
    assert resp.db_service
    # assert resp.auth_service
    # assert resp.authz_service
