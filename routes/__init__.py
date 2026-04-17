from .main import register_main_routes


def register_routes(app):
    """Register all application route groups."""
    register_main_routes(app)
