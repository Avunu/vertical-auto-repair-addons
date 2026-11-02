from . import models


def post_init_hook(env):
    """Seed the demo scenario once the module and its dependencies are loaded."""
    env["shop.demo.seed"].seed()
